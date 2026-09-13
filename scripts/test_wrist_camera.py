#!/usr/bin/env python3
"""Verify the wrist camera stream without connecting to any motors."""

import time
from pathlib import Path

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.cameras.opencv.configuration_opencv import Cv2Backends


CAMERA_PATH = Path(
    "/dev/v4l/by-id/"
    "usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0"
)


if not CAMERA_PATH.exists():
    raise SystemExit(f"손목 카메라를 찾지 못했습니다: {CAMERA_PATH}")

resolved_camera = CAMERA_PATH.resolve()
if not resolved_camera.name.startswith("video"):
    raise SystemExit(f"예상하지 못한 카메라 장치 경로입니다: {resolved_camera}")
camera_index = int(resolved_camera.name.removeprefix("video"))

camera = OpenCVCamera(
    OpenCVCameraConfig(
        # Discover the camera through its persistent by-id symlink, then pass
        # its videoN number to OpenCV. This Pi OpenCV build accepts V4L2 camera
        # indices but cannot open a V4L2 device by filename.
        index_or_path=camera_index,
        width=1280,
        height=720,
        fps=30,
        fourcc="MJPG",
        backend=Cv2Backends.V4L2,
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
