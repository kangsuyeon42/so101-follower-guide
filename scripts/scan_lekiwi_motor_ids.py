#!/usr/bin/env python3
"""Ping LeKiwi arm and wheel motor IDs without writing motor settings."""

import argparse
from pathlib import Path

import scservo_sdk as scs


DEFAULT_PORT = (
    "/dev/serial/by-id/"
    "usb-1a86_USB_Single_Serial_5AAF263511-if00"
)


parser = argparse.ArgumentParser()
parser.add_argument("--port", default=DEFAULT_PORT)
parser.add_argument("--baudrate", type=int, default=1_000_000)
parser.add_argument("--first-id", type=int, default=1)
parser.add_argument("--last-id", type=int, default=9)
args = parser.parse_args()

if args.baudrate <= 0:
    parser.error("--baudrate는 0보다 커야 합니다.")
if not 0 <= args.first_id <= args.last_id < scs.BROADCAST_ID:
    parser.error("ID 범위가 올바르지 않습니다.")
if not Path(args.port).exists():
    raise SystemExit(f"모터 포트를 찾지 못했습니다: {args.port}")

port = scs.PortHandler(args.port)
packet = scs.PacketHandler(0)

if not port.openPort():
    raise SystemExit(f"포트를 열 수 없습니다: {args.port}")
if not port.setBaudRate(args.baudrate):
    port.closePort()
    raise SystemExit(f"baudrate 설정 실패: {args.baudrate}")

found = []
try:
    print(f"port: {args.port}")
    print(f"baudrate: {args.baudrate}")
    print("ID  MODEL  STATUS")
    for motor_id in range(args.first_id, args.last_id + 1):
        model, result, error = packet.ping(port, motor_id)
        ok = result == scs.COMM_SUCCESS and error == 0
        if ok:
            found.append(motor_id)
            status = "OK"
        else:
            status = f"result={result}, error={error}"
        print(f"{motor_id:2d}  {model:5d}  {status}")
finally:
    port.closePort()

print(f"\n응답한 모터 ID: {found}")
missing = [
    motor_id
    for motor_id in range(args.first_id, args.last_id + 1)
    if motor_id not in found
]
print(f"응답하지 않은 모터 ID: {missing}")
