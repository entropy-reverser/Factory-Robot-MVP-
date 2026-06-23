# Factory Robot MVP — 架构设计与模块说明

## 1. 系统总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                      用户交互层 (Host)                          │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  RViz   │  │ Gazebo   │  │ Keyboard │  │ Docker CLI   │  │
│  │ (可视化) │  │ (仿真)   │  │ (遥控)   │  │ (部署管理)    │  │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
└───────┼────────────┼─────────────┼───────────────┼──────────┘
        │            │             │               │
        ▼            ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                    ROS2 Humble (中间件)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  TF2     │  │ Topics   │  │ Actions  │  │ DDS Discovery│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└───────┬────────────┬─────────────┬───────────────┬──────────┘
        │            │             │               │
        ▼            ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                    功能层 (Packages)                            │
│  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │factory_world │  │factory_robot│  │    robot_slam      │  │
│  │  仿真环境    │  │_description │  │  (SLAM + Nav2)     │  │
│  │  SDF / Launch│  │ URDF / Xacro│  │  Config / Launch   │  │
│  └──────────────┘  └────────────┘  └────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              robot_bringup (顶层启动)                │  │
│  │         robot_factory.launch.py                      │  │
│  └──────────────────────────────────────────────────────┘  │
└───────┬────────────┬─────────────┬───────────────────────────┘
        │            │             │
        ▼            ▼             ▼
┌──────────────────────────────────────────────────────────────┐
│                    仿真引擎 (Gazebo Ignition)                   │
│  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │  Physics     │  │  Sensors   │  │  Diff-Drive      │  │
│  │  (碰撞/动力学)│  │  (LiDAR/   │  │  (cmd_vel->odom) │  │
│  │              │  │  Camera)   │  │                  │  │
│  └──────────────┘  └────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 模块职责划分

### 2.1 `factory_world`

- **职责**：提供仿真场景的静态世界描述。
- **关键文件**：
  - `worlds/factory_world.sdf`：厂房、墙壁、货架、立柱、货物箱。
  - `launch/factory_world.launch.py`：启动 `ign gazebo` 并加载 SDF。
- **扩展点**：可在 `models/` 中添加更精细的货架 / 设备模型，并在 SDF 中引用。

### 2.2 `factory_robot_description`

- **职责**：定义机器人本体、传感器、执行器及其物理/仿真属性。
- **关键文件**：
  - `urdf/robot.urdf.xacro`：主描述文件，包含底盘、差速轮、万向轮、扩展安装位。
  - `urdf/sensors/lidar.xacro`：360° 2D 激光雷达，发布 `/scan`。
  - `urdf/sensors/depth_camera.xacro`：RGB-D 相机，发布彩色图与深度图。
  - `urdf/gazebo_plugins.xacro`：Ignition 差速控制插件。
- **扩展点**：
  - 在 `top_mount_link` 下挂载机械臂 xacro。
  - 增加更多传感器（如超声波、IMU）并添加对应 `gazebo` 插件。

### 2.3 `robot_slam`

- **职责**：提供 SLAM 建图与导航配置。
- **关键文件**：
  - `config/slam_toolbox.yaml`：异步在线建图参数。
  - `config/nav2_params.yaml`：Nav2 全局/局部规划、代价地图、AMCL 参数。
  - `launch/slam.launch.py`：启动 `slam_toolbox` + RViz。
  - `launch/navigation.launch.py`：启动 Nav2 bringup + RViz。
- **扩展点**：
  - 将 `mode: mapping` 改为 `mode: localization` 并加载已有地图，实现纯定位。
  - 增加 `map_saver` 自动保存逻辑。

### 2.4 `robot_bringup`

- **职责**：作为顶层入口，协调所有子模块的启动顺序。
- **关键文件**：
  - `launch/robot_factory.launch.py`：一键启动世界 + 机器人 + 桥接 + SLAM。
- **设计原则**：只负责 Include 子 launch，不包含具体业务逻辑，保证可维护性。

---

## 3. 数据流与 Topic 设计

```
┌─────────────────┐       /clock         ┌─────────────────┐
│  Gazebo Ignition│ ◄─────────────────── │  ros_gz_bridge  │
│                 │       /scan          │                 │
│  ┌───────────┐  │ ◄─────────────────── │  ┌───────────┐  │
│  │ 2D LiDAR  │  │       /camera/*      │  │ Sensors   │  │
│  └─────┬─────┘  │ ◄─────────────────── │  └───────────┘  │
│  ┌───────────┐  │                      └────────┬────────┘
│  │ Diff-Drive│  │                               │
│  │ (odom)    │  │                      ┌────────▼────────┐
│  └───────────┘  │                      │  ROS2 Topic Bus │
│  ┌───────────┐  │                      └────────┬────────┘
│  │ RGB-D Cam │  │                               │
│  └───────────┘  │         ┌──────────┬──────────┼──────────┬──────────┐
└─────────────────┘         │          │          │          │          │
                            ▼          ▼          ▼          ▼          ▼
                      ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
                      │slam_toolbox│ │robot_state│ │ Nav2     │ │ YOLO (预留)│
                      │ (建图)   │ │_publisher │ │ (导航)   │ │ (视觉)    │
                      └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 核心 Topic 列表

| Topic | 类型 | 方向 | 说明 |
|-------|------|------|------|
| `/scan` | `sensor_msgs/LaserScan` | Gazebo → ROS2 | 2D 激光扫描数据 |
| `/camera/color/image_raw` | `sensor_msgs/Image` | Gazebo → ROS2 | 彩色图像（YOLO 输入） |
| `/camera/depth/image_raw` | `sensor_msgs/Image` | Gazebo → ROS2 | 深度图像（点云/避障） |
| `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | Gazebo → ROS2 | 相机内参 |
| `/cmd_vel` | `geometry_msgs/Twist` | ROS2 → Gazebo | 机器人速度指令 |
| `/odom` | `nav_msgs/Odometry` | Gazebo → ROS2 | 里程计数据 |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM → ROS2 | 2D 栅格地图 |
| `/tf` | `tf2_msgs/TFMessage` | 双向 | 坐标变换树 |
| `/clock` | `rosgraph_msgs/Clock` | Gazebo → ROS2 | 仿真时间 |

---

## 4. 坐标系设计

```
map (全局地图坐标系，slam_toolbox / Nav2 使用)
  └── odom (里程计坐标系，diff-drive 插件发布)
        └── base_link (机器人本体中心)
              ├── left_wheel_link
              ├── right_wheel_link
              ├── caster_wheel_link
              ├── top_mount_link (机械臂安装位)
              ├── lidar_link (激光雷达)
              └── camera_link (深度相机)
```

---

## 5. 扩展设计原则

### 5.1 传感器扩展

新增传感器时，只需：
1. 在 `urdf/sensors/` 新建 `xxx.xacro`。
2. 在 `robot.urdf.xacro` 中 `<xacro:include>` 并调用宏。
3. 在 `robot_bringup/launch/robot_factory.launch.py` 的 `bridge` 节点中添加对应 topic 桥接规则。

### 5.2 功能扩展（YOLO / 机械臂）

建议在 `src/` 下新建独立功能包，如 `robot_vision`、`robot_manipulation`，保持与现有模块的松耦合：
- `robot_vision` 订阅 `/camera/color/image_raw`，发布 `/detected_objects`。
- `robot_manipulation` 提供 action server，接收抓取目标，调用 MoveIt2 或自定义控制器。

### 5.3 多机扩展

在 `robot_spawn.launch.py` 中增加 `robot_namespace` 参数，通过不同 namespace 和初始位置生成多个机器人，利用 ROS2 DDS 自动发现实现多机通信。

---

## 6. 关键设计决策记录 (ADR)

| 决策 | 方案 | 原因 |
|------|------|------|
| 仿真器选择 | Gazebo Ignition (Fortress) | ROS2 Humble 官方推荐，与 ros_gz 集成成熟 |
| 建图方案 | slam_toolbox async_online | 社区支持好，参数丰富，可无缝切换 localization 模式 |
| 导航方案 | Nav2 bringup | ROS2 标准导航框架，插件化设计，易于替换局部规划器 |
| 传感器仿真 | 纯 Ignition 原生传感器 | 无需额外插件，直接通过 ros_gz_bridge 输出 ROS2 topic |
| 项目结构 | 按功能分包，顶层 bringup | 符合 ROS2 最佳实践，模块间低耦合，方便独立测试 |
