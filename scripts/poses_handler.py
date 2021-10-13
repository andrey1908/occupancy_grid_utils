from tqdm import tqdm
import numpy as np
import rosbag
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from tf_conversions import fromTf, fromMsg, toMsg, fromMatrix, toMatrix


def ros_message_to_matrix(ros_message):
    if ros_message._type == 'geometry_msgs/TransformStamped':
        return toMatrix(fromTf(((ros_message.transform.translation.x, ros_message.transform.translation.y, ros_message.transform.translation.z), \
            (ros_message.transform.rotation.x, ros_message.transform.rotation.y, ros_message.transform.rotation.z, ros_message.transform.rotation.w))))
    if ros_message._type == 'nav_msgs/Odometry':
        return toMatrix(fromMsg(ros_message.pose.pose))
    raise TypeError("Unknown type {}".format(type(ros_message)))


def read_poses(bag, topic, use_tqdm=False):
    timestamps = list()
    poses = list()
    frame_id = None
    child_frame_id = None
    if use_tqdm:
        bag_reader = tqdm(bag.read_messages(topics=[topic]), total=bag.get_message_count(topic_filters=[topic]))
    else:
        bag_reader = bag.read_messages(topics=[topic])
    for _, msg, t in bag_reader:
        if child_frame_id:
            if child_frame_id != msg.child_frame_id:
                raise RuntimeError
        else:
            child_frame_id = msg.child_frame_id
        if frame_id:
            if frame_id != msg.header.frame_id:
                raise RuntimeError
        else:
            frame_id = msg.header.frame_id
        timestamps.append(msg.header.stamp)
        poses.append(ros_message_to_matrix(msg))
    return timestamps, poses, frame_id, child_frame_id


def read_poses_from_bag_files(rosbag_files, topic, use_tqdm=False):
    if isinstance(rosbag_files, str):
        rosbag_files = [rosbag_files]
    combined_timestamps = list()
    combined_poses = list()
    prev_frame_id = None
    prev_child_frame_id = None
    for rosbag_file in rosbag_files:
        with rosbag.Bag(rosbag_file) as bag:
            timestamps, poses, frame_id, child_frame_id = read_poses(bag, topic, use_tqdm=use_tqdm)
            combined_timestamps += timestamps
            combined_poses += poses
            if prev_frame_id is not None:
                if (prev_frame_id != frame_id) or (prev_child_frame_id != child_frame_id):
                    raise RuntimeError()
            prev_frame_id = frame_id
            prev_child_frame_id = child_frame_id
    return combined_timestamps, combined_poses, frame_id, child_frame_id


def move_first_pose_to_the_origin(poses):
    first_pose_inv = np.linalg.inv(poses[0])
    for i in range(len(poses)):
        poses[i] = first_pose_inv @ poses[i]


# 'transform' should move frame that is used now to desired frame
def transform_poses(poses, transform):
    transform_inv = np.linalg.inv(transform)
    for i in range(len(poses)):
        poses[i] = transform_inv @ poses[i] @ transform


def write_poses(out_file, poses):
    with open(out_file, 'w') as f:
        for i, pose in enumerate(poses):
            out_pose_str = '{:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e} {:.6e}'.format(
                    pose[0][0], pose[0][1], pose[0][2], pose[0][3],
                    pose[1][0], pose[1][1], pose[1][2], pose[1][3],
                    pose[2][0], pose[2][1], pose[2][2], pose[2][3])
            if i != len(poses) - 1:
                out_pose_str = out_pose_str + '\n'
            f.write(out_pose_str)


def poses_to_ros_path(poses, timestamps):
    path = Path()
    path.header.frame_id = 'map'
    path.header.stamp = timestamps[0]
    for pose, timestamp in zip(poses, timestamps):
        ros_pose = toMsg(fromMatrix(pose))
        pose_stamped = PoseStamped(pose=ros_pose)
        pose_stamped.header.frame_id = 'map'
        pose_stamped.header.stamp = timestamp
        path.poses.append(pose_stamped)
    return path
