#!/usr/bin/env python3
"""Print all gamepad axis values for 15 seconds without touching the robot."""

import time

import pygame


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise SystemExit("게임패드를 찾지 못했습니다.")

gamepad = pygame.joystick.Joystick(0)
gamepad.init()

axis_count = gamepad.get_numaxes()

print("게임패드:", gamepad.get_name())
print("축 개수:", axis_count)
print("15초 동안 컨트롤을 하나씩 움직이세요.")

try:
    for _ in range(75):
        pygame.event.pump()

        values = [
            round(gamepad.get_axis(axis), 2)
            for axis in range(axis_count)
        ]

        print(values)
        time.sleep(0.2)
finally:
    pygame.quit()
