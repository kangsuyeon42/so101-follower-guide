#!/usr/bin/env python3
"""Move the leader and follower together to their saved home candidates."""

import argparse
import json
import time
from pathlib import Path

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOOP_HZ = 20
DEFAULT_MAX_JOINT_SPEED_DEG_S = 15.0
DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S = 25.0


def load_target(filename: str) -> dict[str, float]:
    with (PROJECT_DIR / "config" / filename).open() as file:
        return {
            name: float(value)
            for name, value in json.load(file)["position"].items()
        }


def read_torque_state(bus) -> dict[str, int]:
    return {
        name: bus.read("Torque_Enable", name, normalize=False)
        for name in bus.motors
    }


def move_duration(
    start: dict[str, float],
    target: dict[str, float],
    joint_speed: float,
    gripper_speed: float,
) -> float:
    durations = [
        abs(target[name] - start[name])
        / (gripper_speed if name == "gripper" else joint_speed)
        for name in start
    ]
    # Smoothstep peak speed is 1.5 times its average speed.
    return 1.5 * max(0.5, *durations)


parser = argparse.ArgumentParser()
parser.add_argument("--leader-port", default="/dev/ttyACM1")
parser.add_argument("--follower-port", default="/dev/ttyACM0")
parser.add_argument(
    "--joint-speed", type=float, default=DEFAULT_MAX_JOINT_SPEED_DEG_S
)
parser.add_argument(
    "--gripper-speed",
    type=float,
    default=DEFAULT_MAX_GRIPPER_SPEED_PERCENT_S,
)
args = parser.parse_args()

if args.leader_port == args.follower_port:
    parser.error("Leader와 Follower 포트는 서로 달라야 합니다.")
if args.joint_speed <= 0 or args.gripper_speed <= 0:
    parser.error("속도 제한은 0보다 커야 합니다.")
for label, port in (("Leader", args.leader_port), ("Follower", args.follower_port)):
    if not Path(port).exists():
        parser.error(f"{label} 포트를 찾지 못했습니다: {port}")

leader_target = load_target("leader_home_candidate.json")
follower_target = load_target("follower_home_candidate.json")
leader = SO101Leader(
    SO101LeaderConfig(port=args.leader_port, id="leader", use_degrees=True)
)
follower = SO101Follower(
    SO101FollowerConfig(
        port=args.follower_port,
        id="follower",
        use_degrees=True,
        disable_torque_on_disconnect=True,
    )
)
leader_torque_attempted = False
follower_torque_attempted = False

try:
    # Connect only to the buses. This avoids calibration or configuration writes.
    leader.bus.connect()
    follower.bus.connect()

    leader_torque = read_torque_state(leader.bus)
    follower_torque = read_torque_state(follower.bus)
    print("현재 토크 상태:")
    for label, state in (("Leader", leader_torque), ("Follower", follower_torque)):
        print(f"  {label}")
        for name, enabled in state.items():
            print(f"    {name:14s}: {'ON' if enabled else 'OFF'}")
    if any(leader_torque.values()) or any(follower_torque.values()):
        raise SystemExit("이미 토크가 켜진 모터가 있어 홈 이동을 시작하지 않습니다.")

    leader_present = leader.bus.sync_read("Present_Position", num_retry=2)
    follower_present = follower.bus.sync_read("Present_Position", num_retry=2)
    leader_start = {name: float(leader_present[name]) for name in leader.bus.motors}
    follower_start = {
        name: float(follower_present[name]) for name in follower.bus.motors
    }

    for label, start, target in (
        ("Leader", leader_start, leader_target),
        ("Follower", follower_start, follower_target),
    ):
        print(f"\n{label} 현재 위치 -> 홈 후보")
        for name in start:
            unit = "%" if name == "gripper" else "deg"
            print(f"  {name:14s}: {start[name]:+8.3f} -> {target[name]:+8.3f} {unit}")

    duration = max(
        move_duration(
            leader_start, leader_target, args.joint_speed, args.gripper_speed
        ),
        move_duration(
            follower_start, follower_target, args.joint_speed, args.gripper_speed
        ),
    )
    print(
        f"\n속도 제한: 관절 {args.joint_speed:.1f} deg/s, "
        f"그리퍼 {args.gripper_speed:.1f} %/s"
    )
    print(f"동기화된 예상 이동 시간: {duration:.1f}초")
    print("이동 중 Ctrl+C를 누르면 양쪽 토크를 해제하고 종료합니다.")
    input("두 팔 주변과 아래를 비우고 손을 뗀 뒤 ENTER: ")

    # Overwrite retained goals before either arm's torque is enabled.
    leader.bus.sync_write("Goal_Position", leader_start)
    follower.bus.sync_write("Goal_Position", follower_start)
    follower_torque_attempted = True
    follower.bus.enable_torque()
    leader_torque_attempted = True
    leader.bus.enable_torque()
    print("양쪽 토크 ON — 저장된 홈 후보로 함께 이동합니다.")

    start_time = time.monotonic()
    while True:
        progress = min((time.monotonic() - start_time) / duration, 1.0)
        blend = progress * progress * (3.0 - 2.0 * progress)
        leader_goal = {
            name: leader_start[name]
            + (leader_target[name] - leader_start[name]) * blend
            for name in leader_start
        }
        follower_goal = {
            name: follower_start[name]
            + (follower_target[name] - follower_start[name]) * blend
            for name in follower_start
        }
        leader.bus.sync_write("Goal_Position", leader_goal)
        follower.bus.sync_write("Goal_Position", follower_goal)
        print(f"\r진행률 {progress * 100:6.1f}%", end="", flush=True)
        if progress >= 1.0:
            break
        time.sleep(1 / LOOP_HZ)

    print("\n두 팔이 홈 후보 목표에 도착했습니다.")
    time.sleep(0.5)
    for label, bus, target in (
        ("Leader", leader.bus, leader_target),
        ("Follower", follower.bus, follower_target),
    ):
        reached = bus.sync_read("Present_Position", num_retry=2)
        print(f"\n{label} 실제 도착 위치")
        for name in bus.motors:
            value = float(reached[name])
            unit = "%" if name == "gripper" else "deg"
            print(
                f"  {name:14s}: {value:+8.3f} {unit}  "
                f"(오차 {value - target[name]:+.3f})"
            )

    input("\n자세를 확인하고 두 팔을 받을 준비 후 ENTER를 누르면 토크를 해제합니다: ")

except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    for label, bus, torque_attempted in (
        ("Follower", follower.bus, follower_torque_attempted),
        ("Leader", leader.bus, leader_torque_attempted),
    ):
        if bus.is_connected:
            if torque_attempted:
                try:
                    bus.disable_torque(num_retry=2)
                    print(f"{label} 토크 OFF")
                except Exception as error:
                    print(f"경고: {label} 토크 해제 명령 실패: {error}")
            bus.disconnect(disable_torque=False)
    print("양쪽 연결 종료")
