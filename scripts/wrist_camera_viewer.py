#!/usr/bin/env python3
"""Display the Pi wrist-camera stream on the laptop; never opens motors."""

import argparse

import cv2
import numpy as np
import pygame
import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="10.42.0.2")
    parser.add_argument("--port", type=int, default=5560)
    args = parser.parse_args()

    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE, b"")
    subscriber.setsockopt(zmq.RCVHWM, 1)
    subscriber.setsockopt(zmq.CONFLATE, 1)
    subscriber.connect(f"tcp://{args.ip}:{args.port}")
    pygame.init()
    screen = None
    clock = pygame.time.Clock()
    print("Waiting for wrist camera. Press Q or Esc in the window to quit.")

    try:
        running = True
        while running:
            encoded = subscriber.recv()
            frame = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width = rgb.shape[:2]
            if screen is None:
                screen = pygame.display.set_mode((width, height))
                pygame.display.set_caption("LeKiwi Wrist Camera - Q/Esc to quit")
            surface = pygame.image.frombuffer(rgb.tobytes(), (width, height), "RGB")
            screen.blit(surface, (0, 0))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
            clock.tick(60)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        subscriber.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
