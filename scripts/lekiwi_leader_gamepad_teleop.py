#!/usr/bin/env python3
"""Control LeKiwi's arm from an SO-101 leader and its base from a gamepad."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import pygame
import zmq

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.cameras.opencv.configuration_opencv import ColorMode, Cv2Backends
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


JOINTS = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
LEFT_STICK_X = 0
LEFT_STICK_Y = 1
OPTIONS_BUTTON = 9
LOOP_HZ = 20
DEFAULT_LEADER_PORT = Path(
    "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF219186-if00"
)
FOLLOWER_CALIBRATION = (
    Path.home()
    / ".cache/huggingface/lerobot/calibration/robots/so_follower/follower.json"
)
BODY_CAMERA = Path(
    "/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_2F21131F-video-index0"
)


def camera_index_from_by_id(path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"Camera not found: {path}")
    resolved = path.resolve()
    if not resolved.name.startswith("video"):
        raise SystemExit(f"Unexpected camera device: {resolved}")
    return int(resolved.name.removeprefix("video"))


def apply_deadzone(value: float, deadzone: float) -> float:
    if abs(value) < deadzone:
        return 0.0
    magnitude = (abs(value) - deadzone) / (1.0 - deadzone)
    return (-1.0 if value < 0 else 1.0) * magnitude


def send_action(
    socket: zmq.Socket,
    arm_goal: dict[str, float],
    x_velocity: float = 0.0,
    y_velocity: float = 0.0,
    theta_velocity: float = 0.0,
) -> None:
    socket.send_string(
        json.dumps(
            {
                **{f"arm_{name}.pos": value for name, value in arm_goal.items()},
                "x.vel": x_velocity,
                "y.vel": y_velocity,
                "theta.vel": theta_velocity,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--leader-port", type=Path, default=DEFAULT_LEADER_PORT)
    parser.add_argument("--speed", type=float, default=0.05)
    parser.add_argument("--turn-speed", type=float, default=25.0)
    parser.add_argument("--deadzone", type=float, default=0.15)
    parser.add_argument("--joint-speed", type=float, default=20.0)
    parser.add_argument("--gripper-speed", type=float, default=40.0)
    parser.add_argument("--practice-ui", action="store_true")
    parser.add_argument("--wrist-port", type=int, default=5560)
    args = parser.parse_args()

    if not args.leader_port.exists():
        parser.error(f"Leader port not found: {args.leader_port}")
    if not FOLLOWER_CALIBRATION.exists():
        parser.error(f"Follower calibration not found: {FOLLOWER_CALIBRATION}")
    if not 0 < args.speed <= 0.08:
        parser.error("--speed must be greater than 0 and at most 0.08 m/s")
    if not 0 < args.turn_speed <= 30:
        parser.error("--turn-speed must be greater than 0 and at most 30 deg/s")
    if not 0 <= args.deadzone < 0.5:
        parser.error("--deadzone must be at least 0 and less than 0.5")
    if not 0 < args.joint_speed <= 30:
        parser.error("--joint-speed must be greater than 0 and at most 30 deg/s")
    if not 0 < args.gripper_speed <= 60:
        parser.error("--gripper-speed must be greater than 0 and at most 60 %/s")

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        pygame.quit()
        raise SystemExit("게임패드를 찾지 못했습니다.")
    gamepad = pygame.joystick.Joystick(0)
    gamepad.init()

    leader = SO101Leader(
        SO101LeaderConfig(
            port=str(args.leader_port),
            id="leader",
            use_degrees=True,
        )
    )
    body_camera = None
    if args.practice_ui:
        body_camera = OpenCVCamera(
            OpenCVCameraConfig(
                index_or_path=camera_index_from_by_id(BODY_CAMERA),
                width=1280,
                height=720,
                fps=30,
                fourcc="MJPG",
                backend=Cv2Backends.V4L2,
                color_mode=ColorMode.RGB,
            )
        )

    context = zmq.Context()
    command = context.socket(zmq.PUSH)
    command.setsockopt(zmq.CONFLATE, 1)
    command.connect(f"tcp://{args.ip}:5555")
    observation = context.socket(zmq.PULL)
    observation.setsockopt(zmq.RCVHWM, 2)
    observation.connect(f"tcp://{args.ip}:5556")
    wrist_stream = None
    if args.practice_ui:
        wrist_stream = context.socket(zmq.SUB)
        wrist_stream.setsockopt(zmq.SUBSCRIBE, b"")
        wrist_stream.setsockopt(zmq.RCVHWM, 1)
        wrist_stream.setsockopt(zmq.CONFLATE, 1)
        wrist_stream.connect(f"tcp://{args.ip}:{args.wrist_port}")

    arm_goal = None
    try:
        poller = zmq.Poller()
        poller.register(observation, zmq.POLLIN)
        if observation not in dict(poller.poll(5000)):
            raise SystemExit("No LeKiwi host observation received within 5 seconds.")
        state = json.loads(observation.recv_multipart()[0])
        follower_start = {
            name: float(state[f"arm_{name}.pos"]) for name in JOINTS
        }
        arm_goal = dict(follower_start)
        with FOLLOWER_CALIBRATION.open() as file:
            follower_calibration = json.load(file)
        joint_bounds = {}
        for name in JOINTS[:-1]:
            entry = follower_calibration[name]
            half_range = (
                (entry["range_max"] - entry["range_min"]) * 180.0 / 4095.0
            )
            # Preserve a verified starting pose at an endpoint, but never allow
            # a command farther outside the recorded calibration range.
            joint_bounds[name] = (
                min(-half_range, follower_start[name]),
                max(half_range, follower_start[name]),
            )

        # Do not run or write calibration. The saved leader calibration is only
        # loaded to interpret its present positions.
        leader.connect(calibrate=False)
        if body_camera is not None:
            body_camera.connect()
        leader_start_action = leader.get_action()
        leader_start = {
            name: float(leader_start_action[f"{name}.pos"]) for name in JOINTS
        }

        print(f"Leader: {args.leader_port}")
        print(f"Gamepad: {gamepad.get_name()}")
        print("Leader controls arm 6 axes; left stick controls base only.")
        print("OPTIONS, window close, or Ctrl+C: stop base and exit.")
        input("두 팔과 베이스 주변을 비우고, 왼쪽 스틱을 놓은 뒤 ENTER: ")

        screen_size = (1280, 720) if args.practice_ui else (700, 240)
        screen = pygame.display.set_mode(screen_size)
        title = "LeKiwi PRACTICE - NOT RECORDING" if args.practice_ui else "LeKiwi Leader + Gamepad Teleoperation"
        pygame.display.set_caption(title)
        font = pygame.font.Font(None, 27)
        clock = pygame.time.Clock()
        last_time = time.monotonic()
        running = True
        wrist_rgb = None

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.JOYDEVICEREMOVED:
                    print("Gamepad disconnected.")
                    running = False

            if not running or gamepad.get_button(OPTIONS_BUTTON):
                break

            now = time.monotonic()
            dt = min(now - last_time, 0.1)
            last_time = now

            leader_action = leader.get_action()
            for name in JOINTS:
                requested = follower_start[name] + (
                    float(leader_action[f"{name}.pos"]) - leader_start[name]
                )
                if name == "gripper":
                    requested = min(100.0, max(0.0, requested))
                    max_step = args.gripper_speed * dt
                else:
                    lower, upper = joint_bounds[name]
                    requested = min(upper, max(lower, requested))
                    max_step = args.joint_speed * dt
                delta = min(max(requested - arm_goal[name], -max_step), max_step)
                arm_goal[name] += delta

            longitudinal = -apply_deadzone(
                gamepad.get_axis(LEFT_STICK_Y), args.deadzone
            )
            lateral = -apply_deadzone(
                gamepad.get_axis(LEFT_STICK_X), args.deadzone
            )
            x_velocity = y_velocity = theta_velocity = 0.0
            drive_label = "STOP"
            if longitudinal != 0.0 and lateral != 0.0:
                x_velocity = longitudinal * args.speed
                theta_velocity = longitudinal * lateral * args.turn_speed
                drive_label = "CURVE"
            elif longitudinal != 0.0:
                x_velocity = longitudinal * args.speed
                drive_label = "FORWARD" if longitudinal > 0 else "BACKWARD"
            elif lateral != 0.0:
                y_velocity = lateral * args.speed
                drive_label = "STRAFE LEFT" if lateral > 0 else "STRAFE RIGHT"

            send_action(
                command,
                arm_goal,
                x_velocity=x_velocity,
                y_velocity=y_velocity,
                theta_velocity=theta_velocity,
            )

            screen.fill((25, 25, 30))
            if args.practice_ui:
                body_rgb = body_camera.read()
                while wrist_stream.poll(timeout=0):
                    encoded = wrist_stream.recv()
                    decoded = cv2.imdecode(
                        np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                    if decoded is not None:
                        wrist_rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)

                body_surface = pygame.image.frombuffer(
                    body_rgb.tobytes(),
                    (body_rgb.shape[1], body_rgb.shape[0]),
                    "RGB",
                )
                body_surface = pygame.transform.smoothscale(body_surface, (640, 360))
                screen.blit(body_surface, (0, 0))
                if wrist_rgb is not None:
                    wrist_surface = pygame.image.frombuffer(
                        wrist_rgb.tobytes(),
                        (wrist_rgb.shape[1], wrist_rgb.shape[0]),
                        "RGB",
                    )
                    wrist_surface = pygame.transform.smoothscale(
                        wrist_surface, (640, 360)
                    )
                    screen.blit(wrist_surface, (640, 0))
                screen.blit(font.render("FRONT (C920)", True, (255, 255, 255)), (16, 8))
                wrist_label = "WRIST" if wrist_rgb is not None else "WRIST - WAITING FOR STREAM"
                screen.blit(font.render(wrist_label, True, (255, 255, 255)), (656, 8))
                text_top = 390
            else:
                text_top = 18
            lines = (
                "LEADER: follower arm 6 axes",
                "LEFT STICK: drive/strafe/curve (no arm control)",
                f"BASE {drive_label}: x={x_velocity:+.3f} y={y_velocity:+.3f} "
                f"theta={theta_velocity:+.1f}",
                "OPTIONS: stop base and quit",
                f"arm pan={arm_goal['shoulder_pan']:+.1f} "
                f"lift={arm_goal['shoulder_lift']:+.1f} "
                f"elbow={arm_goal['elbow_flex']:+.1f}",
            )
            for index, line in enumerate(lines):
                screen.blit(font.render(line, True, (235, 235, 235)), (22, text_top + index * 42))
            pygame.display.flip()
            clock.tick(LOOP_HZ)
    except KeyboardInterrupt:
        pass
    finally:
        if arm_goal is not None:
            for _ in range(6):
                send_action(command, arm_goal)
                time.sleep(0.05)
        if leader.is_connected:
            leader.disconnect()
        if body_camera is not None and body_camera.is_connected:
            body_camera.disconnect()
        pygame.quit()
        if wrist_stream is not None:
            wrist_stream.close()
        observation.close()
        command.close()
        context.term()
        print("Final base STOP sent. Integrated teleoperation ended.")


if __name__ == "__main__":
    main()
