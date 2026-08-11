#!/usr/bin/env python3
"""Very small real-hardware Cartesian XYZ test for an SO-101."""

import json
import time
from pathlib import Path

import numpy as np
import pygame

from lerobot.model.kinematics import RobotKinematics
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


PORT = "/dev/ttyACM0"
ROBOT_ID = "follower"
URDF_FILE = Path.home() / "SO-ARM100" / "Simulation" / "SO101" / "so101_new_calib.urdf"
PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
CALIBRATION_FILE = Path.home() / ".cache/huggingface/lerobot/calibration/robots/so_follower/follower.json"

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]

LEFT_STICK_X = 0
LEFT_STICK_Y = 1
L2_AXIS = 2
R2_AXIS = 5
OPTIONS_BUTTON = 9
CAPTURE_BUTTON = 8  # Share
GRIPPER_CLOSE_BUTTON = 0  # Cross
GRIPPER_OPEN_BUTTON = 1   # Circle
DEADZONE = 0.20
TRIGGER_DEADZONE = 0.05
LOOP_HZ = 20
MAX_SPEED_M_S = 0.025       # 25 mm/s
MAX_XY_OFFSET_M = 0.080     # Start position +/- 80 mm
MAX_Z_UP_OFFSET_M = 0.100   # Start position +100 mm
SOFT_FLOOR_Z_M = -0.0332    # Final floor pose captured with the mounted arm
FLOOR_SLOW_ZONE_M = 0.020   # Slow downward motion within 20 mm of floor
MAX_JOINT_STEP_DEG = 1.0    # Per control frame
MAX_RAW_IK_STEP_DEG = 10.0  # Reject implausible IK solution jumps
MAX_IK_ITERATIONS = 10
MAX_HOME_ERROR_DEG = 8.0
JOINT_LIMIT_MARGIN_DEG = 3.0
FOLLOWING_PAUSE_ERROR_DEG = 12.0
FOLLOWING_RESUME_ERROR_DEG = 6.0
FOLLOWING_ESTOP_ERROR_DEG = 25.0
FOLLOWING_ESTOP_TIMEOUT_S = 1.0
MAX_GRIPPER_OFFSET_PERCENT = 30.0
GRIPPER_SPEED_PERCENT_S = 10.0
INPUT_SMOOTHING_TIME_S = 0.12
WRIST_SPEED_DEG_S = 10.0
WRIST_FLEX_INDEX = JOINT_NAMES.index("wrist_flex")
WRIST_ROLL_INDEX = JOINT_NAMES.index("wrist_roll")


def apply_deadzone(value: float) -> float:
    if abs(value) < DEADZONE:
        return 0.0
    magnitude = (abs(value) - DEADZONE) / (1.0 - DEADZONE)
    return float(np.sign(value) * magnitude)


def trigger_value(value: float) -> float:
    normalized = (value + 1.0) / 2.0
    if normalized < TRIGGER_DEADZONE:
        return 0.0
    return (normalized - TRIGGER_DEADZONE) / (1.0 - TRIGGER_DEADZONE)


with HOME_FILE.open() as file:
    saved_home = json.load(file)["position"]

with CALIBRATION_FILE.open() as file:
    calibration = json.load(file)

joint_lower = []
joint_upper = []
for name in JOINT_NAMES:
    calibrated_range = calibration[name]["range_max"] - calibration[name]["range_min"]
    half_range_deg = calibrated_range * 180.0 / 4095.0
    joint_lower.append(-half_range_deg + JOINT_LIMIT_MARGIN_DEG)
    joint_upper.append(+half_range_deg - JOINT_LIMIT_MARGIN_DEG)
joint_lower = np.array(joint_lower)
joint_upper = np.array(joint_upper)


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    pygame.quit()
    raise SystemExit("게임패드를 찾지 못했습니다.")

gamepad = pygame.joystick.Joystick(0)
gamepad.init()

kinematics = RobotKinematics(
    urdf_path=str(URDF_FILE),
    target_frame_name="gripper_frame_link",
    joint_names=JOINT_NAMES,
)

robot = SO101Follower(
    SO101FollowerConfig(
        port=PORT,
        id=ROBOT_ID,
        use_degrees=True,
        disable_torque_on_disconnect=True,
    )
)

torque_enabled = False

try:
    # Deliberately connect only the motor bus. This avoids calibration prompts
    # and prevents robot.connect() from changing configuration unexpectedly.
    robot.bus.connect()
    present = robot.bus.sync_read("Present_Position", num_retry=2)
    current_joints = np.array([present[name] for name in JOINT_NAMES], dtype=float)
    gripper_position = float(present["gripper"])
    start_gripper_position = gripper_position

    saved_home_joints = np.array([saved_home[name] for name in JOINT_NAMES], dtype=float)
    home_error = np.abs(current_joints - saved_home_joints)
    if np.max(home_error) > MAX_HOME_ERROR_DEG:
        print("홈 후보에서 너무 멀어 실제 제어를 시작하지 않습니다.")
        for name, error in zip(JOINT_NAMES, home_error, strict=True):
            print(f"  {name:14s}: 홈과 {error:.2f} deg 차이")
        raise SystemExit("먼저 move_to_home_candidate.py를 실행하세요.")

    start_pose = kinematics.forward_kinematics(current_joints)
    target_pose = start_pose.copy()

    print("\n현재 자세를 시작점으로 사용합니다.")
    for name in JOINT_NAMES:
        print(f"  {name:14s}: {present[name]:+8.3f} deg")
    print(f"  {'gripper':14s}: {gripper_position:8.3f} %")
    print("\n왼쪽 스틱: 앞뒤/좌우, L2/R2: 아래/위")
    print("방향키 위/아래: 손목 기울기, 왼쪽/오른쪽: 손목 회전")
    print("Cross/Circle: 그리퍼 닫기/열기")
    print("Share: 현재 위치 출력")
    print("x/y 범위: 시작점 기준 +/- 80 mm, z 위쪽: +100 mm")
    print(f"기록된 소프트 바닥 z: {SOFT_FLOOR_Z_M * 1000:.1f} mm")
    print("OPTIONS 또는 Ctrl+C: 즉시 토크 해제 후 종료")
    input("팔 아래를 비우고 전원 차단 준비가 됐다면 ENTER를 누르세요. ")

    # Write the measured pose before torque-on, so enabling torque cannot make
    # the arm jump toward an old goal left in motor memory.
    hold_goal = {name: float(present[name]) for name in robot.bus.motors}
    robot.bus.sync_write("Goal_Position", hold_goal)
    robot.bus.enable_torque()
    torque_enabled = True
    print("토크 ON — 스틱을 놓으면 현재 위치를 유지합니다.")

    last_time = time.monotonic()
    last_print_time = 0.0
    last_feedback_time = 0.0
    following_error = 0.0
    following_error_since = None
    motion_paused = False
    capture_was_pressed = False
    smoothed_xyz_command = np.zeros(3, dtype=float)

    while True:
        pygame.event.pump()

        if not gamepad.get_init():
            print("\n게임패드 연결이 끊겼습니다.")
            break
        if gamepad.get_button(OPTIONS_BUTTON):
            print("\n[ESTOP] OPTIONS 입력 감지")
            break

        capture_pressed = bool(gamepad.get_button(CAPTURE_BUTTON))
        if capture_pressed and not capture_was_pressed:
            captured = robot.bus.sync_read("Present_Position", num_retry=2)
            captured_joints = np.array([captured[name] for name in JOINT_NAMES], dtype=float)
            captured_pose = kinematics.forward_kinematics(captured_joints)
            captured_offset_mm = (captured_pose[:3, 3] - start_pose[:3, 3]) * 1000
            print("\n\n--- POSITION CAPTURE ---")
            print("xyz absolute (m):", np.round(captured_pose[:3, 3], 6))
            print("xyz offset (mm):", np.round(captured_offset_mm, 2))
            for name in JOINT_NAMES:
                print(f"{name:14s}: {captured[name]:+8.3f} deg")
            print(f"{'gripper':14s}: {captured['gripper']:8.3f} %")
            print("--- END CAPTURE ---\n")
        capture_was_pressed = capture_pressed

        now = time.monotonic()
        dt = min(now - last_time, 0.1)
        last_time = now

        xyz_command = np.array(
            [
                -apply_deadzone(gamepad.get_axis(LEFT_STICK_Y)),  # Up: +x
                -apply_deadzone(gamepad.get_axis(LEFT_STICK_X)),  # Left: +y
                trigger_value(gamepad.get_axis(R2_AXIS))
                - trigger_value(gamepad.get_axis(L2_AXIS)),       # R2: +z
            ],
            dtype=float,
        )
        command_norm = np.linalg.norm(xyz_command)
        if command_norm > 1.0:
            xyz_command /= command_norm

        hat_x, hat_y = gamepad.get_hat(0)
        wrist_mode = hat_x != 0 or hat_y != 0
        if motion_paused:
            # Freeze the target and allow the real motors to catch up instead
            # of immediately dropping torque for ordinary transient lag.
            smoothed_xyz_command[:] = 0.0
            wrist_mode = False

        # Exponential smoothing removes abrupt stick and trigger changes while
        # remaining independent of small loop-timing variations.
        smoothing_alpha = 1.0 - np.exp(-dt / INPUT_SMOOTHING_TIME_S)
        smoothed_xyz_command += smoothing_alpha * (xyz_command - smoothed_xyz_command)
        if np.all(xyz_command == 0.0) and np.linalg.norm(smoothed_xyz_command) < 0.02:
            smoothed_xyz_command[:] = 0.0

        if smoothed_xyz_command[2] < 0.0:
            floor_clearance = target_pose[2, 3] - SOFT_FLOOR_Z_M
            floor_speed_scale = float(
                np.clip(floor_clearance / FLOOR_SLOW_ZONE_M, 0.15, 1.0)
            )
            smoothed_xyz_command[2] *= floor_speed_scale

        if not wrist_mode and not motion_paused:
            target_pose[:3, 3] += smoothed_xyz_command * MAX_SPEED_M_S * dt
            target_pose[:2, 3] = np.clip(
                target_pose[:2, 3],
                start_pose[:2, 3] - MAX_XY_OFFSET_M,
                start_pose[:2, 3] + MAX_XY_OFFSET_M,
            )
            target_pose[2, 3] = np.clip(
                target_pose[2, 3],
                SOFT_FLOOR_Z_M,
                start_pose[2, 3] + MAX_Z_UP_OFFSET_M,
            )

        close_pressed = bool(gamepad.get_button(GRIPPER_CLOSE_BUTTON))
        open_pressed = bool(gamepad.get_button(GRIPPER_OPEN_BUTTON))
        if not motion_paused and close_pressed != open_pressed:
            gripper_direction = -1.0 if close_pressed else 1.0
            gripper_position += gripper_direction * GRIPPER_SPEED_PERCENT_S * dt
            gripper_position = float(
                np.clip(
                    gripper_position,
                    max(0.0, start_gripper_position - MAX_GRIPPER_OFFSET_PERCENT),
                    min(100.0, start_gripper_position + MAX_GRIPPER_OFFSET_PERCENT),
                )
            )

        candidate_joints = current_joints.copy()
        if wrist_mode:
            # D-pad down increases wrist_flex, matching the previously measured
            # direction where positive flex angles the gripper downward.
            candidate_joints[WRIST_FLEX_INDEX] += -hat_y * WRIST_SPEED_DEG_S * dt
            candidate_joints[WRIST_ROLL_INDEX] += -hat_x * WRIST_SPEED_DEG_S * dt
        else:
            for _ in range(MAX_IK_ITERATIONS):
                candidate_joints = kinematics.inverse_kinematics(
                    current_joint_pos=candidate_joints,
                    desired_ee_pose=target_pose,
                    position_weight=1.0,
                    orientation_weight=0.2,
                )
                candidate_pose = kinematics.forward_kinematics(candidate_joints)
                if np.linalg.norm(candidate_pose[:3, 3] - target_pose[:3, 3]) < 0.0001:
                    break

        joint_step = candidate_joints - current_joints
        raw_max_step = float(np.max(np.abs(joint_step)))
        if raw_max_step > 0.0:
            step_scale = min(1.0, MAX_JOINT_STEP_DEG / raw_max_step)
        else:
            step_scale = 1.0
        limited_candidate_joints = current_joints + joint_step * step_scale
        limited_candidate_pose = kinematics.forward_kinematics(limited_candidate_joints)
        within_joint_limits = bool(
            np.all(limited_candidate_joints >= joint_lower)
            and np.all(limited_candidate_joints <= joint_upper)
        )
        within_workspace = bool(
            np.all(
                np.abs(limited_candidate_pose[:2, 3] - start_pose[:2, 3])
                <= MAX_XY_OFFSET_M + 0.001
            )
            and limited_candidate_pose[2, 3] >= SOFT_FLOOR_Z_M - 0.001
            and limited_candidate_pose[2, 3] <= start_pose[2, 3] + MAX_Z_UP_OFFSET_M + 0.001
        )

        if raw_max_step <= MAX_RAW_IK_STEP_DEG and within_joint_limits and within_workspace:
            current_joints = limited_candidate_joints
            if wrist_mode:
                # The directly controlled wrist pose becomes the new Cartesian
                # target, so later XYZ motion starts from and holds this angle.
                target_pose = kinematics.forward_kinematics(current_joints)
            elif step_scale < 1.0:
                # Do not let an unreachable position backlog build up while
                # joint motion is being rate-limited.
                limited_pose = kinematics.forward_kinematics(current_joints)
                target_pose[:3, 3] = limited_pose[:3, 3]
            goals = {
                f"{name}.pos": float(value)
                for name, value in zip(JOINT_NAMES, current_joints, strict=True)
            }
            goals["gripper.pos"] = gripper_position
            robot.send_action(goals)
            status = "LIMIT" if step_scale < 1.0 else "OK"
        else:
            # Discard an unsafe target and stay at the last commanded pose.
            target_pose = kinematics.forward_kinematics(current_joints)
            status = "REJECT"

        if now - last_feedback_time >= 0.25:
            feedback = robot.bus.sync_read("Present_Position", num_retry=2)
            feedback_joints = np.array([feedback[name] for name in JOINT_NAMES], dtype=float)
            following_error = float(np.max(np.abs(feedback_joints - current_joints)))
            if following_error > FOLLOWING_PAUSE_ERROR_DEG:
                motion_paused = True
            elif following_error < FOLLOWING_RESUME_ERROR_DEG:
                motion_paused = False

            if following_error > FOLLOWING_ESTOP_ERROR_DEG:
                if following_error_since is None:
                    following_error_since = now
                elif now - following_error_since >= FOLLOWING_ESTOP_TIMEOUT_S:
                    print(
                        "\n[ESTOP] 모터 추종 오차가 "
                        f"{FOLLOWING_ESTOP_TIMEOUT_S:.2f}초 이상 큽니다: "
                        f"{following_error:.2f} deg"
                    )
                    break
            else:
                following_error_since = None
            last_feedback_time = now

        if now - last_print_time >= 0.1:
            actual_pose = kinematics.forward_kinematics(current_joints)
            xyz_offset_mm = (actual_pose[:3, 3] - start_pose[:3, 3]) * 1000
            print(
                f"\rxyz offset=[{xyz_offset_mm[0]:+6.2f}, "
                f"{xyz_offset_mm[1]:+6.2f}, {xyz_offset_mm[2]:+6.2f}] mm  "
                f"gripper={gripper_position:5.1f}%  "
                f"raw_step={raw_max_step:5.2f} deg  "
                f"follow={following_error:4.2f} deg  "
                f"{'PAUSE' if motion_paused else ('WRIST' if wrist_mode else 'XYZ'):5s} "
                f"{status:6s}",
                end="",
                flush=True,
            )
            last_print_time = now

        time.sleep(max(0.0, 1 / LOOP_HZ - (time.monotonic() - now)))

except KeyboardInterrupt:
    print("\nCtrl+C 입력 감지")
finally:
    if robot.bus.is_connected:
        if torque_enabled:
            robot.bus.disable_torque(num_retry=2)
            print("토크 OFF")
        robot.bus.disconnect(disable_torque=False)
    pygame.quit()
    print("연결 종료")
