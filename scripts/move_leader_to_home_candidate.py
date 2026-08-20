#!/usr/bin/env python3
"""Move the leader to its saved home, then release torque before teleoperation."""

import argparse
import json
import time
from pathlib import Path

from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "leader_home_candidate.json"
LOOP_HZ = 20
DEFAULT_MAX_JOINT_SPEED_DEG_S = 15.0
DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S = 25.0

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM1")
parser.add_argument("--joint-speed", type=float, default=DEFAULT_MAX_JOINT_SPEED_DEG_S)
parser.add_argument(
    "--gripper-speed",
    type=float,
    default=DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S,
)
args = parser.parse_args()

if args.joint_speed <= 0 or args.gripper_speed <= 0:
    parser.error("속도 제한은 0보다 커야 합니다.")
if not Path(args.port).exists():
    raise SystemExit(f"Leader 포트를 찾지 못했습니다: {args.port}")

with HOME_FILE.open() as file:
    target = {
        name: float(value) for name, value in json.load(file)["position"].items()
    }

leader = SO101Leader(
    SO101LeaderConfig(port=args.port, id="leader", use_degrees=True)
)
torque_enable_attempted = False

try:
    # Avoid leader.connect(), which also writes motor configuration.
    leader.bus.connect()
    torque_state = {
        name: leader.bus.read("Torque_Enable", name, normalize=False)
        for name in leader.bus.motors
    }
    print("현재 Leader 토크 상태:")
    for name, enabled in torque_state.items():
        print(f"  {name:14s}: {'ON' if enabled else 'OFF'}")
    if any(torque_state.values()):
        raise SystemExit("이미 토크가 켜진 모터가 있어 홈 이동을 시작하지 않습니다.")

    present = leader.bus.sync_read("Present_Position", num_retry=2)
    start = {name: float(present[name]) for name in leader.bus.motors}

    print("\n현재 위치 -> Leader 홈 후보")
    for name in leader.bus.motors:
        unit = "%" if name == "gripper" else "deg"
        print(f"  {name:14s}: {start[name]:+8.3f} -> {target[name]:+8.3f} {unit}")

    joint_durations = [
        abs(target[name] - start[name]) / args.joint_speed
        for name in leader.bus.motors
        if name != "gripper"
    ]
    gripper_duration = abs(target["gripper"] - start["gripper"]) / args.gripper_speed
    # Smoothstep peak speed is 1.5 times its average speed.
    duration = 1.5 * max(0.5, *joint_durations, gripper_duration)

    print(f"예상 이동 시간: {duration:.1f}초")
    print("이동 중에는 Leader를 잡지 말고, Ctrl+C로 중단할 수 있습니다.")
    input("Leader 주변을 비우고 손을 뗀 뒤 ENTER: ")

    # Prevent motion toward goals retained from an earlier session.
    leader.bus.sync_write("Goal_Position", start)
    torque_enable_attempted = True
    leader.bus.enable_torque()
    print("Leader 토크 ON — 저장된 홈 후보로 이동합니다.")

    start_time = time.monotonic()
    while True:
        elapsed = time.monotonic() - start_time
        progress = min(elapsed / duration, 1.0)
        blend = progress * progress * (3.0 - 2.0 * progress)
        goal = {
            name: start[name] + (target[name] - start[name]) * blend
            for name in leader.bus.motors
        }
        leader.bus.sync_write("Goal_Position", goal)
        print(f"\r진행률 {progress * 100:6.1f}%", end="", flush=True)
        if progress >= 1.0:
            break
        time.sleep(1 / LOOP_HZ)

    print("\nLeader 홈 후보에 도착했습니다.")
    time.sleep(0.5)
    reached = leader.bus.sync_read("Present_Position", num_retry=2)
    for name in leader.bus.motors:
        error = float(reached[name]) - target[name]
        unit = "%" if name == "gripper" else "deg"
        print(f"  {name:14s}: {reached[name]:+8.3f} {unit}  (오차 {error:+.3f})")

    input("자세를 확인하고 팔을 받을 준비 후 ENTER를 누르면 토크를 해제합니다: ")

except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    if leader.bus.is_connected:
        if torque_enable_attempted:
            try:
                leader.bus.disable_torque(num_retry=2)
                print("Leader 토크 OFF")
            except Exception as error:
                print(f"경고: Leader 토크 해제 명령 실패: {error}")
        leader.bus.disconnect(disable_torque=False)
    print("연결 종료")
