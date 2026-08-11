#!/usr/bin/env python3
"""Read LeRobot-calibrated joint positions without enabling torque."""

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

PORT = "/dev/ttyACM0"
ROBOT_ID = "follower"


robot = SO101Follower(
    SO101FollowerConfig(
        port=PORT,
        id=ROBOT_ID,
        use_degrees=True,
    )
)

# Connect only the bus. robot.connect() also performs motor configuration.
robot.bus.connect()

try:
    positions = robot.bus.sync_read("Present_Position", num_retry=2)
    for joint, value in positions.items():
        unit = "%" if joint == "gripper" else "deg"
        print(f"{joint:14s} {value:9.3f} {unit}")
finally:
    # Do not write torque state during this read-only check.
    robot.bus.disconnect(disable_torque=False)

