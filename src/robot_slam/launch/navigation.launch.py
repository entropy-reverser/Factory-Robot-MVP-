import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    """
    启动 Nav2 导航栈（定位 + 规划 + 控制）
    前置条件：已完成建图并保存为 YAML + PGM 文件
    用法：
      ros2 launch robot_slam navigation.launch.py map:=path/to/factory_map.yaml
    """
    pkg_slam = get_package_share_directory("robot_slam")
    pkg_nav2 = get_package_share_directory("nav2_bringup")

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    map_yaml_file = LaunchConfiguration("map", default=os.path.join(pkg_slam, "maps", "factory_map.yaml"))

    # Nav2 bringup（包含 AMCL + 全局/局部规划器 + BT navigator + recovery）
    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2, "launch", "bringup_launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "map": map_yaml_file,
            "params_file": os.path.join(pkg_slam, "config", "nav2_params.yaml"),
            "autostart": "true",
        }.items(),
    )

    # RViz（带导航专用配置）
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("map", default_value=os.path.join(pkg_slam, "maps", "factory_map.yaml")),
        nav2_bringup,
        rviz_node,
    ])
