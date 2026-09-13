#!/usr/bin/env python3
"""Move the laptop leader and Pi-hosted LeKiwi arm to saved home poses."""

import argparse
import json
import time
from pathlib import Path

import zmq

from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
JOINTS = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
DEFAULT_LEADER_PORT = Path(
    "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF219186-if00"
)
LOOP_HZ = 20


def load_home(filename: str) -> dict[str, float]:
    with (PROJECT_DIR / "config" / filename).open() as file:
        return {
            name: float(value)
            for name, value in json.load(file)["position"].items()
        }


def movement_duration(
    start: dict[str, float],
    target: dict[str, float],
    joint_speed: float,
    gripper_speed: float,
) -> float:
    durations = [
        abs(target[name] - start[name])
        / (gripper_speed if name == "gripper" else joint_speed)
        for name in JOINTS
    ]
    return 1.5 * max(0.5, *durations)


def send_action(socket: zmq.Socket, arm_goal: dict[str, float]) -> None:
    socket.send_string(
        json.dumps(
            {
                **{f"arm_{name}.pos": value for name, value in arm_goal.items()},
                "x.vel": 0.0,
                "y.vel": 0.0,
                "theta.vel": 0.0,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--leader-port", type=Path, default=DEFAULT_LEADER_PORT)
    parser.add_argument("--joint-speed", type=float, default=10.0)
    parser.add_argument("--gripper-speed", type=float, default=20.0)
    args = parser.parse_args()

    if not args.leader_port.exists():
        parser.error(f"Leader port not found: {args.leader_port}")
    if not 0 < args.joint_speed <= 15:
        parser.error("--joint-speed must be greater than 0 and at most 15 deg/s")
    if not 0 < args.gripper_speed <= 25:
        parser.error("--gripper-speed must be greater than 0 and at most 25 %/s")

    leader_target = load_home("leader_home_candidate.json")
    follower_target = load_home("follower_home_candidate.json")
    leader = SO101Leader(
        SO101LeaderConfig(
            port=str(args.leader_port),
            id="leader",
            use_degrees=True,
        )
    )

    context = zmq.Context()
    command = context.socket(zmq.PUSH)
    command.setsockopt(zmq.CONFLATE, 1)
    command.connect(f"tcp://{args.ip}:5555")
    observation = context.socket(zmq.PULL)
    observation.setsockopt(zmq.RCVHWM, 2)
    observation.connect(f"tcp://{args.ip}:5556")
    leader_torque_enabled = False
    follower_goal = None

    try:
        poller = zmq.Poller()
        poller.register(observation, zmq.POLLIN)
        if observation not in dict(poller.poll(5000)):
            raise SystemExit("No LeKiwi host observation received within 5 seconds.")
        state = json.loads(observation.recv_multipart()[0])
        follower_start = {
            name: float(state[f"arm_{name}.pos"]) for name in JOINTS
        }
        follower_goal = dict(follower_start)

        # Connect only to the bus: no setup, configuration, or calibration.
        leader.bus.connect()
        torque_state = {
            name: leader.bus.read("Torque_Enable", name, normalize=False)
            for name in leader.bus.motors
        }
        if any(torque_state.values()):
            raise SystemExit("Leader torque is already ON; home move aborted.")
        present = leader.bus.sync_read("Present_Position", num_retry=2)
        leader_start = {name: float(present[name]) for name in JOINTS}

        duration = max(
            movement_duration(
                leader_start,
                leader_target,
                args.joint_speed,
                args.gripper_speed,
            ),
            movement_duration(
                follower_start,
                follower_target,
                args.joint_speed,
                args.gripper_speed,
            ),
        )
        print("Leader and LeKiwi follower current pose -> saved home poses")
        print(f"Expected duration: {duration:.1f} seconds")
        print("The base remains stopped. Ctrl+C aborts the move.")
        input("두 팔 주변과 아래를 비우고 손을 뗀 뒤 ENTER: ")

        # Prevent the leader from moving toward a retained motor goal.
        leader.bus.sync_write("Goal_Position", leader_start)
        leader.bus.enable_torque()
        leader_torque_enabled = True

        started_at = time.monotonic()
        while True:
            progress = min((time.monotonic() - started_at) / duration, 1.0)
            blend = progress * progress * (3.0 - 2.0 * progress)
            leader_goal = {
                name: leader_start[name]
                + (leader_target[name] - leader_start[name]) * blend
                for name in JOINTS
            }
            follower_goal = {
                name: follower_start[name]
                + (follower_target[name] - follower_start[name]) * blend
                for name in JOINTS
            }
            leader.bus.sync_write("Goal_Position", leader_goal)
            send_action(command, follower_goal)
            print(f"\rProgress {progress * 100:6.1f}%", end="", flush=True)
            if progress >= 1.0:
                break
            time.sleep(1 / LOOP_HZ)

        print("\nBoth arms reached their saved home targets.")
        input("두 팔을 받을 준비 후 ENTER를 누르면 Leader 토크를 해제합니다: ")
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
    finally:
        if follower_goal is not None:
            for _ in range(6):
                send_action(command, follower_goal)
                time.sleep(0.05)
        if leader.bus.is_connected:
            if leader_torque_enabled:
                try:
                    leader.bus.disable_torque(num_retry=2)
                    print("Leader torque OFF")
                except Exception as error:
                    print(f"Warning: could not disable Leader torque: {error}")
            leader.bus.disconnect(disable_torque=False)
        observation.close()
        command.close()
        context.term()
        print("Final base STOP sent. Home move ended.")


if __name__ == "__main__":
    main()
