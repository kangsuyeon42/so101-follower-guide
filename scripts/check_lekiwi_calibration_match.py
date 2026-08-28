#!/usr/bin/env python3
"""Check whether LeKiwi's saved calibration matches its motor registers.

This script only opens the motor bus and reads calibration registers. It does
not enable/disable torque or write positions, IDs, or calibration values.
"""

import argparse
from pathlib import Path

from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
from lerobot.robots.lekiwi.lekiwi import LeKiwi


DEFAULT_PORT = (
    "/dev/serial/by-id/"
    "usb-1a86_USB_Single_Serial_5AAF263511-if00"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--robot-id", default="follower")
    args = parser.parse_args()

    if not Path(args.port).exists():
        raise SystemExit(f"Motor port not found: {args.port}")

    config = LeKiwiConfig(
        id=args.robot_id,
        port=args.port,
        cameras={},
    )
    robot = LeKiwi(config)
    robot.bus.connect()
    try:
        actual = robot.bus.read_calibration()
        print(f"calibration_file: {robot.calibration_fpath}")
        matches = actual == robot.calibration
        print(f"calibration_matches_motors: {matches}")

        if not matches:
            print("\nMismatched calibration fields:")
            fields = ("id", "drive_mode", "homing_offset", "range_min", "range_max")
            for motor in robot.bus.motors:
                expected = robot.calibration.get(motor)
                observed = actual.get(motor)
                if expected is None or observed is None:
                    print(f"- {motor}: file={expected}, motor={observed}")
                    continue
                differences = [
                    f"{field}: file={getattr(expected, field)}, motor={getattr(observed, field)}"
                    for field in fields
                    if getattr(expected, field) != getattr(observed, field)
                ]
                if differences:
                    print(f"- {motor}")
                    for difference in differences:
                        print(f"    {difference}")
    finally:
        robot.bus.disconnect(disable_torque=False)


if __name__ == "__main__":
    main()
