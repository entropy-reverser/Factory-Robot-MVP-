import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Launch the YOLO vision detector node with configurable parameters."""
    pkg_vision = get_package_share_directory("robot_vision")
    config_file = os.path.join(pkg_vision, "config", "yolo_detector.yaml")

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    yolo_node = Node(
        package="robot_vision",
        executable="yolo_detector",
        name="yolo_detector",
        output="screen",
        parameters=[
            config_file,
            {"use_sim_time": use_sim_time},
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        yolo_node,
    ])
