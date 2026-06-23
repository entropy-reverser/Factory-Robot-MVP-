import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch the gripper URDF (standalone) + controller_manager + position controller.
    
    This launch file is intended to be included AFTER the robot is spawned,
    or run standalone if the gripper URDF is already part of the robot description.
    """
    pkg_gripper = get_package_share_directory("robot_gripper")
    
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    
    # Load the gripper controller parameters
    controller_config = os.path.join(pkg_gripper, "config", "gripper_controller.yaml")

    # Controller manager node (spawns the ros2_control controller)
    # Note: In Ignition, the controller manager is typically started via
    #       the ign_ros2_control plugin embedded in the robot URDF.
    #       This node is a fallback for standalone testing.
    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[
            controller_config,
            {"use_sim_time": use_sim_time},
        ],
        output="screen",
    )

    # Spawner for the gripper position controller
    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "gripper_position_controller",
            "--controller-manager",
            "/controller_manager",
        ],
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        controller_manager,
        gripper_controller_spawner,
    ])
