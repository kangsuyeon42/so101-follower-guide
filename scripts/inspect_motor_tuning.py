#!/usr/bin/env python3
"""Read SO-101 motor motion and PID settings without changing them."""

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


robot = SO101Follower(
    SO101FollowerConfig(
        port="/dev/ttyACM0",
        id="follower",
        use_degrees=True,
    )
)

registers = [
    "Acceleration",
    "Goal_Velocity",
    "P_Coefficient",
    "I_Coefficient",
    "D_Coefficient",
]

robot.bus.connect()

try:
    print("motor tuning registers (raw values)")
    print(
        f"{'motor':14s} "
        f"{'accel':>7s} {'velocity':>9s} "
        f"{'P':>5s} {'I':>5s} {'D':>5s}"
    )

    for motor in robot.bus.motors:
        values = {
            register: robot.bus.read(register, motor, normalize=False)
            for register in registers
        }
        print(
            f"{motor:14s} "
            f"{values['Acceleration']:7d} "
            f"{values['Goal_Velocity']:9d} "
            f"{values['P_Coefficient']:5d} "
            f"{values['I_Coefficient']:5d} "
            f"{values['D_Coefficient']:5d}"
        )
finally:
    # This inspection must not change whether torque is currently enabled.
    robot.bus.disconnect(disable_torque=False)

