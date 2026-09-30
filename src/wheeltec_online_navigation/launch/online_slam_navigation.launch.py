#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wheeltec 在线 SLAM 与 Nav2 一体化启动文件。

该启动流程适用于“不预先建图”的场景：
1. 先启动底盘、传感器、里程计和机器人模型；
2. 再启动 slam_toolbox，实时生成 map 坐标系与地图；
3. 最后启动 Nav2 导航、巡路点节点，并可选启动 RViz。
"""

import os

# 通过包名查找安装后的 share 目录，避免写死绝对路径。
from ament_index_python.packages import get_package_share_directory

# ROS 2 Launch 核心组件：主描述、参数声明、包含其他 launch、延时动作。
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)

# IfCondition 用于根据 launch 参数决定是否启动某个节点。
from launch.conditions import IfCondition

# 允许包含由 Python 编写的子 launch 文件。
from launch.launch_description_sources import PythonLaunchDescriptionSource

# LaunchConfiguration 用来引用命令行或默认的 launch 参数。
from launch.substitutions import LaunchConfiguration

# 声明本文件需要启动的 ROS 2 节点。
from launch_ros.actions import Node


def generate_launch_description():
    """构造并返回完整的在线 SLAM 导航启动描述。"""

    # ==================== 可配置 launch 参数 ====================
    # 是否使用 Gazebo/仿真时钟；实车运行时必须保持 False。
    use_sim_time = LaunchConfiguration('use_sim_time')

    # 是否让 Nav2 生命周期管理器自动 configure/activate 各服务器。
    autostart = LaunchConfiguration('autostart')

    # 是否使用 Nav2 component container 方式启动，实车默认 False。
    use_composition = LaunchConfiguration('use_composition')

    # 是否启动 RViz2；默认 False，需要可视化时传 true。
    start_rviz = LaunchConfiguration('start_rviz')

    # ==================== 各 ROS 2 包的 share 路径 ====================
    # 本包路径：用于定位 slam_toolbox 参数文件。
    online_nav_dir = get_package_share_directory('wheeltec_online_navigation')

    # Wheeltec Nav2 参数和 RViz 配置所在包。
    wheeltec_nav2_dir = get_package_share_directory('wheeltec_nav2')

    # 底盘、IMU、里程计和雷达的启动文件所在包。
    turn_on_dir = get_package_share_directory('turn_on_wheeltec_robot')

    # ROS 2 官方 Nav2 标准启动文件所在包。
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    # ==================== 默认配置文件路径 ====================
    # 在线异步地图模式的 slam_toolbox 参数文件。
    default_slam_params = os.path.join(
        online_nav_dir, 'config', 'slam_toolbox_online_async.yaml')

    # V550_mec 车型对应的 Nav2 控制器、代价地图和规划器参数。
    default_nav_params = os.path.join(
        wheeltec_nav2_dir, 'param', 'wheeltec_params', 'param_V550_mec.yaml')

    # 与当前导航配置匹配的 RViz 可视化配置。
    default_rviz_config = os.path.join(
        wheeltec_nav2_dir, 'rviz', 'wheeltec.rviz')

    # 将参数文件路径也暴露为可直接覆盖的 launch 参数。
    slam_params_file = LaunchConfiguration('slam_params_file')
    nav_params_file = LaunchConfiguration('nav_params_file')
    rviz_config = LaunchConfiguration('rviz_config')

    # ==================== 需要包含的子 launch 文件 ====================
    # 启动底盘串口、IMU、EKF、机器人状态发布器和 URDF。
    turn_on_launch = os.path.join(
        turn_on_dir, 'launch', 'turn_on_wheeltec_robot.launch.py')

    # 启动激光雷达驱动，为在线建图和代价地图提供 /scan。
    lidar_launch = os.path.join(
        turn_on_dir, 'launch', 'wheeltec_lidar.launch.py')

    # 启动 Nav2 的规划器、控制器、行为树和代价地图等标准节点。
    navigation_launch = os.path.join(
        nav2_bringup_dir, 'launch', 'navigation_launch.py')

    # 底盘和传感器必须先启动，SLAM 与 Nav2 才能获得 TF、里程计和激光数据。
    base_and_sensors = [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turn_on_launch)
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(lidar_launch)
        ),
    ]

    # ==================== slam_toolbox 在线建图节点 ====================
    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',

        # 先加载 YAML 参数，再用 launch 参数覆盖仿真时间配置。
        parameters=[
            slam_params_file,
            {'use_sim_time': use_sim_time},
        ],
    )

    # ==================== Nav2 导航节点组 ====================
    # 复用 ROS 2 官方 navigation_launch.py，但替换为 Wheeltec 参数文件。
    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(navigation_launch),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'use_composition': use_composition,
            'params_file': nav_params_file,
        }.items(),
    )

    # 巡路点循环节点：收到 /start_waypoint_cycle 后按路点顺序循环导航。
    waypoint_cycle = Node(
        package='nav2_waypoint_cycle',
        executable='nav2_waypoint_cycle',
        name='waypoint_cycle',
        output='screen',
    )

    # ==================== 可选 RViz2 可视化 ====================
    rviz_node = Node(
        # 只有 start_rviz:=true 时才真正启动 RViz。
        condition=IfCondition(start_rviz),
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # ==================== 启动参数声明与执行顺序 ====================
    return LaunchDescription([
        # 仿真时间开关。实车建议保持 False。
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='False',
            description='Use simulation clock if true'),

        # Nav2 生命周期节点自动启动开关。
        DeclareLaunchArgument(
            'autostart',
            default_value='True',
            description='Automatically configure and activate Nav2 lifecycle nodes'),

        # 是否使用组件容器减少进程数量和通信开销。
        DeclareLaunchArgument(
            'use_composition',
            default_value='False',
            description='Use Nav2 component container composition'),

        # 是否打开 RViz2。
        DeclareLaunchArgument(
            'start_rviz',
            default_value='True',
            description='Start RViz with the Wheeltec navigation configuration'),

        # 允许用户覆盖在线 SLAM 参数文件。
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=default_slam_params,
            description='slam_toolbox parameter file'),

        # 允许用户覆盖 Nav2 参数文件。
        DeclareLaunchArgument(
            'nav_params_file',
            default_value=default_nav_params,
            description='Nav2 parameter file'),

        # 允许用户替换 RViz 配置文件。
        DeclareLaunchArgument(
            'rviz_config',
            default_value=default_rviz_config,
            description='RViz configuration file'),

        # 第一步：立即启动底盘、IMU、里程计、URDF 和激光雷达。
        *base_and_sensors,

        # 第二步：等待 3 秒，让底盘与传感器发布稳定的 TF 和 /scan。
        TimerAction(period=3.0, actions=[slam_node]),

        # 第三步：再等待 8 秒，确认 map->odom 已稳定后启动 Nav2。
        TimerAction(period=8.0, actions=[navigation, waypoint_cycle]),

        # 第四步：按需启动 RViz2。
        rviz_node,
    ])
