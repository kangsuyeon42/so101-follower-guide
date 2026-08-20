#!/usr/bin/env python3
"""Safely test relative three-joint body following from leader to follower."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import scservo_sdk as scs

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
from lerobot.model.kinematics import RobotKinematics


PROJECT_DIR = Path(__file__).resolve().parents[1]
FOLLOWER_HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
LEADER_HOME_FILE = PROJECT_DIR / "config" / "leader_home_candidate.json"
FOLLOWER_CALIBRATION_FILE = (
    Path.home()
    / ".cache/huggingface/lerobot/calibration/robots/so_follower/follower.json"
)
URDF_FILE = Path.home() / "SO-ARM100/Simulation/SO101/so101_new_calib.urdf"
BODY_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex"]
ALL_JOINTS = BODY_JOINTS + ["wrist_flex", "wrist_roll", "gripper"]
MOTOR_IDS = range(1, 7)
LOOP_HZ = 20
MAX_FOLLOWER_HOME_ERROR_DEG = 3.0
MAX_LEADER_HOME_ERROR_DEG = 5.0
MAX_LEADER_OFFSET_DEG = 2.0
MAX_FOLLOWER_SPEED_DEG_S = 1.0
GOAL_SEND_THRESHOLD_DEG = 0.15
FOLLOWING_ESTOP_ERROR_DEG = 5.0
FOLLOWING_ESTOP_TIMEOUT_S = 0.25
SOFT_FLOOR_Z_M = -0.0332
JOINT_LIMIT_MARGIN_DEG = 3.0


parser = argparse.ArgumentParser()
parser.add_argument("--leader-port", default="/dev/ttyACM1")
parser.add_argument("--follower-port", default="/dev/ttyACM0")
parser.add_argument("--mode", choices=["body", "full", "teleop"], default="body")
args = parser.parse_args()

tracked_joints = BODY_JOINTS if args.mode == "body" else ALL_JOINTS


def unit_for(joint: str) -> str:
    return "%" if joint == "gripper" else "deg"


def max_offset_for(joint: str) -> float:
    if args.mode == "body":
        return 2.0
    if args.mode == "full":
        return 10.0 if joint == "gripper" else 3.0
    return 100.0 if joint == "gripper" else 180.0


def max_speed_for(joint: str) -> float:
    if args.mode == "body":
        return MAX_FOLLOWER_SPEED_DEG_S
    if args.mode == "full":
        return 5.0 if joint == "gripper" else 2.0
    return 60.0 if joint == "gripper" else 30.0


def send_threshold_for(joint: str) -> float:
    return 0.3 if joint == "gripper" else GOAL_SEND_THRESHOLD_DEG


def estop_error_for(joint: str) -> float:
    if args.mode == "teleop":
        return 25.0 if joint == "gripper" else 20.0
    return 10.0 if joint == "gripper" else FOLLOWING_ESTOP_ERROR_DEG

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
    print(
        f"{arm_name} torque:",
        " ".join(f"ID{i}={'ON' if v else 'OFF'}" for i, v in torque_states.items()),
    )
    if any(torque_states.values()):
        raise SystemExit(f"{arm_name} 토크가 이미 켜져 있어 시험을 중단합니다.")

time.sleep(0.5)

with FOLLOWER_HOME_FILE.open() as file:
    follower_home = json.load(file)["position"]
with LEADER_HOME_FILE.open() as file:
    leader_home = json.load(file)["position"]

kinematics = None
joint_lower = None
joint_upper = None
if args.mode == "teleop":
    with FOLLOWER_CALIBRATION_FILE.open() as file:
        follower_calibration = json.load(file)
    lower = []
    upper = []
    for name in ALL_JOINTS[:-1]:
        entry = follower_calibration[name]
        half_range_deg = (entry["range_max"] - entry["range_min"]) * 180.0 / 4095.0
        lower.append(-half_range_deg + JOINT_LIMIT_MARGIN_DEG)
        upper.append(+half_range_deg - JOINT_LIMIT_MARGIN_DEG)
    joint_lower = np.array(lower)
    joint_upper = np.array(upper)
    kinematics = RobotKinematics(
        urdf_path=str(URDF_FILE),
        target_frame_name="gripper_frame_link",
        joint_names=ALL_JOINTS[:-1],
    )

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
    connect_bus_with_retry(leader.bus, "Leader")
    connect_bus_with_retry(follower.bus, "Follower")

    follower_present = follower.bus.sync_read("Present_Position", num_retry=2)
    follower_home_errors = {
        name: abs(float(follower_present[name]) - float(follower_home[name]))
        for name in tracked_joints
    }
    if max(follower_home_errors.values()) > MAX_FOLLOWER_HOME_ERROR_DEG:
        print("Follower가 홈 후보에서 너무 멀어 시험을 시작하지 않습니다.")
        for name, error in follower_home_errors.items():
            print(f"  {name:14s}: 홈과 {error:.2f} deg 차이")
        raise SystemExit("먼저 follower를 기존 홈 후보로 복귀시키세요.")

    leader_action = leader.get_action()
    leader_start = {
        name: float(leader_action[f"{name}.pos"]) for name in tracked_joints
    }
    if args.mode != "teleop":
        leader_home_errors = {
            name: abs(leader_start[name] - float(leader_home[name]))
            for name in tracked_joints
        }
        if max(leader_home_errors.values()) > MAX_LEADER_HOME_ERROR_DEG:
            print("Leader가 저장된 홈 후보에서 너무 멉니다.")
            for name, error in leader_home_errors.items():
                print(f"  {name:14s}: 홈과 {error:.2f} deg 차이")
            raise SystemExit("Leader를 손으로 저장된 홈 근처에 맞추세요.")

    follower_start = {
        name: float(follower_present[name]) for name in tracked_joints
    }
    operational_lower = joint_lower
    operational_upper = joint_upper
    if args.mode == "teleop":
        start_joints = np.array(
            [follower_start[name] for name in ALL_JOINTS[:-1]], dtype=float
        )
        # A manually verified start pose may already be inside the configured
        # joint-limit margin. Permit motion away from that pose toward the safe
        # interior, but never permit movement farther toward the endpoint.
        # Teleoperation uses the full recorded calibration range. The 3-degree
        # test margin is removed; only the actual recorded endpoints remain.
        calibration_lower = joint_lower - JOINT_LIMIT_MARGIN_DEG
        calibration_upper = joint_upper + JOINT_LIMIT_MARGIN_DEG
        operational_lower = np.minimum(calibration_lower, start_joints)
        operational_upper = np.maximum(calibration_upper, start_joints)
    follower_goal = dict(follower_start)
    last_sent_goal = dict(follower_start)
    hold_goal = {
        name: float(follower_present[name]) for name in follower.bus.motors
    }

    test_name = {
        "body": "몸통 3축",
        "full": "6축 통합",
        "teleop": "6축 텔레오퍼레이션",
    }[args.mode]
    print(f"\n{test_name} 상대 추종 시험")
    for name in tracked_joints:
        print(
            f"  {name:14s}: leader {leader_start[name]:+7.2f} {unit_for(name)}, "
            f"follower {follower_start[name]:+7.2f} {unit_for(name)}"
        )
    if args.mode == "body":
        print("  Leader 이동 허용: 각 시작점 기준 ±2.0 deg")
        print("  Follower 속도: 관절별 최대 1.0 deg/s")
        print("  손목과 그리퍼: 시작 위치 고정")
    elif args.mode == "full":
        print("  이동 허용: 몸통/손목 ±3.0 deg, 그리퍼 ±10.0 %")
        print("  Follower 속도: 몸통/손목 2.0 deg/s, 그리퍼 5.0 %/s")
    else:
        print("  홈 기준 별도 소프트 이동 범위 제한 없음")
        print("  Follower 속도: 몸통/손목 30.0 deg/s, 그리퍼 60.0 %/s")
        print(f"  소프트 바닥: URDF base z={SOFT_FLOOR_Z_M * 1000:.1f} mm")
    print("  Ctrl+C: follower 토크 해제 후 종료")
    input("두 팔 주변을 비우고 follower를 받을 준비 후 ENTER: ")

    follower.bus.sync_write("Goal_Position", hold_goal)
    follower_torque_enable_attempted = True
    follower.bus.enable_torque()
    print(f"Follower 토크 ON — {test_name} 상대 이동을 추종합니다.")

    last_time = time.monotonic()
    last_feedback_time = 0.0
    excessive_error_since = {name: None for name in tracked_joints}
    following_errors = {name: 0.0 for name in tracked_joints}

    while True:
        now = time.monotonic()
        dt = min(now - last_time, 0.1)
        last_time = now

        action = leader.get_action()
        proposed_goal = dict(follower_goal)
        for name in tracked_joints:
            leader_position = float(action[f"{name}.pos"])
            offset = float(
                np.clip(
                    leader_position - leader_start[name],
                    -max_offset_for(name),
                    max_offset_for(name),
                )
            )
            if args.mode == "teleop" and name == "gripper":
                # This leader physically closes at a calibrated value near 30%.
                # Map that saved closed/home value to follower 0%, and 100% to
                # follower 100%, so starting closed is not treated as zero motion.
                leader_closed = float(leader_home["gripper"])
                denominator = max(1e-6, 100.0 - leader_closed)
                requested_goal = (
                    (leader_position - leader_closed) * 100.0 / denominator
                )
            else:
                requested_goal = follower_start[name] + offset
            max_step = max_speed_for(name) * dt
            proposed_goal[name] += float(
                np.clip(
                    requested_goal - proposed_goal[name],
                    -max_step,
                    max_step,
                )
            )
            if name == "gripper":
                proposed_goal[name] = float(np.clip(proposed_goal[name], 0.0, 100.0))

        if args.mode == "teleop":
            proposed_joints = np.array(
                [proposed_goal[name] for name in ALL_JOINTS[:-1]], dtype=float
            )
            # Clamp only the joint that reaches its directional limit. Do not
            # reject unrelated joints in the same control frame.
            proposed_joints = np.clip(
                proposed_joints, operational_lower, operational_upper
            )
            for name, value in zip(
                ALL_JOINTS[:-1], proposed_joints, strict=True
            ):
                proposed_goal[name] = float(value)
            proposed_pose = kinematics.forward_kinematics(proposed_joints)
            above_floor = bool(proposed_pose[2, 3] >= SOFT_FLOOR_Z_M)
            if not above_floor:
                # Keep axes that cannot lower the end effector responsive.
                # Revert only the pitch-chain joints responsible for z.
                for name in ("shoulder_lift", "elbow_flex", "wrist_flex"):
                    proposed_goal[name] = follower_goal[name]
                proposed_joints = np.array(
                    [proposed_goal[name] for name in ALL_JOINTS[:-1]], dtype=float
                )
                proposed_pose = kinematics.forward_kinematics(proposed_joints)
                above_floor = bool(proposed_pose[2, 3] >= SOFT_FLOOR_Z_M)
            if above_floor:
                follower_goal = proposed_goal
        else:
            follower_goal = proposed_goal

        goals_to_send = {
            name: follower_goal[name]
            for name in tracked_joints
            if abs(follower_goal[name] - last_sent_goal[name])
            >= send_threshold_for(name)
        }
        if goals_to_send:
            follower.bus.sync_write("Goal_Position", goals_to_send)
            last_sent_goal.update(goals_to_send)

        if now - last_feedback_time >= 0.25:
            actual = follower.bus.sync_read("Present_Position", num_retry=2)
            for name in tracked_joints:
                error = abs(float(actual[name]) - follower_goal[name])
                following_errors[name] = error
                if error > estop_error_for(name):
                    if excessive_error_since[name] is None:
                        excessive_error_since[name] = now
                    elif (
                        now - excessive_error_since[name]
                        >= FOLLOWING_ESTOP_TIMEOUT_S
                    ):
                        raise SystemExit(
                            f"{name} 추종 오차가 {error:.2f} "
                            f"{unit_for(name)}로 지속되어 E-stop"
                        )
                else:
                    excessive_error_since[name] = None
            last_feedback_time = now

        status = "  ".join(
            f"{name}={follower_goal[name]:+6.2f}/{following_errors[name]:4.2f}"
            for name in tracked_joints
        )
        print(f"\r{status}", end="", flush=True)
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
