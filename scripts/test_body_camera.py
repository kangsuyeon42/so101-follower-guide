#!/usr/bin/env python3
"""Display the laptop-connected body camera without opening any motors."""

from pathlib import Path

import pygame

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.cameras.opencv.configuration_opencv import ColorMode, Cv2Backends


CAMERA_PATH = Path(
    "/dev/v4l/by-id/"
    "usb-046d_HD_Pro_Webcam_C920_2F21131F-video-index0"
)


def camera_index_from_by_id(path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"Body camera not found: {path}")
    resolved = path.resolve()
    if not resolved.name.startswith("video"):
        raise SystemExit(f"Unexpected camera device: {resolved}")
    return int(resolved.name.removeprefix("video"))


def main() -> None:
    camera = OpenCVCamera(
        OpenCVCameraConfig(
            index_or_path=camera_index_from_by_id(CAMERA_PATH),
            width=1280,
            height=720,
            fps=30,
            fourcc="MJPG",
            backend=Cv2Backends.V4L2,
            color_mode=ColorMode.RGB,
        )
    )

    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    pygame.display.set_caption("LeKiwi Body Camera - Q/Esc to quit")
    clock = pygame.time.Clock()

    try:
        camera.connect()
        print("Body camera preview started. Press Q or Esc in the window to quit.")
        running = True
        while running:
            rgb = camera.read()
            height, width = rgb.shape[:2]
            surface = pygame.image.frombuffer(rgb.tobytes(), (width, height), "RGB")
            screen.blit(surface, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_q,
                    pygame.K_ESCAPE,
                ):
                    running = False
            clock.tick(60)
    except KeyboardInterrupt:
        pass
    finally:
        if camera.is_connected:
            camera.disconnect()
        pygame.quit()
        print("Body camera preview stopped.")


if __name__ == "__main__":
    main()
