#!/usr/bin/env python3
"""Find responsive Feetech motor IDs without moving the arm."""

import argparse

import scservo_sdk as scs

BAUDRATE = 1_000_000
FIRST_ID = 1
LAST_ID = 20


parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM0")
args = parser.parse_args()

port = scs.PortHandler(args.port)
if not port.openPort():
    raise SystemExit(f"Could not open {args.port}")

if not port.setBaudRate(BAUDRATE):
    port.closePort()
    raise SystemExit(f"Could not set baud rate to {BAUDRATE}")

packet = scs.PacketHandler(0)
found = []

try:
    for motor_id in range(FIRST_ID, LAST_ID + 1):
        model, result, error = packet.ping(port, motor_id)
        if result == scs.COMM_SUCCESS:
            found.append(motor_id)
            print(f"FOUND ID={motor_id}, model={model}, error={error}")
finally:
    port.closePort()

print("Motor IDs:", found if found else "no response")
