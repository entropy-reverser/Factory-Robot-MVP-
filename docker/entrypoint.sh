#!/bin/bash
# ============================================================
# Docker Entrypoint: Auto-source ROS2 environments
# ============================================================
set -e

# Source ROS2 Humble base
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

# Source workspace build (if present)
if [ -f /workspace/install/setup.bash ]; then
    source /workspace/install/setup.bash
fi

# Execute the command passed to the container
exec "$@"
