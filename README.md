# Factory Robot MVP

> 基于 **ROS2 Humble + Gazebo Ignition** 的工厂移动机器人仿真全栈项目 —— 从 SLAM 建图、自主导航、YOLO 视觉检测到机械爪控制，通过 **Docker 实现环境隔离部署**。

---

## 项目概览

```
┌─────────────────────────────────────────────────────────────────┐
│                      HOST (WSL2 / Ubuntu 22.04)                 │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Gazebo       │  │ RViz2        │  │ ROS2 Core (SLAM/Nav2) │  │
│  │ Ignition     │  │ 可视化        │  │ slam_toolbox + Nav2   │  │
│  │ (仿真引擎)    │  │              │  │                       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘  │
│         │                  │                      │              │
│         └──────────────────┼──────────────────────┘              │
│                            │  DDS (ROS_DOMAIN_ID=0)              │
│  ┌─────────────────────────┼─────────────────────────────────┐  │
│  │         Docker Containers (network_mode: host)              │  │
│  │  ┌─────────────────┐    ┌─────────────────────────────┐   │  │
│  │  │ vision 容器      │    │ gripper 容器 (可选)          │   │  │
│  │  │ YOLO 目标检测    │    │ ros2_control 机械爪控制      │   │  │
│  │  │ ultralytics      │    │ position_controllers        │   │  │
│  │  └─────────────────┘    └─────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 核心能力

| 模块 | 功能 | 运行位置 |
|------|------|---------|
| `factory_world` | 厂房 SDF 仿真场景（墙壁/货架/货物箱） | Host |
| `factory_robot_description` | 差速底盘机器人 URDF（LiDAR + RGB-D Camera + Gripper） | Host |
| `robot_slam` | SLAM 在线建图 (`slam_toolbox`) + 自主导航 (`Nav2`) | Host |
| `robot_vision` | YOLO 目标检测节点，发布 `Detection2DArray` | Docker |
| `robot_gripper` | 1-DOF 平行夹爪 URDF + `ros2_control` 位置控制器 | Docker / Host |
| `robot_bringup` | 一键启动编排（世界 + 机器人 + 桥接 + SLAM） | Host |

---

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| **操作系统** | Ubuntu (Jammy Jellyfish) | 22.04 LTS |
| **运行环境** | WSL2 (Windows Subsystem for Linux 2) | 最新版 |
| **ROS 发行版** | ROS 2 Humble Hawksbill | humble |
| **仿真引擎** | Gazebo Ignition (Fortress) | fortress |
| **SLAM 方案** | slam_toolbox (async_online) | ros-humble |
| **导航框架** | Nav2 (AMCL + BT Navigator + DWB) | ros-humble |
| **目标检测** | Ultralytics YOLO (预训练推理) | v8.0.200+ |
| **硬件抽象** | ros2_control (IgnitionSystem) | ros-humble |
| **容器化** | Docker Engine + Docker Compose | latest |
| **基础镜像** | osrf/ros:humble-desktop-full-jammy | - |

---

## 开发环境要求

### 硬件要求

- **CPU**: 4 核心以上（YOLO 推理建议 6 核+）
- **内存**: 8 GB 以上（推荐 16 GB）
- **硬盘**: 20 GB 可用空间（Docker 镜像 + 编译缓存）
- **GPU**: 可选（CUDA 加速 YOLO 推理）

### 软件版本矩阵

```
Windows 11
  └── WSL2 (Ubuntu 22.04)
        ├── ROS2 Humble (ros-humble-desktop-full)
        ├── Gazebo Ignition Fortress
        ├── Docker Desktop (WSL2 backend)
        └── Python 3.10 (系统自带)
```

> **注意**: Gazebo GUI 必须运行在宿主机（Host），不放入 Docker 容器。这是为了避免 WSL2 下 X11/GPU 转发的兼容性问题。

---

## 项目结构

```
factory_robot_mvp/
├── docker/                          # Docker 部署配置
│   ├── Dockerfile                   # 基础镜像: ROS2 Humble + 全量依赖 + colcon build
│   ├── Dockerfile.vision            # YOLO 视觉服务镜像 (继承基础镜像 + ultralytics)
│   ├── docker-compose.yml           # 编排: vision / gripper 服务 (Gazebo 在 Host)
│   └── entrypoint.sh                # 容器入口: 自动 source ROS2 环境
│
├── docs/                            # 设计与部署文档
│   ├── architecture.md              # 系统架构详细说明
│   ├── design_doc.md                # 设计决策记录 (ADR)
│   ├── deployment_guide.md          # 完整部署与启动指南
│   └── setup_guide.md               # 环境搭建步骤
│
├── src/                             # ROS2 工作空间源码包
│   ├── factory_robot_description/   # 机器人本体描述
│   │   ├── urdf/
│   │   │   ├── robot.urdf.xacro     # 主 URDF: 差速底盘 + 轮子 + 传感器 + 夹爪
│   │   │   ├── gazebo_plugins.xacro # Ignition 差速驱动插件
│   │   │   └── sensors/
│   │   │       ├── lidar.xacro      # 360° 2D 激光雷达 → /scan
│   │   │       └── depth_camera.xacro # RGB-D 相机 → /camera/*
│   │   └── launch/
│   │       └── robot_spawn.launch.py
│   │
│   ├── factory_world/               # 仿真场景
│   │   ├── worlds/factory_world.sdf  # 厂房 SDF 场景文件
│   │   └── launch/factory_world.launch.py
│   │
│   ├── robot_bringup/               # 顶层启动入口
│   │   └── launch/robot_factory.launch.py  # 一键启动全部模块
│   │
│   ├── robot_slam/                  # 建图与导航
│   │   ├── config/
│   │   │   ├── slam_toolbox.yaml    # 异步在线建图参数
│   │   │   └── nav2_params.yaml     # Nav2 全参数 (AMCL/代价地图/DWB)
│   │   └── launch/
│   │       ├── slam.launch.py       # SLAM 建图 + RViz
│   │       └── navigation.launch.py # Nav2 导航 (需传入地图)
│   │
│   ├── robot_vision/                # YOLO 视觉检测
│   │   ├── robot_vision/
│   │   │   └── yolo_detector.py     # 检测节点 (订阅图像 → 推理 → 发布 Detection2DArray)
│   │   ├── config/yolo_detector.yaml
│   │   └── launch/yolo.launch.py
│   │
│   └── robot_gripper/               # 机械爪控制
│       ├── urdf/gripper.urdf.xacro  # 1-DOF 平行夹爪 Xacro (mimic 关节)
│       ├── config/gripper_controller.yaml
│       └── launch/gripper.launch.py
│
└── yolo26n.pt                       # YOLO 预训练权重文件 (需自行获取)
```

---

## 依赖清单

### ROS2 APT 包 (已打包在 Dockerfile 中)

| 包名 | 用途 |
|------|------|
| `ros-humble-slam-toolbox` | SLAM 在线建图 |
| `ros-humble-nav2-bringup` | 导航框架完整栈 |
| `ros-humble-nav2-map-server` | 地图保存/加载服务 |
| `ros-humble-robot-state-publisher` | URDF → TF 树发布 |
| `ros-humble-ros-gz` | Gazebo-Ignition ↔ ROS2 桥接元包 |
| `ros-humble-ros-gz-bridge` | Topic 双向桥接 (`parameter_bridge`) |
| `ros-humble-ros-gz-sim` | 实体生成工具 |
| `ros-humble-xacro` | URDF 宏展开 |
| `ros-humble-cv-bridge` | ROS Image ↔ OpenCV 转换 |
| `ros-humble-vision-msgs` | Detection2DArray 标准消息 |
| `ros-humble-ign-ros2-control` | Gazebo 仿真控制器接口 |
| `ros-humble-position-controllers` | 位置关节控制器 |
| `ros-humble-teleop-twist-keyboard` | 键盘遥控 |

### Python pip 包 (仅 vision 服务)

| 包名 | 版本 | 用途 |
|------|------|------|
| `ultralytics` | >=8.0.200 | YOLO 推理引擎 |
| `opencv-python-headless` | >=4.8.1 | 图像处理 (无 GUI) |
| `torch` | latest | PyTorch 后端 (自动安装) |

### 系统依赖

| 依赖 | 用途 |
|------|------|
| `ignition-fortress` | Gazebo Ignition 仿真器 |
| `python3-colcon-common-extensions` | ROS2 编译工具链 |
| `python3-pip` | Python 包管理 |
| `python3-rosdep` | ROS 依赖解析 |

---

## 设计原则

### 1. 分层架构 (Split Architecture)

```
GUI 层 (Gazebo/RViz)  ←→  计算层 (SLAM/Nav2/YOLO/Gripper)
     Host                    Docker Container
```

- **Gazebo 运行在宿主机**: 避免 WSL2 下 X11/GPU 转发的黑屏/GLX 问题
- **计算密集型节点容器化**: YOLO 推理、控制器等无 GUI 节点放入 Docker
- **DDS 通信桥接**: 通过 `network_mode: host` + 统一 `ROS_DOMAIN_ID=0` 实现跨边界通信

### 2. 模块化分包

每个功能独立为一个 ROS2 package，通过 `robot_bringup` 统一编排:

- 新增传感器 → 在 `urdf/sensors/` 添加 xacro，在 bridge 规则中添加 topic
- 新增功能 → 创建新 package (如 `robot_vision`, `robot_gripper`)
- 可选加载 → 夹爪/视觉包可按需启动，不影响核心建图导航流程

### 3. 标准化接口

- **视觉输出**: 使用 `vision_msgs/Detection2DArray` (非自定义消息)，确保与 Nav2/MoveIt2 兼容
- **控制输入**: 使用 `ros2_control` 标准框架，仿真代码可直接迁移到真实硬件
- **坐标系统一**: TF 树从 `map → odom → base_link → sensors/gripper` 层级清晰

### 4. 开发友好性

- `--symlink-install`: Python 代码修改后无需重新编译
- Bind mount `src/` 到容器: 主机代码变更即时反映到容器内
- 参数外置 YAML: 所有可调参数集中在 `config/` 目录

---

## 快速开始 (Docker 部署)

### Step 1: 环境准备

```bash
# 1. 安装 ROS2 Humble (桌面完整版)
sudo apt update && sudo apt install -y ros-humble-desktop-full

# 2. 安装 Gazebo Ignition Fortress
sudo apt install -y ignition-fortress && ign gazebo --version

# 3. 安装 Docker Desktop (启用 WSL2 backend)
#    下载: https://www.docker.com/products/docker-desktop/

# 4. 克隆项目
git clone https://github.com/entropy-reverser/Factory-Robot-MVP-.git ~/factory_robot_mvp
cd ~/factory_robot_mvp

# 5. 放置 YOLO 权重文件 (需自行获取 yolo26n.pt)
#    确保 yolo26n.pt 位于项目根目录
ls ~/factory_robot_mvp/yolo26n.pt
```

### Step 2: 宿主机编译工作空间

```bash
cd ~/factory_robot_mvp
rosdep install --from-paths src --ignore-src -y
colcon build --symlink-install
source install/setup.bash

# 推荐: 添加到 ~/.bashrc
echo "source ~/factory_robot_mvp/install/setup.bash" >> ~/.bashrc
```

### Step 3: 启动仿真 (一键)

```bash
# Terminal 1 — 启动 Gazebo + 机器人 + SLAM + 桥接 (全部在宿主机)
ros2 launch robot_bringup robot_factory.launch.py
```

这将依次启动:
1. Gazebo Ignition 加载厂房场景 `factory_world.sdf`
2. 生成差速驱动机器人实体 (带 LiDAR + Camera + Gripper)
3. `ros_gz_bridge` 桥接传感器话题
4. `slam_toolbox` 开始在线建图
5. 打开 RViz2 显示地图和机器人模型

### Step 4: 启动 Docker 服务 (可选)

```bash
# Terminal 2 — 构建并启动 YOLO 视觉服务
cd ~/factory_robot_mvp/docker
docker-compose build vision
docker-compose up -d vision

# Terminal 3 — 启动机械爪控制服务 (可选)
docker-compose up -d gripper
```

### Step 5: 验证与操作

```bash
# ====== 验证话题 ======
ros2 topic list
# 预期输出:
# /scan, /camera/color/image_raw, /camera/depth/image_raw, /clock
# /cmd_vel, /odom, /map, /tf
# /vision/detections          (YOLO 容器启动后)
# /vision/detection_image     (YOLO 容器启动后)

# ====== 键盘遥控 (建图时使用) ======
ros2 run teleop_twist_keyboard teleop_twist_keyboard
# i=前进 k=停止 ,=后退 j=左转 l=右转

# ====== 保存建图结果 ======
ros2 run nav2_map_server map_saver_cli -f \
  ~/factory_robot_mvp/src/robot_slam/maps/factory_map

# ====== 启动导航 (需要已有地图) ======
ros2 launch robot_slam navigation.launch.py \
  map:=~/factory_robot_mvp/src/robot_slam/maps/factory_map.yaml
# 然后在 RViz 中: 2D Pose Estimate → 设置初始位姿 → Nav2 Goal 发送目标

# ====== 控制夹爪 ======
# 张开夹爪
ros2 topic pub /gripper_controller/commands std_msgs/msg/Float64MultiArray \
  "data: [0.0]" --once
# 闭合夹爪
ros2 topic pub /gripper_controller/commands std_msgs/msg/Float64MultiArray \
  "data: [0.04]" --once

# ====== 查看 YOLO 检测结果 ======
ros2 topic echo /vision/detections
ros2 run rqt_image_view rqt_image_view /vision/detection_image
```

### Step 6: 停止与清理

```bash
# 停止所有 Docker 容器
cd ~/factory_robot_mvp/docker && docker-compose down

# 停止宿主机 ROS2 进程 (在各终端 Ctrl+C, 或)
killall rviz2 ign gazebo 2>/dev/null
```

---

## Docker 镜像架构

```
osrf/ros:humble-desktop-full-jammy
  │
  ├─► Dockerfile (基础镜像: factory_robot:latest)
  │     ├─ apt: 全部 ROS2 依赖 (slam-toolbox, nav2, ros-gz, ...)
  │     ├─ copy src/ → colcon build --symlink-install
  │     └─ entrypoint.sh (自动 source 环境)
  │
  └─► Dockerfile.vision (视觉镜像: factory_robot_vision:latest)
        ├─ FROM factory_robot:latest
        ├─ pip: ultralytics + opencv-python-headless + torch
        └─ colcon build --packages-select robot_vision
```

| 镜像 | 大小约 | 用途 |
|------|--------|------|
| `factory_robot:latest` | ~3.5 GB | 基础运行时 + 全量 ROS2 包 |
| `factory_robot_vision:latest` | ~5 GB | 基础 + YOLO 推理栈 |

---

## 核心 Topic 数据流

```
Gazebo Ignition ──bridge──▶ ROS2 Topic Bus
                                 │
    /scan (LaserScan) ──────────┼──▶ slam_toolbox ──▶ /map (OccupancyGrid)
    /camera/color/image_raw ────┼──▶ YOLODetectorNode ──▶ /vision/detections
    /camera/depth/image_raw ────┤                        /vision/detection_image
    /cmd_vel (Twist) ◀──────────┼──◀ Nav2 / teleop
    /odom (Odometry) ───────────┼──▶ AMCL / robot_state_publisher
    /clock (Clock) ─────────────┤   (时间同步)
    /tf (TFMessage) ════════════╛   (坐标变换树)
```

---

## 坐标系设计

```
map (全局地图坐标系)
  └── odom (里程计坐标系)
        └── base_link (机器人本体中心)
              ├── left_wheel_link / right_wheel_link (驱动轮)
              ├── caster_wheel_link (万向支撑轮)
              ├── top_mount_link (扩展安装位)
              │     └── gripper_base_link
              │           ├── left_finger_link
              │           └── right_finger_link (mimic joint)
              ├── lidar_link (激光雷达)
              └── camera_link (深度相机)
```

---

## 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| Gazebo 黑屏 | WSL2 GPU 渲染问题 | `export LIBGL_ALWAYS_SOFTWARE=1` |
| `/scan` 无数据 | bridge 未启动或 LiDAR 配置错误 | 检查 `parameter_bridge` 进程; 确认 `lidar.xacro` topic 为 `scan` |
| YOLO 容器看不到摄像头画面 | DDS 跨容器失败 | 确认 `network_mode: host` + `ROS_DOMAIN_ID=0` 一致 |
| Nav2 无法规划路径 | 未完成定位 | RViz 中先点击 "2D Pose Estimate" 设定初始位姿 |
| 夹爪控制器未激活 | URDF 未加载 | 先启动机器人 spawn，再启动 gripper launch |
| docker-compose build rosdep 失败 | 缺少初始化 | 先执行 `rosdep init && rosdep update` |
| YOLO 无检测结果 | 权重路径错误 | 确认 `yolo26n.pt` 已挂载到 `/workspace/weights/yolo26n.pt` |

---

## 后续优化路径

### Phase 1 — 当前 MVP (已完成)
- [x] SLAM 在线建图与地图保存
- [x] Nav2 自主导航 (DWB 局部规划器)
- [x] YOLO 目标检测 (Docker 隔离)
- [x] 1-DOF 平行夹爪 (ros2_control)

### Phase 2 — 3D 感知增强
- [ ] **深度融合检测**: 结合 RGB-D 点云与 2D BBox 输出 3D 位姿估计 (`Detection3DArray`)
- [ ] **点云分割**: 对货架/地面/障碍物进行语义分割
- [ ] **相机-LiDAR 融合**: 外参标定 + 联合滤波

### Phase 3 — 操作执行
- [ ] **6-DOF 机械臂**: 在 `top_mount_link` 挂载多关节臂 URDF + MoveIt2
- [ ] **抓取物理仿真**: 实现 Gazebo grasp plugin (link_attacher)
- [ ] **视觉伺服**: 基于检测框偏移量的闭环抓取控制

### Phase 4 — 系统工程
- [ ] **行为树任务编排**: 扩展 Nav2 BT，实现「导航→检测→抓取→放置」完整工作流
- [ ] **多机协调**: namespace 隔离 + DDS 多域通信
- [ ] **真机迁移**: 替换 IgnitionSystem 为真实硬件接口 (serial/CAN/EtherCAT)

### Phase 5 — 工程化
- [ ] **CI/CD Pipeline**: GitHub Actions 自动构建 Docker 镜像 + 单元测试
- [ ] **性能基准测试**: SLAM 精度 / 导航成功率 / YOLO 推理延迟 benchmark
- [ ] **Web 可视化**: Foxgbridge / Rosbridge 实现浏览器端监控

---

## 开源目的

本项目旨在提供一个 **开箱即用的工厂移动机器人仿真开发基线**:

- **学习参考**: 覆盖 ROS2 从建模到导航到感知的完整技术链路
- **快速原型**: 基于成熟的模块化结构，快速验证新的算法/传感器方案
- **部署模板**: Docker 隔离方案可直接适配到边缘计算设备 (Jetson / NUC)
- **社区共建**: 欢迎提交 Issue / PR，共同完善工业机器人仿真生态

---

## License

MIT License

---

## 致谢

- [ROS 2 Humble](https://docs.ros.org/en/humble/) — 机器人操作系统
- [Gazebo Ignition](https://gazebosim.org/home) — 高保真物理仿真
- [Nav2](https://nav2.docs.getros.org/) — 自主导航框架
- [Ultralytics YOLO](https://docs.ultralytics.com/) — 实时目标检测
- [OSRF Docker Images](https://hub.docker.com/r/osrf/ros/) — 官方 ROS2 基础镜像
