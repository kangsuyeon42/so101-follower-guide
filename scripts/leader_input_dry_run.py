#!/usr/bin/env python3
"""Print calibrated SO-101 leader input without connecting to the follower."""

import argparse
import time

import scservo_sdk as scs

from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


MOTOR_IDS = range(1, 7)
TORQUE_ENABLE_ADDRESS = 40


parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM1")
parser.add_argument("--id", default="leader")
parser.add_argument("--hz", type=float, default=10.0)
args = parser.parse_args()

if args.hz <= 0:
    raise SystemExit("--hz must be greater than zero")

# Inspect torque before SO101Leader.connect() can write any configuration.
port = scs.PortHandler(args.port)
if not port.openPort():
    raise SystemExit(f"Could not open {args.port}")
if not port.setBaudRate(1_000_000):
    port.closePort()
    raise SystemExit("Could not set baud rate to 1000000")

packet = scs.PacketHandler(0)
try:
    torque_states = []
    for motor_id in MOTOR_IDS:
        torque, result, error = packet.read1ByteTxRx(
            port, motor_id, TORQUE_ENABLE_ADDRESS
        )
        if result != scs.COMM_SUCCESS or error != 0:
            raise SystemExit(f"Could not read torque state for motor ID {motor_id}")
        torque_states.append(torque)
finally:
    port.closePort()

if any(torque_states):
    enabled_ids = [
        motor_id for motor_id, enabled in zip(MOTOR_IDS, torque_states, strict=True) if enabled
    ]
    raise SystemExit(f"Leader torque is ON for motor IDs {enabled_ids}; dry-run aborted")

leader = SO101Leader(
    SO101LeaderConfig(port=args.port, id=args.id, use_degrees=True)
)

try:
    leader.connect(calibrate=False)
    print("LEADER INPUT DRY-RUN — follower에는 연결하지 않습니다.")
    print("Ctrl+C: 종료")
    while True:
        action = leader.get_action()
        values = "  ".join(
            f"{name.removesuffix('.pos')}={value:+8.2f}"
            for name, value in action.items()
        )
        print(f"\r{values}", end="", flush=True)
        time.sleep(1.0 / args.hz)
except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    if leader.is_connected:
        leader.disconnect()
    print("Leader 연결 종료")
