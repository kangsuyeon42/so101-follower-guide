#!/usr/bin/env python3
"""Publish the Pi wrist camera as low-latency JPEG frames; never opens motors."""

import argparse
import signal
from pathlib import Path

import cv2
import zmq

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.cameras.opencv.configuration_opencv import ColorMode, Cv2Backends


DEFAULT_CAMERA = Path(
    "/dev/v4l/by-id/"
    "usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0"
)


def camera_index_from_by_id(path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"Camera not found: {path}")
    resolved = path.resolve()
    if not resolved.name.startswith("video"):
        raise SystemExit(f"Unexpected camera device: {resolved}")
    return int(resolved.name.removeprefix("video"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=Path, default=DEFAULT_CAMERA)
    parser.add_argument("--port", type=int, default=5560)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    args = parser.parse_args()
    if not 1 <= args.jpeg_quality <= 100:
        parser.error("--jpeg-quality must be between 1 and 100")

    camera = OpenCVCamera(
        OpenCVCameraConfig(
            index_or_path=camera_index_from_by_id(args.camera),
            width=1280,
            height=720,
            fps=30,
            fourcc="MJPG",
            backend=Cv2Backends.V4L2,
            color_mode=ColorMode.RGB,
        )
    )
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.setsockopt(zmq.SNDHWM, 1)
    publisher.bind(f"tcp://*:{args.port}")
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        camera.connect()
        print(f"Wrist camera streaming on tcp://*:{args.port}. Ctrl+C stops.")
        while running:
            rgb = camera.read()
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            ok, encoded = cv2.imencode(
                ".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, args.jpeg_quality]
            )
            if ok:
                publisher.send(encoded.tobytes())
    finally:
        if camera.is_connected:
            camera.disconnect()
        publisher.close(linger=0)
        context.term()
        print("Wrist camera stream stopped.")


if __name__ == "__main__":
    main()
