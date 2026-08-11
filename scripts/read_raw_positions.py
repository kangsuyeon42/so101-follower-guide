#!/usr/bin/env python3
"""Read raw encoder positions without sending movement commands."""

import scservo_sdk as scs

PORT = "/dev/ttyACM0"
BAUDRATE = 1_000_000
MOTORS = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}


port = scs.PortHandler(PORT)
if not port.openPort():
    raise SystemExit(f"Could not open {PORT}")

if not port.setBaudRate(BAUDRATE):
    port.closePort()
    raise SystemExit(f"Could not set baud rate to {BAUDRATE}")

servo = scs.sms_sts(port)

try:
    print(f"{'ID':>2}  {'JOINT':14s}  {'RAW':>5}  STATUS")
    for motor_id, joint in MOTORS.items():
        raw, result, error = servo.read2ByteTxRx(motor_id, 56)
        ok = result == scs.COMM_SUCCESS and error == 0
        status = "OK" if ok else f"result={result}, error={error}"
        print(f"{motor_id:2d}  {joint:14s}  {raw:5d}  {status}")
finally:
    port.closePort()

