# Factory Robot MVP — Design Document (v2.0)

> **Scope**: Analysis of existing dependencies, Docker feasibility, YOLO vision integration (no training), and gripper simulation design.  
> **Target**: ROS2 Humble + Gazebo Ignition (Fortress) + WSL2/Ubuntu 22.04

---

## 1. Existing Dependency Audit

### 1.1 Verified Humble-Compatible Packages

All dependencies declared in `Dockerfile` and `package.xml` files are verified as **ROS2 Humble (`ros-humble-*`)** packages:

| Package | Status | Humble? | Notes |
|---------|--------|---------|-------|
| `ros-humble-slam-toolbox` | ✅ Required | Yes | `async_online` mapping mode |
| `ros-humble-nav2-bringup` | ✅ Required | Yes | Global/local planner + AMCL |
| `ros-humble-nav2-map-server` | ✅ Required | Yes | Map save/load |
| `ros-humble-robot-state-publisher` | ✅ Required | Yes | TF tree from URDF |
| `ros-humble-joint-state-publisher` | ✅ Optional | Yes | GUI debugging only |
| `ros-humble-ros-gz` | ✅ Required | Yes | Meta-package for Gazebo bridge |
| `ros-humble-ros-gz-sim` | ✅ Required | Yes | `ros_gz_sim create` spawn |
| `ros-humble-ros-gz-bridge` | ✅ Required | Yes | Topic bridging Ignition ↔ ROS2 |
| `ros-humble-xacro` | ✅ Required | Yes | URDF macro expansion |
| `ros-humble-teleop-twist-keyboard` | ✅ Optional | Yes | Keyboard teleop for mapping |
| `ignition-fortress` | ✅ Required | N/A | Gazebo simulator, bundled with Humble |

**Verdict**: All declared dependencies are correct and aligned with ROS2 Humble. No deprecated or mismatched packages detected.

### 1.2 Missing / Recommended Additions

| Package | Reason |
|---------|--------|
| `ros-humble-cv-bridge` | Required for YOLO vision node (Image ↔ OpenCV) |
| `ros-humble-vision-msgs` | Standard `Detection2DArray` message for perception output |
| `python3-ultralytics` | YOLO inference engine (PyPI) |
| `ros-humble-ign-ros2-control` | Required if we add gripper via `ros2_control` |
| `ros-humble-position-controllers` | Joint position controller for gripper |
| `ros-humble-joint-trajectory-controller` | Optional for arm trajectories (future) |

---

## 2. Docker Feasibility & Redesign

### 2.1 Problem Statement

Running **Gazebo Ignition GUI inside Docker** requires:
- X11 socket forwarding (`/tmp/.X11-unix`)
- `DISPLAY` env var injection
- `privileged: true` (for GPU / render access)
- Host network mode (for DDS multicast discovery)

This is **brittle on WSL2** and adds unnecessary complexity. GPU-accelerated rendering inside Docker on WSL2 often fails with black-screen or GLX errors.

### 2.2 Design Decision: Gazebo Outside, ROS2 Nodes Inside

We adopt a **split-architecture**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOST (WSL2 / Native Ubuntu)                                        │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Gazebo Ignition      │  │ ROS2 Core + SLAM + Nav2 (optional)   │  │
│  │ (GUI + Physics)      │  │ (Can run native or in Docker)          │  │
│  └──────────────────────┘  └──────────────────────────────────────┘  │
│                          │                                          │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Docker Container      │  │ Docker Container                     │  │
│  │  ┌────────────────┐  │  │  ┌────────────────────────────────┐  │  │
│  │  │ YOLO Vision    │  │  │  │ Gripper Controller (optional)  │  │  │
│  │  │ (robot_vision) │  │  │  │ (robot_gripper)                │  │  │
│  │  └────────────────┘  │  │  └────────────────────────────────┘  │  │
│  └──────────────────────┘  └──────────────────────────────────────┘  │
│                          ▲                                          │
│                          │  DDS (host network)                       │
│  Shared ROS_DOMAIN_ID=0  │                                          │
└─────────────────────────────────────────────────────────────────────┘
```

**Rationale**:
- Gazebo runs natively on host → GUI works flawlessly, GPU acceleration intact.
- Docker containers run **compute-only** nodes (YOLO inference, controllers) → no GUI needed.
- `network_mode: host` ensures DDS discovery between host-native ROS2 and container ROS2.
- `ROS_DOMAIN_ID` isolates different robot fleets if needed.

### 2.3 Docker Best Practices Applied

1. **Multi-stage image hierarchy** (not full multi-stage, but modular services):
   - `factory_robot_base`: ROS2 Humble + build tools + colcon
   - `factory_robot_vision`: Base + `ultralytics` + `opencv-python` + `robot_vision` package
   - `factory_robot_gripper`: Base + `ros2_control` + `robot_gripper` package

2. **Layer caching**: Copy `src/` and compile before copying runtime configs. Dependencies that change less often (apt packages) are installed first.

3. **Non-root user**: The container runs as `root` (standard for ROS2 dev containers). For production, add a `rosuser` with UID/GID matching the host.

4. **Bind mounts for live development**: Mount `src/` from host into container so code changes do not require rebuild.

5. **Entrypoint script**: Automatically sources `/opt/ros/humble/setup.bash` and workspace `setup.bash`.

### 2.4 Docker Compose Services (Redesigned)

| Service | Runs In | Command | Network |
|---------|---------|---------|---------|
| `gazebo` | **Host** (not Docker) | `ign gazebo -r factory_world.sdf` | Host DDS |
| `vision` | Docker | `ros2 launch robot_vision yolo.launch.py` | `host` mode |
| `gripper` | Docker (optional) | `ros2 launch robot_gripper gripper.launch.py` | `host` mode |
| `nav2` | Host or Docker | `ros2 launch robot_slam navigation.launch.py` | Host DDS |

---

## 3. YOLO Vision Module Design (`robot_vision`)

### 3.1 Requirement

- **No training**: Use the existing `yolo26n.pt` weights file.
- **Sensor integration**: Subscribe to `/camera/color/image_raw` from the Gazebo depth camera.
- **Output standardization**: Publish `vision_msgs/Detection2DArray` so downstream nodes (gripper, navigation) can consume detections uniformly.
- **Modularity**: The node should be a standalone ROS2 Python node with clean separation between **image acquisition**, **inference**, and **result publishing**.

### 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Gazebo Ignition (Host)                                     │
│  ┌─────────────────┐    ┌─────────────────────────────┐      │
│  │ RGB-D Camera    │───▶│ /camera/color/image_raw     │      │
│  │ (640×480 @ 30Hz)│    │ /camera/color/camera_info   │      │
│  └─────────────────┘    └─────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (ros_gz_bridge)
┌─────────────────────────────────────────────────────────────┐
│  Docker Container — robot_vision                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  YOLODetectorNode (Python)                          │   │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │   │
│  │  │ ImageSubscriber  │──▶│ CvBridge (Image → CV2)   │ │   │
│  │  │ (sensor_msgs)    │  └──────────────────────────┘ │   │
│  │  └──────────────────┘             │                    │   │
│  │                                 ▼                    │   │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │   │
│  │  │ YOLOProcessor    │◀─│ Ultralytics YOLO(26n.pt) │ │   │
│  │  │ (class + bbox)   │  │ inference                │ │   │
│  │  └──────────────────┘  └──────────────────────────┘ │   │
│  │             │                                        │   │
│  │             ▼                                        │   │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │   │
│  │  │ ResultPublisher  │──▶│ /vision/detections       │ │   │
│  │  │ (vision_msgs)    │  │ /vision/detection_image    │   │
│  │  └──────────────────┘  └──────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Module Breakdown

#### `yolo_detector.py` — Main Node

```python
class YOLODetectorNode(Node):
    def __init__(self):
        # 1. Declare parameters (model path, confidence threshold, device)
        # 2. Load YOLO model (ultralytics.YOLO)
        # 3. Create subscribers: /camera/color/image_raw
        # 4. Create publishers: /vision/detections, /vision/detection_image
        # 5. Timer or callback-driven inference
```

**Parameters** (`yaml` config):
| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_path` | `/workspace/weights/yolo26n.pt` | Path to YOLO weights |
| `confidence_threshold` | `0.5` | Minimum confidence to publish |
| `device` | `auto` | `cpu`, `cuda`, or `auto` |
| `publish_visualization` | `True` | Publish annotated image |
| `input_topic` | `/camera/color/image_raw` | Image subscription topic |

#### `yolo.launch.py` — Launch File

- Reads `config/yolo_detector.yaml`
- Starts `yolo_detector.py` node
- Optionally starts `image_view` or `rviz2` for debugging

### 3.4 Why `vision_msgs`?

Using `vision_msgs/Detection2DArray` instead of a custom message ensures:
- **Interoperability**: Nav2, MoveIt2, and third-party tools already understand `vision_msgs`.
- **Standardization**: Bounding boxes are expressed in normalized image coordinates (`Detection2D`).
- **Extensibility**: Easy to add `vision_msgs/Detection3DArray` later when depth camera point cloud is fused.

### 3.5 Why Not Train?

MVP scope dictates **pre-trained inference only**. The existing `yolo26n.pt` is assumed to be trained on the factory cargo classes (e.g., "red_box", "blue_crate"). If classes are generic COCO, we can still run detection and filter by class ID in the node parameters.

---

## 4. Gripper Simulation Design (`robot_gripper`)

### 4.1 Requirement Analysis

We need to simulate a **simple 1-DOF gripper** (e.g., parallel-jaw or vacuum) that can:
1. Open / close via ROS2 topic command.
2. Attach to the `top_mount_link` already defined in the URDF.
3. Interact with the cargo boxes in Gazebo (collision detection).

### 4.2 Option Analysis

| Approach | Complexity | Pros | Cons | Verdict |
|----------|-----------|------|------|---------|
| **A. Pure Ignition Plugin (no ros2_control)** | Low | No extra ROS2 deps; simple `<plugin>` in SDF | Hard to interface with ROS2 topics; non-standard | ❌ Rejected |
| **B. ros2_control + Position Controller** | Medium | Standard ROS2 interface; clean topic API; easy to swap real hardware | Adds `ros2_control` dependency | ✅ **Recommended** |
| **C. MoveIt2 + JointTrajectoryController** | High | Full trajectory planning; collision-aware | Massive dependency; overkill for 1-DOF gripper | ❌ Rejected for MVP |

### 4.3 Design Decision: `ros2_control` with `position_controllers/JointGroupPositionController`

**Rationale**:
- `ros2_control` is the **standard ROS2 hardware abstraction layer**. Even for a simple gripper, using it means the same controller code works in simulation and on real hardware.
- The dependency cost (`ros-humble-ign-ros2-control`, `ros-humble-position-controllers`) is small (~50 MB) and already available in Ubuntu repos.
- **MoveIt2 is NOT needed** for a 1-DOF gripper. We can directly publish `std_msgs/Float64` to the controller command topic.

### 4.4 Gripper URDF Design

A minimal **parallel-jaw gripper** with two symmetrical fingers:

```
base_link (existing robot)
  └── top_mount_link (existing)
        └── gripper_base_link (new, fixed)
              ├── left_finger_link (prismatic joint: "left_finger_joint")
              └── right_finger_link (prismatic joint: "right_finger_joint", mimics left)
```

- `gripper_base_link`: Mount plate, fixed to `top_mount_link`.
- `left_finger_joint`: Prismatic, range `0.0` (open) to `0.04` (closed).
- `right_finger_joint`: Prismatic, **mimic** of left (negative direction), so one command drives both.

### 4.5 ros2_control Configuration

```yaml
ros2_control:
  - hardware:
      plugin: ign_ros2_control/IgnitionSystem
  - joint: left_finger_joint
    command_interface: position
    state_interface: position
  - controller: position_controllers/JointGroupPositionController
    joints: [left_finger_joint]
```

**Command interface**:
- Topic: `/position_controller/commands` (Float64MultiArray)
- Value `0.0` → open, `0.04` → closed

### 4.6 Interaction Logic (MVP — No Physics Plugin)

For MVP, we **do NOT** implement a full Gazebo grasping physics plugin (e.g., `gazebo_ros_link_attacher`). Instead:

1. The robot navigates to the cargo box.
2. The gripper descends (if arm exists) or approaches (if fixed mount).
3. The gripper closes (`position = 0.04`).
4. **Collision geometry** is sufficient for visual proof-of-concept; precise grasping physics is deferred to Phase 2.

If a **simple vacuum gripper** is preferred, the URDF can be reduced to a single `suction_cup_link` with no joints, and a ROS2 service node toggles a boolean `grasped` state. This avoids `ros2_control` entirely. However, since the user wants a **gripper** (implies mechanical fingers), the prismatic-joint approach is more realistic.

### 4.7 Final Decision

- **Use `ros2_control`** with `position_controllers/JointGroupPositionController` for the gripper.
- **Do NOT use MoveIt2** for MVP.
- The gripper is a **separate package** (`robot_gripper`) that can be omitted from bringup if not needed, preserving modularity.

---

## 5. Topic & Coordinate System Summary

### 5.1 New Topics (YOLO + Gripper)

| Topic | Type | Direction | Source |
|-------|------|-----------|--------|
| `/camera/color/image_raw` | `sensor_msgs/Image` | Gazebo → ROS2 | `depth_camera.xacro` |
| `/vision/detections` | `vision_msgs/Detection2DArray` | ROS2 → ROS2 | `robot_vision` |
| `/vision/detection_image` | `sensor_msgs/Image` | ROS2 → ROS2 | `robot_vision` (viz) |
| `/position_controller/commands` | `std_msgs/Float64MultiArray` | ROS2 → Controller | `robot_gripper` |
| `/gripper/command` | `std_msgs/Float64` | ROS2 → Controller | Wrapper node (optional) |

### 5.2 TF Tree (Updated)

```
map
  └── odom
        └── base_link
              ├── camera_link
              ├── lidar_link
              └── top_mount_link
                    └── gripper_base_link
                          ├── left_finger_link
                          └── right_finger_link
```

---

## 6. Extensibility Roadmap

| Phase | Feature | New Packages | Est. Effort |
|-------|---------|------------|-------------|
| **MVP (Now)** | YOLO inference + Gripper open/close | `robot_vision`, `robot_gripper` | 1–2 days |
| **Phase 2** | 3D object pose estimation (depth + bbox) | `robot_vision` extension | 2–3 days |
| **Phase 3** | Full 6-DOF arm + MoveIt2 trajectory | `robot_arm`, `robot_arm_moveit` | 1–2 weeks |
| **Phase 4** | Gazebo grasp physics (plugin) | Custom Ignition plugin | 1 week |
| **Phase 5** | Multi-robot fleet coordination | `fleet_manager` | 2 weeks |

---

## 7. Appendix: Package List (Final)

```
factory_robot_mvp/
├── src/
│   ├── factory_robot_description/   # (existing) URDF + Xacro
│   ├── factory_world/               # (existing) SDF world
│   ├── robot_slam/                  # (existing) SLAM + Nav2 config
│   ├── robot_bringup/               # (existing) Top-level launch
│   ├── robot_vision/                # (NEW) YOLO detection node
│   │   ├── robot_vision/
│   │   │   └── yolo_detector.py
│   │   ├── config/
│   │   │   └── yolo_detector.yaml
│   │   ├── launch/
│   │   │   └── yolo.launch.py
│   │   └── package.xml
│   └── robot_gripper/               # (NEW) Gripper URDF + controller
│       ├── urdf/
│       │   └── gripper.urdf.xacro
│       ├── config/
│       │   └── gripper_controller.yaml
│       ├── launch/
│       │   └── gripper.launch.py
│       └── package.xml
├── docker/
│   ├── Dockerfile                   # (updated) Base + vision layers
│   ├── Dockerfile.vision            # (NEW) YOLO-only service image
│   ├── docker-compose.yml           # (updated) Split services
│   └── entrypoint.sh
└── docs/
    ├── design_doc.md                # (this file)
    └── deployment_guide.md          # (next file)
```
