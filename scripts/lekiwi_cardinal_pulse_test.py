#!/usr/bin/env python3
"""Test short LeKiwi motions: forward, backward, left, and right."""

import argparse
import json
import time

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
) -> None:
    socket.send_string(
        json.dumps(
            {
                **arm_state,
                "x.vel": x_velocity,
                "y.vel": y_velocity,
                "theta.vel": 0.0,
            }
        )
    )


def send_stop(socket: zmq.Socket, arm_state: dict[str, float]) -> None:
    for _ in range(5):
        send_action(socket, arm_state)
        time.sleep(0.05)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--speed", type=float, default=0.02)
    parser.add_argument("--duration", type=float, default=0.3)
    parser.add_argument("--pause", type=float, default=1.5)
    args = parser.parse_args()

    if not 0 < args.speed <= 0.05:
        parser.error("--speed must be greater than 0 and at most 0.05 m/s")
    if not 0 < args.duration <= 0.5:
        parser.error("--duration must be greater than 0 and at most 0.5 seconds")
    if args.pause < 1.0:
        parser.error("--pause must be at least 1.0 second")

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

    motions = (
        ("FORWARD", args.speed, 0.0),
        ("BACKWARD", -args.speed, 0.0),
        ("LEFT", 0.0, args.speed),
        ("RIGHT", 0.0, -args.speed),
    )

    try:
        send_stop(command, arm_state)
        for remaining in (3, 2, 1):
            print(f"Test starts in {remaining}...")
            time.sleep(1)

        for label, x_velocity, y_velocity in motions:
            print(f"{label}: moving for {args.duration:.2f} s")
            deadline = time.monotonic() + args.duration
            while time.monotonic() < deadline:
                send_action(command, arm_state, x_velocity, y_velocity)
                time.sleep(0.05)
            send_stop(command, arm_state)
            print(f"{label}: STOP")
            time.sleep(args.pause)
    finally:
        send_stop(command, arm_state)
        observation.close()
        command.close()
        context.term()

    print("All four directions tested. Final STOP sent.")


if __name__ == "__main__":
    main()
