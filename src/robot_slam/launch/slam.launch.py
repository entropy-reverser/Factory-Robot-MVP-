import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """
    启动 SLAM 建图节点（slam_toolbox） + RViz 可视化
    前置条件：机器人已在仿真中生成，且 /scan 与 /odom topic 正常发布
    """
    pkg_slam = get_package_share_directory("robot_slam")
    rviz_config = os.path.join(pkg_slam, "config", "slam.rviz")
    # 如果 RViz 配置文件不存在，可以去掉 rviz_node 或手动保存配置

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    # slam_toolbox 节点：异步在线建图
    slam_node = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[
            os.path.join(pkg_slam, "config", "slam_toolbox.yaml"),
            {"use_sim_time": use_sim_time},
        ],
        remappings=[
            ("/scan", "/scan"),
            ("/odom", "/odom"),
        ],
    )

    # RViz 可视化（可选，方便观察地图与激光数据）
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", rviz_config] if os.path.exists(rviz_config) else [],
        parameters=[{"use_sim_time": use_sim_time}],
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation time"),
        slam_node,
        rviz_node,
    ])
