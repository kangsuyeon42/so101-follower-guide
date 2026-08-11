#!/usr/bin/env python3
"""Compute the SO-101 home candidate end-effector pose without hardware access."""

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


with HOME_FILE.open() as file:
    home_config = json.load(file)

home_position = home_config["position"]
joint_degrees = np.array(
    [home_position[joint] for joint in JOINT_NAMES],
    dtype=float,
)

kinematics = RobotKinematics(
    urdf_path=str(URDF_FILE),
    target_frame_name="gripper_frame_link",
    joint_names=JOINT_NAMES,
)

transform = kinematics.forward_kinematics(joint_degrees)
position_m = transform[:3, 3]

print("Home joint angles (degrees)")
for joint, angle in zip(JOINT_NAMES, joint_degrees, strict=True):
    print(f"  {joint:14s}: {angle:9.3f}")

print("\nbase_link -> gripper_frame_link transform")
print(np.array2string(transform, precision=5, suppress_small=True))

print("\nEnd-effector position relative to the URDF base")
print(f"  x: {position_m[0]:+.5f} m  ({position_m[0] * 1000:+.1f} mm)")
print(f"  y: {position_m[1]:+.5f} m  ({position_m[1] * 1000:+.1f} mm)")
print(f"  z: {position_m[2]:+.5f} m  ({position_m[2] * 1000:+.1f} mm)")
