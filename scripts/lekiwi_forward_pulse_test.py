#!/usr/bin/env python3
"""Send one short, low-speed forward pulse to a camera-free LeKiwi host."""

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


def send_action(socket: zmq.Socket, arm_state: dict[str, float], x_velocity: float) -> None:
    action = {
        **arm_state,
        "x.vel": x_velocity,
        "y.vel": 0.0,
        "theta.vel": 0.0,
    }
    socket.send_string(json.dumps(action))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--speed", type=float, default=0.02, help="Forward speed in m/s")
    parser.add_argument("--duration", type=float, default=0.3, help="Pulse duration in seconds")
    args = parser.parse_args()

    if not 0 < args.speed <= 0.05:
        parser.error("--speed must be greater than 0 and at most 0.05 m/s")
    if not 0 < args.duration <= 0.5:
        parser.error("--duration must be greater than 0 and at most 0.5 seconds")

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

    try:
        send_action(command, arm_state, 0.0)
        for remaining in (3, 2, 1):
            print(f"Forward pulse in {remaining}...")
            time.sleep(1)

        print(f"Moving at {args.speed:.3f} m/s for {args.duration:.2f} s")
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            send_action(command, arm_state, args.speed)
            time.sleep(0.05)
    finally:
        for _ in range(5):
            send_action(command, arm_state, 0.0)
            time.sleep(0.05)
        observation.close()
        command.close()
        context.term()

    print("STOP sent. Test complete.")


if __name__ == "__main__":
    main()
