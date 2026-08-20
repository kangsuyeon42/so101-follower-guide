#!/usr/bin/env python3
"""Safely test relative single-joint following from leader to follower."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import scservo_sdk as scs

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]
SUPPORTED_JOINTS = ["shoulder_pan", "wrist_flex", "wrist_roll", "gripper"]
MOTOR_IDS = range(1, 7)
LOOP_HZ = 20
MAX_HOME_ERROR_DEG = 3.0
MAX_LEADER_OFFSET_DEG = 2.0
MAX_FOLLOWER_SPEED_DEG_S = 1.0
GOAL_SEND_THRESHOLD_DEG = 0.15
FOLLOWING_ESTOP_ERROR_DEG = 5.0
MAX_GRIPPER_OFFSET_PERCENT = 5.0
MAX_GRIPPER_SPEED_PERCENT_S = 3.0
GRIPPER_GOAL_SEND_THRESHOLD_PERCENT = 0.3
GRIPPER_ESTOP_ERROR_PERCENT = 10.0
FOLLOWING_ESTOP_TIMEOUT_S = 0.25


parser = argparse.ArgumentParser()
parser.add_argument("--leader-port", default="/dev/ttyACM1")
parser.add_argument("--follower-port", default="/dev/ttyACM0")
parser.add_argument("--joint", choices=SUPPORTED_JOINTS, default="shoulder_pan")
args = parser.parse_args()

if args.leader_port == args.follower_port:
    raise SystemExit("Leader와 follower 포트는 서로 달라야 합니다.")


def read_torque_states(port_name: str) -> dict[int, int]:
    port = scs.PortHandler(port_name)
    if not port.openPort():
        raise SystemExit(f"포트를 열 수 없습니다: {port_name}")
    if not port.setBaudRate(1_000_000):
        port.closePort()
        raise SystemExit(f"baudrate 설정 실패: {port_name}")
    packet = scs.PacketHandler(0)
    try:
        states = {}
        for motor_id in MOTOR_IDS:
            torque, result, error = packet.read1ByteTxRx(port, motor_id, 40)
            if result != scs.COMM_SUCCESS or error != 0:
                raise SystemExit(
                    f"{port_name} motor ID {motor_id} 토크 상태 읽기 실패"
                )
            states[motor_id] = torque
        return states
    finally:
        port.closePort()


def connect_bus_with_retry(bus, arm_name: str, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            bus.connect()
            return
        except Exception as error:
            if bus.is_connected:
                bus.disconnect(disable_torque=False)
            if "Input voltage error" in str(error):
                raise SystemExit(
                    f"{arm_name} 모터가 입력 전압 오류를 보고했습니다. "
                    "전원과 케이블을 점검한 뒤 다시 확인하세요."
                ) from error
            if attempt == attempts:
                raise
            print(f"{arm_name} 연결 확인 재시도 {attempt}/{attempts}: {error}")
            time.sleep(0.5)


for arm_name, port_name in (
    ("leader", args.leader_port),
    ("follower", args.follower_port),
):
    if not Path(port_name).exists():
        raise SystemExit(f"{arm_name} 포트를 찾지 못했습니다: {port_name}")
    torque_states = read_torque_states(port_name)
    print(f"{arm_name} torque:", " ".join(f"ID{i}={'ON' if v else 'OFF'}" for i, v in torque_states.items()))
    if any(torque_states.values()):
        raise SystemExit(f"{arm_name} 토크가 이미 켜져 있어 시험을 중단합니다.")

# Give both USB serial adapters time to settle after the SDK checks close them.
time.sleep(0.5)

with HOME_FILE.open() as file:
    saved_home = json.load(file)["position"]

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
follower_torque_enable_attempted = False

try:
    # Read directly from the calibrated bus. SO101Leader.connect() also calls
    # configure(), which writes motor settings that this test does not need.
    connect_bus_with_retry(leader.bus, "Leader")
    connect_bus_with_retry(follower.bus, "Follower")

    present = follower.bus.sync_read("Present_Position", num_retry=2)
    home_error = np.array(
        [abs(float(present[name]) - float(saved_home[name])) for name in JOINT_NAMES]
    )
    if float(np.max(home_error)) > MAX_HOME_ERROR_DEG:
        print("Follower가 홈 후보에서 너무 멀어 시험을 시작하지 않습니다.")
        for name, error in zip(JOINT_NAMES, home_error, strict=True):
            print(f"  {name:14s}: 홈과 {error:.2f} deg 차이")
        raise SystemExit("먼저 follower를 기존 홈 후보로 복귀시키세요.")

    joint = args.joint
    is_gripper = joint == "gripper"
    unit = "%" if is_gripper else "deg"
    max_leader_offset = (
        MAX_GRIPPER_OFFSET_PERCENT if is_gripper else MAX_LEADER_OFFSET_DEG
    )
    max_follower_speed = (
        MAX_GRIPPER_SPEED_PERCENT_S if is_gripper else MAX_FOLLOWER_SPEED_DEG_S
    )
    goal_send_threshold = (
        GRIPPER_GOAL_SEND_THRESHOLD_PERCENT
        if is_gripper
        else GOAL_SEND_THRESHOLD_DEG
    )
    following_estop_error = (
        GRIPPER_ESTOP_ERROR_PERCENT if is_gripper else FOLLOWING_ESTOP_ERROR_DEG
    )
    leader_start = float(leader.get_action()[f"{joint}.pos"])
    follower_start = float(present[joint])
    follower_goal = follower_start
    last_sent_goal = follower_start
    hold_goal = {name: float(present[name]) for name in follower.bus.motors}

    print(f"\n{joint} 단일 관절 상대 추종 시험")
    print(f"  leader 시작값:   {leader_start:+.2f} {unit}")
    print(f"  follower 시작값: {follower_start:+.2f} {unit}")
    print(f"  leader 이동 허용: 시작점 기준 ±{max_leader_offset:.1f} {unit}")
    print(f"  follower 속도:   최대 {max_follower_speed:.1f} {unit}/s")
    print("  Ctrl+C: follower 토크 해제 후 종료")
    input("두 팔 주변을 비우고 follower를 받을 준비 후 ENTER: ")

    # Prevent motion toward a stale goal when follower torque is enabled.
    follower.bus.sync_write("Goal_Position", hold_goal)
    # Set this before the per-motor operation starts: if enabling one of the
    # later motors fails, finally must still switch every motor back off.
    follower_torque_enable_attempted = True
    follower.bus.enable_torque()
    print(f"Follower 토크 ON — {joint}만 leader 상대 이동을 추종합니다.")

    last_time = time.monotonic()
    last_feedback_time = 0.0
    excessive_error_since = None
    while True:
        now = time.monotonic()
        dt = min(now - last_time, 0.1)
        last_time = now

        leader_position = float(leader.get_action()[f"{joint}.pos"])
        leader_offset = leader_position - leader_start
        clipped_offset = float(
            np.clip(leader_offset, -max_leader_offset, max_leader_offset)
        )
        requested_goal = follower_start + clipped_offset
        max_step = max_follower_speed * dt
        follower_goal += float(
            np.clip(requested_goal - follower_goal, -max_step, max_step)
        )

        if abs(follower_goal - last_sent_goal) >= goal_send_threshold:
            follower.bus.write("Goal_Position", joint, follower_goal)
            last_sent_goal = follower_goal

        following_error = 0.0
        if now - last_feedback_time >= 0.25:
            actual = float(
                follower.bus.read("Present_Position", joint, num_retry=2)
            )
            following_error = abs(actual - follower_goal)
            if following_error > following_estop_error:
                if excessive_error_since is None:
                    excessive_error_since = now
                elif now - excessive_error_since >= FOLLOWING_ESTOP_TIMEOUT_S:
                    raise SystemExit(
                        f"추종 오차가 {following_error:.2f} {unit}로 지속되어 E-stop"
                    )
            else:
                excessive_error_since = None
            last_feedback_time = now

        print(
            f"\rleader={leader_position:+7.2f}  offset={leader_offset:+6.2f}  "
            f"goal={follower_goal:+7.2f}  follow={following_error:5.2f}",
            end="",
            flush=True,
        )
        time.sleep(max(0.0, 1 / LOOP_HZ - (time.monotonic() - now)))

except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    if follower.bus.is_connected:
        if follower_torque_enable_attempted:
            try:
                follower.bus.disable_torque(num_retry=2)
                print("Follower 토크 OFF")
            except Exception as error:
                print(f"경고: follower 토크 해제 명령 실패: {error}")
        follower.bus.disconnect(disable_torque=False)
    if leader.is_connected:
        leader.bus.disconnect(disable_torque=False)
    print("연결 종료")
