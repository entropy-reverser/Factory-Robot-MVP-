import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    """
    Top-level bringup: Factory world + robot spawn + ros_gz_bridge + SLAM.
    
    Gazebo runs on the HOST (native), not inside Docker. This launch file
    is meant to be executed on the host machine (WSL2 or native Linux).
    
    Docker containers (vision, gripper) connect via DDS host networking.
    """
    pkg_world = get_package_share_directory("factory_world")
    pkg_desc = get_package_share_directory("factory_robot_description")
    pkg_slam = get_package_share_directory("robot_slam")

    # 1) Launch factory simulation world
    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_world, "launch", "factory_world.launch.py")
        ),
    )

    # 2) Spawn robot into Gazebo
    spawn_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_desc, "launch", "robot_spawn.launch.py")
        ),
    )

    # 3) Launch SLAM toolbox
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_slam, "launch", "slam.launch.py")
        ),
    )

    # 4) ros_gz_bridge: bridge Ignition topics to ROS2
    #    Required for vision, SLAM, and navigation to receive sensor data.
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            # LiDAR scan
            "/scan@sensor_msgs/LaserScan[ignition.msgs.LaserScan",
            # RGB camera
            "/camera/color/image_raw@sensor_msgs/Image[ignition.msgs.Image",
            # Depth camera
            "/camera/depth/image_raw@sensor_msgs/Image[ignition.msgs.Image",
            # Camera calibration
            "/camera/color/camera_info@sensor_msgs/CameraInfo[ignition.msgs.CameraInfo",
            # Simulation clock
            "/clock@rosgraph_msgs/Clock[ignition.msgs.Clock",
        ],
        output="screen",
    )

    return LaunchDescription([
        world_launch,
        spawn_launch,
        bridge,
        slam_launch,
    ])
