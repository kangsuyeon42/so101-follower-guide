#!/usr/bin/env python3
"""Camera-free, dead-man keyboard driving for LeKiwi over ZMQ."""

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
    args = parser.parse_args()

    if not 0 < args.speed <= 0.08:
        parser.error("--speed must be greater than 0 and at most 0.08 m/s")
    if not 0 < args.turn_speed <= 30:
        parser.error("--turn-speed must be greater than 0 and at most 30 deg/s")

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
        raise SystemExit("No LeKiwi host observation received within 5 seconds.")

    frames = observation.recv_multipart()
    state = json.loads(frames[0])
    arm_state = {key: float(state[key]) for key in ARM_KEYS}

    pygame.init()
    screen = pygame.display.set_mode((560, 180))
    pygame.display.set_caption("LeKiwi WASD Drive - ESC to stop and quit")
    font = pygame.font.Font(None, 30)
    clock = pygame.time.Clock()
    running = True
    try:
        print("Click the control window, then use WASD. SPACE stops; ESC quits.")
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            keys = pygame.key.get_pressed()
            focused = pygame.key.get_focused()
            x_velocity = 0.0
            y_velocity = 0.0
            theta_velocity = 0.0
            label = "STOP"

            if focused and not keys[pygame.K_SPACE]:
                longitudinal = int(keys[pygame.K_w]) - int(keys[pygame.K_s])
                lateral = int(keys[pygame.K_a]) - int(keys[pygame.K_d])
                if longitudinal and lateral:
                    # W/S + A/D behaves like car steering, not diagonal strafing.
                    x_velocity = longitudinal * args.speed
                    theta_velocity = longitudinal * lateral * args.turn_speed
                    label = "CURVE LEFT" if theta_velocity > 0 else "CURVE RIGHT"
                elif longitudinal:
                    x_velocity = longitudinal * args.speed
                    label = "FORWARD" if longitudinal > 0 else "BACKWARD"
                elif lateral:
                    # A/D alone retains LeKiwi's omnidirectional side motion.
                    y_velocity = lateral * args.speed
                    label = "STRAFE LEFT" if lateral > 0 else "STRAFE RIGHT"

            send_action(command, arm_state, x_velocity, y_velocity, theta_velocity)
            screen.fill((25, 25, 30))
            lines = (
                "W/A/S/D: front/left/back/right",
                "W+A or W+D: racing-style curve",
                f"{label}   |   SPACE: STOP   ESC: QUIT",
            )
            for index, line in enumerate(lines):
                screen.blit(font.render(line, True, (235, 235, 235)), (24, 25 + index * 45))
            pygame.display.flip()
            clock.tick(20)
    finally:
        for _ in range(6):
            send_action(command, arm_state)
            time.sleep(0.05)
        pygame.quit()
        observation.close()
        command.close()
        context.term()
        print("Final STOP sent. Keyboard teleoperation ended.")


if __name__ == "__main__":
    main()
