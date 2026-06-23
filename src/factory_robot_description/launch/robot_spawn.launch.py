import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():
    """
    生成并加载机器人 URDF，通过 robot_state_publisher 发布 TF，
    并通过 ros_gz_sim create 在 Gazebo Ignition 中生成实体。
    """
    pkg_desc = get_package_share_directory("factory_robot_description")
    xacro_file = os.path.join(pkg_desc, "urdf", "robot.urdf.xacro")

    # 启动参数
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    robot_namespace = LaunchConfiguration("robot_namespace", default="")
    x_pos = LaunchConfiguration("x_pos", default="0.0")
    y_pos = LaunchConfiguration("y_pos", default="0.0")
    z_pos = LaunchConfiguration("z_pos", default="0.15")

    # 通过 xacro 命令生成 URDF（运行时展开）
    robot_description = Command(["xacro", " ", xacro_file])

    # Robot State Publisher：发布 TF 树
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        namespace=robot_namespace,
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "robot_description": robot_description,
        }],
    )

    # Joint State Publisher（GUI 可选，用于调试）
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        namespace=robot_namespace,
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    # 在 Gazebo Ignition 中创建机器人实体
    # 注意：ros_gz_sim 的 create 节点需要参数：-world, -file, -name, -x, -y, -z
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-world", "factory_world",
            "-topic", "/robot_description",
            "-name", "factory_robot",
            "-x", x_pos,
            "-y", y_pos,
            "-z", z_pos,
        ],
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation time"),
        DeclareLaunchArgument("robot_namespace", default_value="", description="Robot namespace"),
        DeclareLaunchArgument("x_pos", default_value="0.0"),
        DeclareLaunchArgument("y_pos", default_value="0.0"),
        DeclareLaunchArgument("z_pos", default_value="0.15"),
        robot_state_publisher,
        joint_state_publisher,
        spawn_robot,
    ])
