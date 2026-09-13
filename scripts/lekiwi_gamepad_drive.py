#!/usr/bin/env python3
"""Camera-free, left-stick gamepad driving for LeKiwi over ZMQ."""

import argparse
import json
import time

import pygame
import zmq


ARM_KEYS = (
    "arm_shoulder_pan.pos",
    "arm_shoulder_lift.pos",
    "arm_elbow_flex.pos",
    "arm_wrist_flex.pos",
    "arm_wrist_roll.pos",
    "arm_gripper.pos",
)
LEFT_STICK_X = 0
LEFT_STICK_Y = 1
OPTIONS_BUTTON = 9
LOOP_HZ = 20


def apply_deadzone(value: float, deadzone: float) -> float:
    if abs(value) < deadzone:
        return 0.0
    magnitude = (abs(value) - deadzone) / (1.0 - deadzone)
    return (-1.0 if value < 0 else 1.0) * magnitude


def send_action(
    socket: zmq.Socket,
    arm_state: dict[str, float],
    x_velocity: float = 0.0,
    y_velocity: float = 0.0,
    theta_velocity: float = 0.0,
) -> None:
    socket.send_string(
        json.dumps(
            {
                **arm_state,
                "x.vel": x_velocity,
                "y.vel": y_velocity,
                "theta.vel": theta_velocity,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--speed", type=float, default=0.05)
    parser.add_argument("--turn-speed", type=float, default=25.0)
    parser.add_argument("--deadzone", type=float, default=0.15)
    args = parser.parse_args()

    if not 0 < args.speed <= 0.08:
        parser.error("--speed must be greater than 0 and at most 0.08 m/s")
    if not 0 < args.turn_speed <= 30:
        parser.error("--turn-speed must be greater than 0 and at most 30 deg/s")
    if not 0 <= args.deadzone < 0.5:
        parser.error("--deadzone must be at least 0 and less than 0.5")

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        pygame.quit()
        raise SystemExit("게임패드를 찾지 못했습니다.")

    gamepad = pygame.joystick.Joystick(0)
    gamepad.init()

    context = zmq.Context()
    command = context.socket(zmq.PUSH)
    command.setsockopt(zmq.CONFLATE, 1)
    command.connect(f"tcp://{args.ip}:5555")

    observation = context.socket(zmq.PULL)
    observation.setsockopt(zmq.RCVHWM, 2)
    observation.connect(f"tcp://{args.ip}:5556")

    poller = zmq.Poller()
    poller.register(observation, zmq.POLLIN)
    events = dict(poller.poll(5000))
    if observation not in events:
        observation.close()
        command.close()
        context.term()
        pygame.quit()
        raise SystemExit("No LeKiwi host observation received within 5 seconds.")

    frames = observation.recv_multipart()
    state = json.loads(frames[0])
    arm_state = {key: float(state[key]) for key in ARM_KEYS}

    screen = pygame.display.set_mode((650, 210))
    pygame.display.set_caption("LeKiwi Gamepad Drive - OPTIONS to stop and quit")
    font = pygame.font.Font(None, 28)
    clock = pygame.time.Clock()

    print(f"Gamepad: {gamepad.get_name()}")
    print("Left stick: drive/strafe/curve. OPTIONS: stop and quit.")

    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            if not gamepad.get_init():
                print("Gamepad disconnected.")
                break
            if gamepad.get_button(OPTIONS_BUTTON):
                print("OPTIONS pressed.")
                break

            longitudinal = -apply_deadzone(
                gamepad.get_axis(LEFT_STICK_Y), args.deadzone
            )
            lateral = -apply_deadzone(
                gamepad.get_axis(LEFT_STICK_X), args.deadzone
            )
            x_velocity = 0.0
            y_velocity = 0.0
            theta_velocity = 0.0
            label = "STOP"

            if longitudinal != 0.0 and lateral != 0.0:
                x_velocity = longitudinal * args.speed
                theta_velocity = longitudinal * lateral * args.turn_speed
                label = "CURVE LEFT" if theta_velocity > 0 else "CURVE RIGHT"
            elif longitudinal != 0.0:
                x_velocity = longitudinal * args.speed
                label = "FORWARD" if longitudinal > 0 else "BACKWARD"
            elif lateral != 0.0:
                y_velocity = lateral * args.speed
                label = "STRAFE LEFT" if lateral > 0 else "STRAFE RIGHT"

            send_action(
                command,
                arm_state,
                x_velocity=x_velocity,
                y_velocity=y_velocity,
                theta_velocity=theta_velocity,
            )

            screen.fill((25, 25, 30))
            lines = (
                "LEFT STICK: up/down = forward/back",
                "left/right = strafe | diagonal = curve",
                f"{label}   x={x_velocity:+.3f}  y={y_velocity:+.3f}",
                f"theta={theta_velocity:+.1f} deg/s   OPTIONS: STOP + QUIT",
            )
            for index, line in enumerate(lines):
                screen.blit(font.render(line, True, (235, 235, 235)), (22, 20 + index * 44))
            pygame.display.flip()
            clock.tick(LOOP_HZ)
    except KeyboardInterrupt:
        pass
    finally:
        for _ in range(6):
            send_action(command, arm_state)
            time.sleep(0.05)
        pygame.quit()
        observation.close()
        command.close()
        context.term()
        print("Final STOP sent. Gamepad teleoperation ended.")


if __name__ == "__main__":
    main()
