#!/usr/bin/env bash
set -euo pipefail

# Camera-free host with a bounded runtime and stable motor port.
# The host watchdog commands zero base velocity when no client command arrives.
HOST_DURATION_S="${1:-60}"

python -m lerobot.robots.lekiwi.lekiwi_host \
  --robot.id=follower \
  --robot.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF263511-if00 \
  --robot.cameras='{}' \
  --host.connection_time_s="$HOST_DURATION_S" \
  --host.watchdog_timeout_ms=500
