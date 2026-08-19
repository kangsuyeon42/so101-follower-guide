#!/usr/bin/env python3
"""Capture a calibrated leader pose without connecting to the follower."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scservo_sdk as scs

from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_DIR / "config" / "leader_home_candidate.json"
MOTOR_IDS = range(1, 7)
TORQUE_ENABLE_ADDRESS = 40
SAMPLE_COUNT = 10


parser = argparse.ArgumentParser()
parser.add_argument("--port", default="/dev/ttyACM1")
parser.add_argument("--id", default="leader")
parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
parser.add_argument("--overwrite", action="store_true")
args = parser.parse_args()

if args.output.exists() and not args.overwrite:
    raise SystemExit(f"이미 파일이 있습니다: {args.output} (--overwrite로 교체)")

# Check torque with the SDK before opening LeRobot's calibrated bus.
port = scs.PortHandler(args.port)
if not port.openPort():
    raise SystemExit(f"포트를 열 수 없습니다: {args.port}")
if not port.setBaudRate(1_000_000):
    port.closePort()
    raise SystemExit("baudrate 설정 실패: 1000000")

packet = scs.PacketHandler(0)
try:
    torque_states = {}
    for motor_id in MOTOR_IDS:
        torque, result, error = packet.read1ByteTxRx(
            port, motor_id, TORQUE_ENABLE_ADDRESS
        )
        if result != scs.COMM_SUCCESS or error != 0:
            raise SystemExit(f"motor ID {motor_id} 토크 상태 읽기 실패")
        torque_states[motor_id] = torque
finally:
    port.closePort()

if any(torque_states.values()):
    enabled = [motor_id for motor_id, state in torque_states.items() if state]
    raise SystemExit(f"Leader 토크가 ON인 모터가 있습니다: {enabled}")

leader = SO101Leader(
    SO101LeaderConfig(port=args.port, id=args.id, use_degrees=True)
)

try:
    # Avoid SO101Leader.connect(), which also writes motor configuration.
    leader.bus.connect()
    print("Follower를 기존 홈에 두고 leader를 같은 실제 자세로 맞추세요.")
    input("Leader 자세가 맞으면 ENTER를 눌러 홈 후보를 기록합니다: ")

    samples = []
    for _ in range(SAMPLE_COUNT):
        action = leader.get_action()
        samples.append(
            {name.removesuffix(".pos"): float(value) for name, value in action.items()}
        )

    position = {
        name: float(np.median([sample[name] for sample in samples]))
        for name in samples[0]
    }
finally:
    if leader.is_connected:
        leader.bus.disconnect(disable_torque=False)

payload = {
    "name": "leader_home_candidate",
    "teleoperator_type": "so101_leader",
    "teleoperator_id": args.id,
    "port_at_capture": args.port,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "units": {"body_joints": "degrees", "gripper": "percent"},
    "position": position,
}

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, indent=2) + "\n")
print(f"Leader 홈 후보 저장: {args.output}")
for name, value in position.items():
    unit = "%" if name == "gripper" else "deg"
    print(f"  {name:14s}: {value:+8.3f} {unit}")
