#!/usr/bin/env bash
set -eo pipefail

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-10}"
WS=/home/wheeltec/wheeltec_nav

source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"

echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "wheeltec_online_navigation=$(ros2 pkg prefix wheeltec_online_navigation)"
echo "wheeltec_nav2=$(ros2 pkg prefix wheeltec_nav2)"
echo "turn_on_wheeltec_robot=$(ros2 pkg prefix turn_on_wheeltec_robot)"

args=("$@")
has_rviz=0
for a in "$@"; do
  [[ "$a" == start_rviz:=* ]] && has_rviz=1
done
if (( has_rviz == 0 )); then
  args+=(start_rviz:=true)
fi

exec ros2 launch wheeltec_online_navigation online_slam_navigation.launch.py "${args[@]}"
