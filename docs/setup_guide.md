# Factory Robot MVP — 环境搭建与运行指南

## 一、宿主机环境要求

- **OS**: Ubuntu 22.04 (Jammy) 或在 WSL2 下运行
- **ROS2**: Humble Hawksbill
- **Gazebo**: Ignition (Fortress)
- **Docker**: Docker Engine + Docker Compose（可选，推荐用于部署）

---

## 二、原生 Linux / WSL2 环境搭建

### 2.1 安装 ROS2 Humble

按 [ROS2 官方文档](https://docs.ros.org/en/humble/Installation.html) 完成安装，确保 `ros-humble-desktop` 已安装。

```bash
sudo apt update && sudo apt install -y ros-humble-desktop
```

### 2.2 安装 Gazebo Ignition (Fortress)

```bash
sudo apt install -y ignition-fortress
```

验证安装：

```bash
ign gazebo --version
```

### 2.3 安装 ROS2 相关功能包

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
  ros-humble-teleop-twist-keyboard
```

### 2.4 创建工作空间并编译

假设项目已解压到 `~/factory_robot_mvp`：

```bash
cd ~/factory_robot_mvp
rosdep install --from-paths src --ignore-src -y
colcon build --symlink-install
source install/setup.bash
```

> **提示**：`--symlink-install` 允许修改 Python launch 文件后无需重新编译。

---

## 三、运行步骤

### 3.1 一键启动（推荐）

在一个终端中执行：

```bash
ros2 launch robot_bringup robot_factory.launch.py
```

这将自动：
1. 启动 Gazebo Ignition 并加载 `factory_world.sdf`
2. 生成机器人实体
3. 启动 `ros_gz_bridge` 桥接 `/scan`、`/camera/*`、`/clock`
4. 启动 `slam_toolbox` 在线建图
5. 启动 RViz 可视化

### 3.2 分步启动（调试时使用）

**终端 1 — 启动仿真世界：**

```bash
ros2 launch factory_world factory_world.launch.py
```

**终端 2 — 生成机器人：**

```bash
ros2 launch factory_robot_description robot_spawn.launch.py
```

**终端 3 — 启动 SLAM + RViz：**

```bash
ros2 launch robot_slam slam.launch.py
```

**终端 4 — 键盘遥控（可选）：**

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

使用 `i` 前进，`k` 停止，`,` 后退，`j` 左转，`l` 右转。

---

## 四、建图与保存

在 RViz 中观察 `/map` 话题，随着机器人移动，地图会逐渐填充。

当地图完成覆盖后，保存地图：

```bash
ros2 run nav2_map_server map_saver_cli -f ~/factory_robot_mvp/src/robot_slam/maps/factory_map
```

这将生成两个文件：
- `factory_map.pgm`  —  地图灰度图像
- `factory_map.yaml`  —  地图元数据（分辨率、原点等）

---

## 五、导航运行（需先建图）

确保已保存地图后，启动导航：

```bash
ros2 launch robot_slam navigation.launch.py map:=~/factory_robot_mvp/src/robot_slam/maps/factory_map.yaml
```

在 RViz 中：
1. 点击 **"2D Pose Estimate"** 按钮，在地图上大致标注机器人初始位置。
2. 点击 **"Nav2 Goal"** 按钮，在地图上选择目标点与朝向。

Nav2 将自动规划全局路径并控制机器人移动到目标点。

---

## 六、Docker 部署（推荐用于隔离环境）

### 6.1 前提条件

- Docker Engine 已安装
- Docker Compose 已安装
- X11 转发已配置（用于在宿主机显示 Gazebo / RViz GUI）

### 6.2 允许 Docker 访问 X11

```bash
xhost +local:docker
```

### 6.3 构建并运行

```bash
cd ~/factory_robot_mvp/docker
docker-compose up --build
```

首次构建会下载基础镜像并编译工作空间，耗时约 10-20 分钟。

### 6.4 进入运行中的容器

```bash
docker-compose exec factory-robot bash
```

在容器内可以执行任意 ROS2 命令：

```bash
ros2 topic list
ros2 launch robot_bringup robot_factory.launch.py
```

### 6.5 停止容器

```bash
docker-compose down
```

---

## 七、常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| Gazebo 黑屏 | GPU 渲染问题 | 设置 `LIBGL_ALWAYS_SOFTWARE=1` 强制软件渲染 |
| `/scan` 无数据 | 桥接未启动 | 检查 `ros_gz_bridge` 是否运行；确认 `lidar.xacro` 中 topic 为 `scan` |
| 机器人无法移动 | 差速控制插件未加载 | 检查 `gazebo_plugins.xacro` 中 diff-drive 插件配置；确认 `cmd_vel` 有数据 |
| slam_toolbox 崩溃 | 缺少 `map` 或 `odom` frame | 确保 `robot_state_publisher` 正常运行，TF 树完整 |
| Nav2 无法接收目标 | 未定位 | 在 RViz 中先使用 "2D Pose Estimate" 给定初始位姿 |

---

## 八、后续扩展步骤

1. **YOLO 视觉识别**：安装 `yolov8_ros` 或自定义 vision 包，订阅 `/camera/color/image_raw`，运行目标检测节点。
2. **机械臂抓取**：在 `robot.urdf.xacro` 的 `top_mount_link` 下挂载机械臂 xacro，配置 `ign_ros2_control` 关节控制器，结合 MoveIt2 或自定义 action 实现抓取。
