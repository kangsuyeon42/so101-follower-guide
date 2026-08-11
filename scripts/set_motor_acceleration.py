#!/usr/bin/env python3
"""Set a moderate SO-101 acceleration value without changing PID or velocity."""

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


ARM_ACCELERATION = 50
GRIPPER_ACCELERATION = 20


def target_acceleration(motor: str) -> int:
    return GRIPPER_ACCELERATION if motor == "gripper" else ARM_ACCELERATION

robot = SO101Follower(
    SO101FollowerConfig(
        port="/dev/ttyACM0",
        id="follower",
        use_degrees=True,
    )
)

robot.bus.connect()

try:
    before = {
        motor: robot.bus.read("Acceleration", motor, normalize=False)
        for motor in robot.bus.motors
    }

    print("Acceleration 변경 예정")
    for motor, value in before.items():
        print(f"  {motor:14s}: {value:3d} -> {target_acceleration(motor):3d}")

    input("제어 프로그램이 종료되어 있다면 ENTER를 눌러 적용하세요. ")

    for motor in robot.bus.motors:
        robot.bus.write(
            "Acceleration",
            motor,
            target_acceleration(motor),
            normalize=False,
        )

    print("\n적용 결과")
    for motor in robot.bus.motors:
        value = robot.bus.read("Acceleration", motor, normalize=False)
        print(f"  {motor:14s}: {value:3d}")
finally:
    # Acceleration can be changed without altering the current torque state.
    robot.bus.disconnect(disable_torque=False)
