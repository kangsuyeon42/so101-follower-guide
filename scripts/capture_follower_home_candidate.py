#!/usr/bin/env python3
"""Replace the follower home candidate with its current calibrated pose."""

import argparse
import json
from pathlib import Path

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM0")
args = parser.parse_args()

if not Path(args.port).exists():
    raise SystemExit(f"모터 포트를 찾지 못했습니다: {args.port}")

robot = SO101Follower(
    SO101FollowerConfig(
        port=args.port,
        id="follower",
        use_degrees=True,
    )
)

try:
    # Connect only to the calibrated bus. Do not configure motors or enable torque.
    robot.bus.connect()
    torque_state = {
        name: robot.bus.read("Torque_Enable", name, normalize=False)
        for name in robot.bus.motors
    }
    if any(torque_state.values()):
        enabled = [name for name, state in torque_state.items() if state]
        raise SystemExit(f"토크가 ON인 모터가 있어 기록하지 않습니다: {enabled}")

    present = robot.bus.sync_read("Present_Position", num_retry=2)
    position = {name: float(present[name]) for name in robot.bus.motors}
finally:
    if robot.bus.is_connected:
        robot.bus.disconnect(disable_torque=False)

print("현재 자세로 기존 follower 홈 후보를 교체합니다:")
for name, value in position.items():
    unit = "%" if name == "gripper" else "deg"
    print(f"  {name:14s}: {value:+8.3f} {unit}")
input("팔이 안전한 자세이고 위 값이 맞으면 ENTER: ")

payload = {
    "name": "follower_home_candidate",
    "robot_type": "so101_follower",
    "robot_id": "follower",
    "port": args.port,
    "units": {"body_joints": "degrees", "gripper": "percent"},
    "position": position,
}
HOME_FILE.write_text(json.dumps(payload, indent=2) + "\n")
print(f"홈 후보 갱신 완료: {HOME_FILE}")
