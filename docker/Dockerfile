# ============================================================
# Factory Robot MVP — Base Docker Image
# ROS2 Humble + Gazebo Ignition + SLAM/Nav2 + ros2_control
# 
# Gazebo GUI runs on the HOST, not inside this container.
# This image is used for both base and derived vision/gripper services.
# ============================================================
FROM osrf/ros:humble-desktop-full-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# Install all ROS2 and system dependencies in a single layer
RUN apt-get update && apt-get install -y \
    ros-humble-slam-toolbox \
    ros-humble-nav2-bringup \
    ros-humble-nav2-map-server \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher \
    ros-humble-ros-gz \
    ros-humble-ros-gz-sim \
    ros-humble-ros-gz-bridge \
    ros-humble-xacro \
    ros-humble-teleop-twist-keyboard \
    ros-humble-cv-bridge \
    ros-humble-vision-msgs \
    ros-humble-ign-ros2-control \
    ros-humble-position-controllers \
    python3-pip \
    python3-rosdep \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Workspace setup
WORKDIR /workspace

# Copy source packages and build
COPY src ./src

RUN rosdep init || true && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -y && \
    /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

# Entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
