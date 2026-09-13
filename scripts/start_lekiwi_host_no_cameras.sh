#!/usr/bin/env bash
set -euo pipefail

# Camera-free host with a stable motor port. With no argument, use a
# practically unlimited duration and let Ctrl+C end the host. A numeric first
# argument still provides a bounded duration for short tests.
# The host watchdog commands zero base velocity when no client command arrives.
HOST_DURATION_S="${1:-2147483647}"
LEROBOT_PYTHON="/home/moai5/miniforge3/envs/lerobot/bin/python"

if [[ ! -x "$LEROBOT_PYTHON" ]]; then
  echo "LeRobot Python not found or not executable: $LEROBOT_PYTHON" >&2
  exit 1
fi

"$LEROBOT_PYTHON" -m lerobot.robots.lekiwi.lekiwi_host \
  --robot.id=follower \
  --robot.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF219171-if00 \
  --robot.cameras='{}' \
  --host.connection_time_s="$HOST_DURATION_S" \
  --host.watchdog_timeout_ms=500
