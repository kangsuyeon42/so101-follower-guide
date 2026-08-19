#!/usr/bin/env python3
"""Read raw encoder positions without sending movement commands."""

import argparse

import scservo_sdk as scs

BAUDRATE = 1_000_000
MOTORS = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}


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

try:
    print(f"{'ID':>2}  {'JOINT':14s}  {'RAW':>5}  {'TORQUE':>6}  STATUS")
    for motor_id, joint in MOTORS.items():
        raw, result, error = packet.read2ByteTxRx(port, motor_id, 56)
        torque, torque_result, torque_error = packet.read1ByteTxRx(port, motor_id, 40)
        position_ok = result == scs.COMM_SUCCESS and error == 0
        torque_ok = torque_result == scs.COMM_SUCCESS and torque_error == 0
        ok = position_ok and torque_ok
        status = "OK" if ok else (
            f"position=({result},{error}), torque=({torque_result},{torque_error})"
        )
        torque_label = "ON" if torque else "OFF"
        print(f"{motor_id:2d}  {joint:14s}  {raw:5d}  {torque_label:>6}  {status}")
finally:
    port.closePort()
