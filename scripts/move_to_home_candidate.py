#!/usr/bin/env python3
"""Move an SO-101 slowly from its present pose to the saved home candidate."""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
ROBOT_ID = "follower"
LOOP_HZ = 20
DEFAULT_MAX_JOINT_SPEED_DEG_S = 15.0
DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S = 25.0


parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM0")
parser.add_argument(
    "--joint-speed",
    type=float,
    default=DEFAULT_MAX_JOINT_SPEED_DEG_S,
    help="body-joint peak speed limit in deg/s (default: %(default)s)",
)
parser.add_argument(
    "--gripper-speed",
    type=float,
    default=DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S,
    help="gripper peak speed limit in percent/s (default: %(default)s)",
)
args = parser.parse_args()

if args.joint_speed <= 0 or args.gripper_speed <= 0:
    parser.error("속도 제한은 0보다 커야 합니다.")


with HOME_FILE.open() as file:
    home_data = json.load(file)

target = {name: float(value) for name, value in home_data["position"].items()}

robot = SO101Follower(
    SO101FollowerConfig(
        port=args.port,
        id=ROBOT_ID,
        use_degrees=True,
        disable_torque_on_disconnect=True,
    )
)

torque_enabled = False

try:
    if not Path(args.port).exists():
        raise SystemExit(f"모터 포트를 찾지 못했습니다: {args.port}")

    # Connect only to the bus so this script does not start calibration or
    # rewrite the motor configuration.
    robot.bus.connect()
    torque_state = {
        name: robot.bus.read("Torque_Enable", name, normalize=False)
        for name in robot.bus.motors
    }
    print("현재 토크 상태:")
    for name, enabled in torque_state.items():
        print(f"  {name:14s}: {'ON' if enabled else 'OFF'}")
    if any(torque_state.values()):
        raise SystemExit("이미 토크가 켜진 모터가 있어 홈 이동을 시작하지 않습니다.")

    present = robot.bus.sync_read("Present_Position", num_retry=2)
    start = {name: float(present[name]) for name in robot.bus.motors}

    print("현재 위치 -> 홈 후보")
    for name in robot.bus.motors:
        unit = "%" if name == "gripper" else "deg"
        print(f"  {name:14s}: {start[name]:+8.3f} -> {target[name]:+8.3f} {unit}")

    joint_durations = [
        abs(target[name] - start[name]) / args.joint_speed
        for name in robot.bus.motors
        if name != "gripper"
    ]
    gripper_duration = abs(target["gripper"] - start["gripper"]) / args.gripper_speed
    # Smoothstep's peak speed is 1.5 times its average speed, so lengthen the
    # move accordingly to keep the actual peak below the configured limits.
    duration = 1.5 * max(0.5, *joint_durations, gripper_duration)

    print(
        f"\n속도 제한: 몸통 {args.joint_speed:.1f} deg/s, "
        f"그리퍼 {args.gripper_speed:.1f} %/s"
    )
    print(f"예상 이동 시간: {duration:.1f}초")
    print("이동 중 Ctrl+C를 누르면 토크를 해제하고 종료합니다.")
    input("팔 주변과 아래를 비우고, 팔을 받을 준비가 됐다면 ENTER: ")

    # Store the measured position as the goal before enabling torque. This
    # prevents movement toward an old goal retained by a motor.
    robot.bus.sync_write("Goal_Position", start)
    robot.bus.enable_torque()
    torque_enabled = True
    print("토크 ON — 홈 후보로 이동합니다.")

    start_time = time.monotonic()
    while True:
        elapsed = time.monotonic() - start_time
        progress = min(elapsed / duration, 1.0)
        # Smoothstep gives zero velocity at the beginning and end.
        blend = progress * progress * (3.0 - 2.0 * progress)

        goal = {
            name: start[name] + (target[name] - start[name]) * blend
            for name in robot.bus.motors
        }
        robot.bus.sync_write("Goal_Position", goal)

        print(f"\r진행률 {progress * 100:6.1f}%", end="", flush=True)
        if progress >= 1.0:
            break
        time.sleep(1 / LOOP_HZ)

    print("\n홈 후보 목표에 도착했습니다.")
    time.sleep(0.5)
    reached = robot.bus.sync_read("Present_Position", num_retry=2)
    print("실제 도착 위치")
    for name in robot.bus.motors:
        unit = "%" if name == "gripper" else "deg"
        error = float(reached[name]) - target[name]
        print(f"  {name:14s}: {reached[name]:+8.3f} {unit}  (오차 {error:+.3f})")

    input("\n자세를 확인하세요. 팔을 받을 준비 후 ENTER를 누르면 토크를 해제합니다: ")

except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    if robot.bus.is_connected:
        if torque_enabled:
            robot.bus.disable_torque(num_retry=2)
            print("토크 OFF")
        robot.bus.disconnect(disable_torque=False)
    print("연결 종료")
