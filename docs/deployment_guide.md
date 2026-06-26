# Factory Robot MVP — Deployment & Launch Guide (v2.0)

> **Prerequisites**: ROS2 Humble, Gazebo Ignition Fortress, Docker Desktop (WSL2 backend), `yolo26n.pt` weights file.  
> **Environment**: WSL2 Ubuntu 22.04 or native Linux. Windows host runs Docker Desktop with WSL integration.

---

## 1. Directory Layout (After Update)

```
factory_robot_mvp/
├── docker/
│   ├── Dockerfile                    # Base ROS2 Humble + build tools
│   ├── Dockerfile.vision             # YOLO service (inherits base)
│   ├── docker-compose.yml            # Split services (Gazebo on host)
│   └── entrypoint.sh
├── docs/
│   ├── design_doc.md
│   └── deployment_guide.md         # (this file)
├── src/
│   ├── factory_robot_description/  # Robot URDF + sensors
│   ├── factory_world/               # Factory SDF world
│   ├── robot_bringup/               # Top-level launch orchestration
│   ├── robot_slam/                  # SLAM + Nav2 configs
│   ├── robot_vision/                # YOLO detection node
│   │   ├── config/
│   │   │   └── yolo_detector.yaml
│   │   ├── launch/
│   │   │   └── yolo.launch.py
│   │   ├── robot_vision/
│   │   │   └── yolo_detector.py
│   │   ├── package.xml
│   │   └── setup.py
│   └── robot_gripper/               # 1-DOF gripper URDF + controller
│       ├── config/
│       │   └── gripper_controller.yaml
│       ├── launch/
│       │   └── gripper.launch.py
│       ├── urdf/
│       │   └── gripper.urdf.xacro
│       ├── package.xml
│       └── setup.py
└── yolo26n.pt                       # Pre-trained YOLO weights (host-mounted)
```

---

## 2. Host-Side Preparation (Native ROS2 + Gazebo)

### 2.1 Install ROS2 Humble (if not already)

Follow the [official ROS2 Humble installation guide](https://docs.ros.org/en/humble/Installation.html).

### 2.2 Install Gazebo Ignition (Fortress)

```bash
sudo apt update
sudo apt install -y ignition-fortress
```

Verify:
```bash
ign gazebo --version
```

### 2.3 Install Project Dependencies

```bash
sudo apt install -y \
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
  python3-colcon-common-extensions
```

### 2.4 Build Workspace (Host)

```bash
cd ~/factory_robot_mvp
rosdep install --from-paths src --ignore-src -y
colcon build --symlink-install
source install/setup.bash
```

> **Tip**: Add `source ~/factory_robot_mvp/install/setup.bash` to your `~/.bashrc`.

### 2.5 Place YOLO Weights

Ensure `yolo26n.pt` is at the project root:

```bash
ls ~/factory_robot_mvp/yolo26n.pt
```

If not, copy it there:

```bash
cp /path/to/yolo26n.pt ~/factory_robot_mvp/yolo26n.pt
```

---

## 3. Launch Scenarios

### 3.1 Scenario A: Full Simulation (Gazebo + SLAM + Robot)

Run on **host** (WSL2 or native Linux), not inside Docker.

```bash
# Terminal 1 — Launch everything (Gazebo + robot + SLAM + bridge)
ros2 launch robot_bringup robot_factory.launch.py
```

This starts:
- Gazebo Ignition with `factory_world.sdf`
- Robot spawner
- `ros_gz_bridge` for `/scan`, `/camera/*`, `/clock`
- `slam_toolbox` async online mapping
- RViz2

### 3.2 Scenario B: Add YOLO Vision (Docker)

#### Option B1 — Docker Compose (Recommended)

```bash    mirage
cd ~/factory_robot_mvp/docker

# Build vision service image
docker-compose build vision

# Start vision container (runs in background)
ROS_DOMAIN_ID=0 docker-compose up -d vision

# View logs
docker-compose logs -f vision
```

The `vision` container will:
- Subscribe to `/camera/color/image_raw` (bridged from host Gazebo via DDS)
- Publish `/vision/detections` and `/vision/detection_image`

#### Option B2 — Manual Docker Run

```bash
docker run -d --rm --name factory_vision \
  --network host \
  -e ROS_DOMAIN_ID=0 \
  -v ~/factory_robot_mvp/yolo26n.pt:/workspace/weights/yolo26n.pt:ro \
  -v ~/factory_robot_mvp/src:/workspace/src:ro \
  factory_robot_vision:latest \
  ros2 launch robot_vision yolo.launch.py
```

### 3.3 Scenario C: Add Gripper Control

```bash
# Terminal 2 — Launch gripper URDF + controller (host or Docker)
ros2 launch robot_gripper gripper.launch.py

# Terminal 3 — Send open/close commands
# Open gripper
ros2 topic pub /gripper_controller/commands std_msgs/msg/Float64MultiArray "data: [0.0]"

# Close gripper
ros2 topic pub /gripper_controller/commands std_msgs/msg/Float64MultiArray "data: [0.04]"
```

### 3.4 Scenario D: Full Stack (Everything)

```bash
# Terminal 1 — Host: Gazebo + Robot + SLAM
ros2 launch robot_bringup robot_factory.launch.py

# Terminal 2 — Host: Navigation (after map is saved)
ros2 launch robot_slam navigation.launch.py map:=~/factory_robot_mvp/src/robot_slam/maps/factory_map.yaml

# Terminal 3 — Docker: YOLO Vision
cd ~/factory_robot_mvp/docker && docker-compose up -d vision

# Terminal 4 — Docker or Host: Gripper
cd ~/factory_robot_mvp/docker && docker-compose up -d gripper

# Terminal 5 — Keyboard teleop (optional)
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

---

## 4. Docker Service Reference

### 4.1 `docker-compose.yml` Structure

```yaml
version: "3.8"

services:
  vision:
    build:
      context: ..
      dockerfile: docker/Dockerfile.vision
    image: factory_robot_vision:latest
    container_name: factory_vision
    network_mode: host
    environment:
      - ROS_DOMAIN_ID=0
    volumes:
      - ../yolo26n.pt:/workspace/weights/yolo26n.pt:ro
      - ../src/robot_vision:/workspace/src/robot_vision:ro
    command: >
      bash -c "source /opt/ros/humble/setup.bash &&
               source /workspace/install/setup.bash &&
               ros2 launch robot_vision yolo.launch.py"

  gripper:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    image: factory_robot:latest
    container_name: factory_gripper
    network_mode: host
    environment:
      - ROS_DOMAIN_ID=0
    volumes:
      - ../src:/workspace/src:ro
    command: >
      bash -c "source /opt/ros/humble/setup.bash &&
               source /workspace/install/setup.bash &&
               ros2 launch robot_gripper gripper.launch.py"
```

> **Note**: `gazebo` service is intentionally **removed**. Gazebo runs on the host to avoid X11/GPU forwarding issues.

### 4.2 `Dockerfile.vision` (YOLO Service)

```dockerfile
# Inherits from the base image
FROM factory_robot:latest

# Install Python inference dependencies
RUN pip3 install --no-cache-dir \
    ultralytics==8.0.200 \
    opencv-python-headless==4.8.1.78

# Pre-download PyTorch model weights (optional, speeds first inference)
# RUN python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Build the robot_vision package
WORKDIR /workspace
COPY src/robot_vision ./src/robot_vision
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --packages-select robot_vision --symlink-install"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
```

### 4.3 `Dockerfile` (Base Image — Updated)

```dockerfile
FROM osrf/ros:humble-desktop-full-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

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

WORKDIR /workspace
COPY src ./src

RUN rosdep init || true && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -y && \
    /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
```

---

## 5. Verification Checklist

### 5.1 Gazebo & Sensors

```bash
# Check all topics are alive
ros2 topic list

# Expected output:
# /camera/color/camera_info
# /camera/color/image_raw
# /camera/depth/image_raw
# /clock
# /cmd_vel
# /map
# /odom
# /scan
# /tf
# /vision/detections          <-- after YOLO container starts
# /vision/detection_image     <-- after YOLO container starts
```

### 5.2 YOLO Vision

```bash
# Echo detection messages
ros2 topic echo /vision/detections

# View annotated image (host RViz or image_view)
ros2 run rqt_image_view rqt_image_view /vision/detection_image
```

### 5.3 Gripper

```bash
# Check controller state
ros2 control list_controllers

# Expected:
# gripper_position_controller  [position_controllers/JointGroupPositionController] active

# Send command
ros2 topic pub /gripper_controller/commands std_msgs/msg/Float64MultiArray "data: [0.02]" --once
```

### 5.4 SLAM Map Save

```bash
# After mapping, save the map
ros2 run nav2_map_server map_saver_cli -f ~/factory_robot_mvp/src/robot_slam/maps/factory_map
```

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker-compose build` fails on `rosdep` | Missing `rosdep` initialization | Run `rosdep init && rosdep update` first |
| YOLO container cannot see `/camera/*` | DDS not crossing host/container boundary | Ensure `network_mode: host` and same `ROS_DOMAIN_ID` |
| Gazebo black screen | GPU driver issue in WSL2 | Run `export LIBGL_ALWAYS_SOFTWARE=1` before `ign gazebo` |
| Gripper controller not active | URDF not loaded | Launch `robot_gripper/gripper.launch.py` after robot spawn |
| No detections from YOLO | Model path wrong or class mismatch | Check `model_path` param; verify `yolo26n.pt` is mounted at `/workspace/weights/yolo26n.pt` |
| Nav2 fails to plan | No map or AMCL not localized | Use "2D Pose Estimate" in RViz before sending Nav2 Goal |

---

## 7. Performance Tuning

### 7.1 YOLO Inference Rate

The default YOLO inference may be CPU-heavy. Tune via `config/yolo_detector.yaml`:

```yaml
yolo_detector:
  ros__parameters:
    device: "cpu"          # "cuda" if GPU available inside container
    inference_rate: 5.0    # Hz (default 10 Hz, reduce if CPU throttled)
    image_queue_size: 1    # Drop old frames, keep only latest
```

### 7.2 DDS Tuning (Large Images)

The `/camera/color/image_raw` topic at 640×480 RGB is ~900 KB per message. If image transport causes lag, enable compression:

```bash
# On host, start image transport republish
ros2 run image_transport republish raw compressed --ros-args -r in:=/camera/color/image_raw -r out:=/camera/color/image_raw/compressed
```

Then update YOLO node to subscribe to the compressed topic.

---

## 8. Shutdown & Cleanup

```bash
# Stop Docker containers
cd ~/factory_robot_mvp/docker
docker-compose down

# Stop host ROS2 processes
# Press Ctrl+C in each terminal, or:
killall -9 rviz2 ign gazebo ros2
```

---

*End of Deployment Guide*
