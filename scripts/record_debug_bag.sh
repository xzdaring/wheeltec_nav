#!/usr/bin/env bash
set -Eeuo pipefail

WS="${WHEELTEC_WS:-/home/wheeltec/wheeltec_nav}"
BAG_ROOT="${WHEELTEC_BAG_DIR:-${WS}/bags}"
QOS_OVERRIDES="${WS}/scripts/rosbag_qos_overrides.yaml"
BAG_NAME="wheeltec_debug_$(date +%Y%m%d_%H%M%S)"
DURATION=""
COMPRESS=0
EXTRA_TOPICS="${WHEELTEC_EXTRA_TOPICS:-}"

usage() {
  cat <<'USAGE'
Usage:
  ./record_debug_bag.sh [options]

Options:
  --name NAME        Bag directory name (default: wheeltec_debug_YYYYmmdd_HHMMSS)
  --duration TIME    Stop automatically, e.g. 30s, 2m, 1h
  --out-root DIR     Bag root directory (default: /home/wheeltec/wheeltec_nav/bags)
  --compress         Use file-level zstd compression (more CPU load)
  -h, --help         Show this help

Examples:
  ./record_debug_bag.sh
  ./record_debug_bag.sh --duration 60s
  ./record_debug_bag.sh --name corridor_test_01

Environment:
  WHEELTEC_EXTRA_TOPICS  Extra space-separated topics, e.g. "/camera/image_raw"
USAGE
}

while (($#)); do
  case "$1" in
    --name)
      BAG_NAME="${2:?missing value for --name}"
      shift 2
      ;;
    --duration)
      DURATION="${2:?missing value for --duration}"
      shift 2
      ;;
    --out-root)
      BAG_ROOT="${2:?missing value for --out-root}"
      shift 2
      ;;
    --compress)
      COMPRESS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$BAG_NAME" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Invalid bag name: $BAG_NAME" >&2
  echo "Only letters, numbers, dot, underscore and hyphen are allowed." >&2
  exit 2
fi

if [[ ! -f "$WS/install/setup.bash" ]]; then
  echo "Workspace setup not found: $WS/install/setup.bash" >&2
  exit 1
fi

# ROS setup scripts are not compatible with nounset on all installations.
set +u
source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"
set -u

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 command not found after sourcing $WS/install/setup.bash" >&2
  exit 1
fi

mkdir -p "$BAG_ROOT"
BAG_PATH="$BAG_ROOT/$BAG_NAME"

if [[ -e "$BAG_PATH" ]]; then
  echo "Bag path already exists: $BAG_PATH" >&2
  exit 1
fi

TOPICS=(
  /scan
  /tf
  /tf_static
  /odom
  /odom_combined
  /imu/data_raw
  /imu/data
  /joint_states
  /robot_description
  /cmd_vel
  /red_vel
  /goal_pose
  /initialpose
  /pose
  /set_pose
  /map
  /map_metadata
  /local_costmap/costmap
  /local_costmap/costmap_raw
  /local_costmap/costmap_updates
  /local_costmap/footprint
  /local_costmap/published_footprint
  /local_costmap/clearing_endpoints
  /global_costmap/costmap
  /global_costmap/costmap_raw
  /global_costmap/costmap_updates
  /global_costmap/footprint
  /global_costmap/published_footprint
  /plan
  /plan_smoothed
  /transformed_global_plan
  /path_point
  /trajectories
  /behavior_tree_log
  /navigate_to_pose/_action/feedback
  /navigate_to_pose/_action/status
  /navigate_through_poses/_action/feedback
  /navigate_through_poses/_action/status
  /follow_waypoints/_action/feedback
  /follow_waypoints/_action/status
  /follow_path/_action/feedback
  /follow_path/_action/status
  /spin/_action/feedback
  /spin/_action/status
  /backup/_action/feedback
  /backup/_action/status
  /compute_path_to_pose/_action/feedback
  /compute_path_to_pose/_action/status
  /diagnostics
  /rosout
  /PowerVoltage
  /robot_charging_flag
  /robot_recharge_flag
  /robot_red_flag
  /speed_limit
  /lslidar_order
  /slam_toolbox/scan_visualization
)

if [[ -n "${EXTRA_TOPICS//[[:space:]]/}" ]]; then
  read -r -a EXTRA_ARRAY <<<"$EXTRA_TOPICS"
  TOPICS+=("${EXTRA_ARRAY[@]}")
fi

RECORD_CMD=(ros2 bag record --output "$BAG_PATH" --storage sqlite3 --include-hidden-topics)
if [[ -f "$QOS_OVERRIDES" ]]; then
  RECORD_CMD+=(--qos-profile-overrides-path "$QOS_OVERRIDES")
fi
if (( COMPRESS )); then
  RECORD_CMD+=(--compression-mode file --compression-format zstd)
fi
RECORD_CMD+=("${TOPICS[@]}")

echo "============================================================"
echo "Wheeltec debug rosbag"
echo "Workspace : $WS"
echo "Bag path  : $BAG_PATH"
echo "Topics    : ${#TOPICS[@]}"
echo "Mode      : $([[ -n "$DURATION" ]] && echo "auto stop after $DURATION" || echo 'Ctrl-C to stop')"
echo "============================================================"
df -h "$BAG_ROOT" | tail -1
echo
printf 'Command: '
printf '%q ' "${RECORD_CMD[@]}"
printf '\n\n'

set +e
if [[ -n "$DURATION" ]]; then
  timeout --foreground --signal=INT --kill-after=15s "$DURATION" "${RECORD_CMD[@]}"
  rc=$?
else
  "${RECORD_CMD[@]}"
  rc=$?
fi
set -e

# 124 is timeout's normal indication, 130 is Ctrl-C.
if (( rc != 0 && rc != 124 && rc != 130 )); then
  echo "rosbag record failed with exit code $rc" >&2
  exit "$rc"
fi

echo
echo "Recording finished: $BAG_PATH"
if [[ -f "$BAG_PATH/metadata.yaml" ]]; then
  ros2 bag info "$BAG_PATH" || true
else
  echo "Warning: metadata.yaml was not produced." >&2
  exit 1
fi
