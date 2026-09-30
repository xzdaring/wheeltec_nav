# 指定构建该 ROS 2 包所需的最低 CMake 版本。
cmake_minimum_required(VERSION 3.5)

# 定义 ROS 2 包名，目录安装路径和构建目标都会引用该名称。
project(wheeltec_online_navigation)

# 该包只安装 launch/config 文件，因此只需使用 ament_cmake 构建系统。
find_package(ament_cmake REQUIRED)

# 将 launch 和 config 目录完整安装到 install/<pkg>/share/<pkg>/ 下。
# 运行 ros2 launch 时，get_package_share_directory() 会从这里查找文件。
install(
  DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

# 注册为 ament 包，并生成环境与资源索引，使 ros2 能发现该包。
ament_package()
