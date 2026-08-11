#!/usr/bin/env python3
"""Find responsive Feetech motor IDs without moving the arm."""

import scservo_sdk as scs

PORT = "/dev/ttyACM0"
BAUDRATE = 1_000_000
FIRST_ID = 1
LAST_ID = 20


port = scs.PortHandler(PORT)
if not port.openPort():
    raise SystemExit(f"Could not open {PORT}")

if not port.setBaudRate(BAUDRATE):
    port.closePort()
    raise SystemExit(f"Could not set baud rate to {BAUDRATE}")

servo = scs.sms_sts(port)
found = []

try:
    for motor_id in range(FIRST_ID, LAST_ID + 1):
        model, result, error = servo.ping(motor_id)
        if result == scs.COMM_SUCCESS:
            found.append(motor_id)
            print(f"FOUND ID={motor_id}, model={model}, error={error}")
finally:
    port.closePort()

print("Motor IDs:", found if found else "no response")

