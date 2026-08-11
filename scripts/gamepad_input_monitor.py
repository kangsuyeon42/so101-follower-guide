#!/usr/bin/env python3
"""Display the measured DualShock 4 mapping without connecting to the robot."""

import time

import pygame


DEADZONE = 0.15
LOOP_HZ = 20

AXIS_LEFT_X = 0
AXIS_LEFT_Y = 1
AXIS_L2 = 2
AXIS_RIGHT_X = 3
AXIS_RIGHT_Y = 4
AXIS_R2 = 5

BUTTON_GRIPPER_CLOSE = 0  # Cross
BUTTON_GRIPPER_OPEN = 1  # Circle
BUTTON_ESTOP = 9  # Options


def apply_deadzone(value: float) -> float:
    if abs(value) < DEADZONE:
        return 0.0
    return value


def trigger_value(axis_value: float) -> float:
    """Convert a trigger from -1..1 to 0..1."""
    return (axis_value + 1.0) / 2.0


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise SystemExit("게임패드를 찾지 못했습니다.")

gamepad = pygame.joystick.Joystick(0)
gamepad.init()

print("게임패드:", gamepad.get_name())
print("왼쪽 스틱: 손끝 앞뒤/좌우")
print("L2/R2: 손끝 아래/위")
print("Cross/Circle: 그리퍼 닫기/열기")
print("OPTIONS: dry-run 비상정지 및 종료")

try:
    while True:
        pygame.event.pump()

        if gamepad.get_button(BUTTON_ESTOP):
            print("\n[ESTOP] 비상정지 요청을 감지했습니다. 모니터를 종료합니다.")
            break

        left_x = apply_deadzone(gamepad.get_axis(AXIS_LEFT_X))
        left_y = apply_deadzone(gamepad.get_axis(AXIS_LEFT_Y))
        l2 = trigger_value(gamepad.get_axis(AXIS_L2))
        r2 = trigger_value(gamepad.get_axis(AXIS_R2))

        # User-facing Cartesian commands. Actual robot scale is added later.
        move_forward = -left_y
        move_left = -left_x
        move_up = r2 - l2

        close_pressed = bool(gamepad.get_button(BUTTON_GRIPPER_CLOSE))
        open_pressed = bool(gamepad.get_button(BUTTON_GRIPPER_OPEN))

        if close_pressed == open_pressed:
            gripper = "stop"
        elif close_pressed:
            gripper = "close"
        else:
            gripper = "open"

        print(
            "\r"
            f"forward={move_forward:+.2f}  "
            f"left={move_left:+.2f}  "
            f"up={move_up:+.2f}  "
            f"gripper={gripper:5s}",
            end="",
            flush=True,
        )

        time.sleep(1 / LOOP_HZ)
finally:
    print()
    pygame.quit()
