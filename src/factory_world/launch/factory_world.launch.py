import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    """
    启动工厂仿真世界（Gazebo Ignition）
    - 加载 factory_world.sdf
    - 启动 ros_gz_bridge（可选：桥接特定 topic）
    """
    pkg_world = get_package_share_directory("factory_world")
    world_file = os.path.join(pkg_world, "worlds", "factory_world.sdf")

    # 启动 Ignition Gazebo 仿真器
    ign_gazebo = ExecuteProcess(
        cmd=["ign", "gazebo", "-v", "4", "-r", world_file],
        output="screen",
        shell=False,
    )

    # 启动 ros_gz_bridge：将 Ignition 的 /clock 桥接到 ROS2
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/Clock[ignition.msgs.Clock",
        ],
        output="screen",
    )

    return LaunchDescription([
        ign_gazebo,
        bridge,
    ])
