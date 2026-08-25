#!/usr/bin/env python3
"""Verify the wrist camera stream without connecting to any motors."""

import time
from pathlib import Path

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig


CAMERA_PATH = Path(
    "/dev/v4l/by-id/"
    "usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0"
)


if not CAMERA_PATH.exists():
    raise SystemExit(f"손목 카메라를 찾지 못했습니다: {CAMERA_PATH}")

camera = OpenCVCamera(
    OpenCVCameraConfig(
        index_or_path=CAMERA_PATH,
        width=1280,
        height=720,
        fps=30,
        fourcc="MJPG",
    )
)

try:
    camera.connect()
    started_at = time.monotonic()
    frame_count = 0
    frame = None
    while time.monotonic() - started_at < 5.0:
        frame = camera.read()
        frame_count += 1

    elapsed = time.monotonic() - started_at
    if frame is None:
        raise SystemExit("카메라 프레임을 읽지 못했습니다.")
    print(f"frame shape: {frame.shape}")
    print(f"frames: {frame_count}")
    print(f"measured fps: {frame_count / elapsed:.2f}")
finally:
    if camera.is_connected:
        camera.disconnect()
