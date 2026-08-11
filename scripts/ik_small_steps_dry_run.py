#!/usr/bin/env python3
"""Solve independent 2 mm SO-101 Cartesian steps without hardware access."""

import json
from pathlib import Path

import numpy as np

from lerobot.model.kinematics import RobotKinematics


PROJECT_DIR = Path(__file__).resolve().parents[1]
HOME_FILE = PROJECT_DIR / "config" / "follower_home_candidate.json"
URDF_FILE = Path.home() / "SO-ARM100" / "Simulation" / "SO101" / "so101_new_calib.urdf"

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]

STEP_M = 0.002  # 2 mm


with HOME_FILE.open() as file:
    home_position = json.load(file)["position"]

home_joints = np.array(
    [home_position[joint] for joint in JOINT_NAMES],
    dtype=float,
)

def make_kinematics() -> RobotKinematics:
    return RobotKinematics(
        urdf_path=str(URDF_FILE),
        target_frame_name="gripper_frame_link",
        joint_names=JOINT_NAMES,
    )


home_kinematics = make_kinematics()
home_pose = home_kinematics.forward_kinematics(home_joints)

tests = [
    ("x +2 mm", 0, STEP_M),
    ("x -2 mm", 0, -STEP_M),
    ("y +2 mm", 1, STEP_M),
    ("y -2 mm", 1, -STEP_M),
    ("z +2 mm", 2, STEP_M),
    ("z -2 mm", 2, -STEP_M),
]

print("Home end-effector xyz (m):", np.round(home_pose[:3, 3], 6))
print("Cartesian step size (m):", STEP_M)

for label, axis, delta_m in tests:
    # Use an independent solver so a previous test cannot influence this one.
    kinematics = make_kinematics()
    desired_pose = home_pose.copy()
    desired_pose[axis, 3] += delta_m

    # Placo performs one solver update per call. Iterate until the Cartesian
    # position converges instead of sending a partially solved target.
    solved_joints = home_joints.copy()
    iteration_count = 0
    for iteration_count in range(1, 51):
        solved_joints = kinematics.inverse_kinematics(
            current_joint_pos=solved_joints,
            desired_ee_pose=desired_pose,
            position_weight=1.0,
            orientation_weight=0.01,
        )

        intermediate_pose = kinematics.forward_kinematics(solved_joints)
        position_error_m = np.linalg.norm(
            intermediate_pose[:3, 3] - desired_pose[:3, 3]
        )
        if position_error_m < 0.00005:  # 0.05 mm
            break

    solved_pose = kinematics.forward_kinematics(solved_joints)
    joint_delta = solved_joints - home_joints
    achieved_delta_mm = (solved_pose[:3, 3] - home_pose[:3, 3]) * 1000

    print(f"\n{label}")
    print(f"  IK iterations: {iteration_count}")
    print("  joint delta (deg)")
    for joint, delta_deg in zip(JOINT_NAMES, joint_delta, strict=True):
        print(f"    {joint:14s}: {delta_deg:+8.4f}")
    print(
        "  achieved xyz delta (mm): "
        f"[{achieved_delta_mm[0]:+.3f}, "
        f"{achieved_delta_mm[1]:+.3f}, "
        f"{achieved_delta_mm[2]:+.3f}]"
    )
    print(f"  largest joint step: {np.max(np.abs(joint_delta)):.4f} deg")
