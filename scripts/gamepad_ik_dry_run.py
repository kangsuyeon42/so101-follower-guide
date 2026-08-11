#!/usr/bin/env python3
"""Run gamepad-to-IK control without opening the SO-101 serial port."""

import json
import time
from pathlib import Path

import numpy as np
import pygame

from lerobot.model.kinematics import RobotKinematics


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
CALIBRATION_FILE = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "lerobot"
    / "calibration"
    / "robots"
    / "so_follower"
    / "follower.json"
)
URDF_FILE = Path.home() / "SO-ARM100" / "Simulation" / "SO101" / "so101_new_calib.urdf"

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]

DEADZONE = 0.15
LOOP_HZ = 20
MAX_EE_SPEED_M_S = 0.005  # 5 mm/s at full stick
WORKSPACE_RADIUS_M = 0.020  # Home position +/- 20 mm on each axis
MAX_JOINT_STEP_DEG = 2.0
MAX_IK_ITERATIONS = 10

AXIS_LEFT_X = 0
AXIS_LEFT_Y = 1
AXIS_L2 = 2
AXIS_R2 = 5

BUTTON_GRIPPER_CLOSE = 0  # Cross
BUTTON_GRIPPER_OPEN = 1  # Circle
BUTTON_ESTOP = 9  # Options


def apply_deadzone(value: float) -> float:
    if abs(value) < DEADZONE:
        return 0.0
    # Rescale the remaining range so motion starts smoothly at zero.
    magnitude = (abs(value) - DEADZONE) / (1.0 - DEADZONE)
    return float(np.sign(value) * magnitude)


def trigger_value(axis_value: float) -> float:
    return (axis_value + 1.0) / 2.0


def calibration_joint_limits(calibration: dict) -> tuple[np.ndarray, np.ndarray]:
    lower = []
    upper = []
    for joint in JOINT_NAMES:
        entry = calibration[joint]
        half_range_raw = (entry["range_max"] - entry["range_min"]) / 2
        half_range_deg = half_range_raw * 360 / 4095
        lower.append(-half_range_deg)
        upper.append(half_range_deg)
    return np.array(lower), np.array(upper)


with HOME_FILE.open() as file:
    home_config = json.load(file)

with CALIBRATION_FILE.open() as file:
    calibration = json.load(file)

home_position = home_config["position"]
home_joints = np.array([home_position[joint] for joint in JOINT_NAMES], dtype=float)
joint_lower, joint_upper = calibration_joint_limits(calibration)

kinematics = RobotKinematics(
    urdf_path=str(URDF_FILE),
    target_frame_name="gripper_frame_link",
    joint_names=JOINT_NAMES,
)

home_pose = kinematics.forward_kinematics(home_joints)
target_pose = home_pose.copy()
simulated_joints = home_joints.copy()
simulated_gripper = float(home_position["gripper"])

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise SystemExit("게임패드를 찾지 못했습니다.")

gamepad = pygame.joystick.Joystick(0)
gamepad.init()

print("GAMEPAD IK DRY-RUN — 로봇에는 연결하지 않습니다.")
print("왼쪽 스틱: 앞뒤/좌우, L2/R2: 아래/위")
print("Cross/Circle: 그리퍼 닫기/열기, OPTIONS: 종료")
print("표시 좌표 가정: +x=앞, +y=왼쪽, +z=위")
print("홈 xyz (mm):", np.round(home_pose[:3, 3] * 1000, 2))

last_time = time.monotonic()
last_print_time = 0.0

try:
    while True:
        pygame.event.pump()

        if gamepad.get_button(BUTTON_ESTOP):
            print("\n[ESTOP] OPTIONS 입력을 감지했습니다. dry-run을 종료합니다.")
            break

        now = time.monotonic()
        dt = min(now - last_time, 0.1)
        last_time = now

        left_x = apply_deadzone(gamepad.get_axis(AXIS_LEFT_X))
        left_y = apply_deadzone(gamepad.get_axis(AXIS_LEFT_Y))
        l2 = trigger_value(gamepad.get_axis(AXIS_L2))
        r2 = trigger_value(gamepad.get_axis(AXIS_R2))

        command = np.array(
            [
                -left_y,  # Stick up means +x (forward).
                -left_x,  # Stick left means +y (left).
                r2 - l2,  # R2 means +z, L2 means -z.
            ],
            dtype=float,
        )

        target_pose[:3, 3] += command * MAX_EE_SPEED_M_S * dt
        target_pose[:3, 3] = np.clip(
            target_pose[:3, 3],
            home_pose[:3, 3] - WORKSPACE_RADIUS_M,
            home_pose[:3, 3] + WORKSPACE_RADIUS_M,
        )

        candidate_joints = simulated_joints.copy()
        for _ in range(MAX_IK_ITERATIONS):
            candidate_joints = kinematics.inverse_kinematics(
                current_joint_pos=candidate_joints,
                desired_ee_pose=target_pose,
                position_weight=1.0,
                orientation_weight=0.01,
            )

            candidate_pose = kinematics.forward_kinematics(candidate_joints)
            error_m = np.linalg.norm(candidate_pose[:3, 3] - target_pose[:3, 3])
            if error_m < 0.0001:  # 0.1 mm
                break

        joint_step = candidate_joints - simulated_joints
        within_joint_limits = bool(
            np.all(candidate_joints >= joint_lower)
            and np.all(candidate_joints <= joint_upper)
        )
        within_step_limit = bool(np.max(np.abs(joint_step)) <= MAX_JOINT_STEP_DEG)

        if within_joint_limits and within_step_limit:
            simulated_joints = candidate_joints
            status = "OK"
        else:
            # Reject the target and return it to the last accepted pose.
            target_pose = kinematics.forward_kinematics(simulated_joints)
            status = "REJECT"

        close_pressed = bool(gamepad.get_button(BUTTON_GRIPPER_CLOSE))
        open_pressed = bool(gamepad.get_button(BUTTON_GRIPPER_OPEN))
        if close_pressed != open_pressed:
            gripper_direction = -1.0 if close_pressed else 1.0
            simulated_gripper += gripper_direction * 20.0 * dt
            simulated_gripper = float(np.clip(simulated_gripper, 0.0, 100.0))

        if now - last_print_time >= 0.1:
            accepted_pose = kinematics.forward_kinematics(simulated_joints)
            offset_mm = (accepted_pose[:3, 3] - home_pose[:3, 3]) * 1000
            print(
                "\r"
                f"xyz offset mm="
                f"[{offset_mm[0]:+6.2f}, {offset_mm[1]:+6.2f}, {offset_mm[2]:+6.2f}]  "
                f"max joint step={np.max(np.abs(joint_step)):5.2f} deg  "
                f"gripper={simulated_gripper:5.1f}%  "
                f"{status:6s}",
                end="",
                flush=True,
            )
            last_print_time = now

        time.sleep(max(0.0, 1 / LOOP_HZ - (time.monotonic() - now)))
finally:
    print()
    pygame.quit()
