# Scripts Reference

`scripts/`에 포함된 점검, 제어, 데이터 기록과 튜닝 도구 설명

모든 명령은 특별한 설명이 없으면 노트북의 프로젝트 루트에서 실행

```bash
conda activate lerobot
cd ~/so101-follower-guide
```

## 안전 표시

| 표시 | 의미 |
| --- | --- |
| 읽기 전용 | 모터 명령과 설정 변경 없이 상태만 확인 |
| 계산 전용 | 모터 포트를 열지 않고 로컬 파일과 URDF만 사용 |
| 파일 기록 | 모터는 움직이지 않지만 `config/` 또는 `outputs/`에 파일 생성 |
| 실기 구동 | 토크 활성화 또는 실제 팔·바퀴 움직임 발생 |
| 설정 변경 | 모터 레지스터 값 변경 |

실기 구동 전 로봇 주변 정리, 예상 동작 확인, 종료 방법 확인과 비상 전원 차단
경로 확보

## 전체 목록

| 파일 | 분류 | 역할 |
| --- | --- | --- |
| `scan_motor_ids.py` | 읽기 전용 | SO-101 Feetech ID 1~20 ping |
| `scan_lekiwi_motor_ids.py` | 읽기 전용 | LeKiwi 팔·바퀴 ID 1~9 ping |
| `read_raw_positions.py` | 읽기 전용 | SO-101 raw encoder와 torque 상태 출력 |
| `read_calibrated_positions.py` | 읽기 전용 | LeRobot 보정 좌표 출력 |
| `check_lekiwi_calibration_match.py` | 읽기 전용 | LeKiwi calibration 파일과 모터 레지스터 비교 |
| `inspect_motor_tuning.py` | 읽기 전용 | 가속도, 속도와 PID 레지스터 출력 |
| `fk_home_candidate.py` | 계산 전용 | 저장된 홈 자세의 FK와 gripper 위치 계산 |
| `ik_small_steps_dry_run.py` | 계산 전용 | 홈 기준 2 mm 이동의 IK 해 검증 |
| `inspect_gamepad_axes.py` | 계산 전용 | 15초 동안 전체 게임패드 축 raw 값 출력 |
| `gamepad_input_monitor.py` | 계산 전용 | 확인된 DualShock 4 입력 매핑 모니터링 |
| `gamepad_ik_dry_run.py` | 계산 전용 | 게임패드 입력부터 IK까지 모터 없이 검증 |
| `test_wrist_camera.py` | 카메라 전용 | Innomaker 손목 카메라 5초 스트림 점검 |
| `capture_follower_home_candidate.py` | 파일 기록 | 현재 Follower 자세를 홈 후보 JSON으로 저장 |
| `capture_leader_home_candidate.py` | 파일 기록 | 현재 Leader 자세를 홈 후보 JSON으로 저장 |
| `move_to_home_candidate.py` | 실기 구동 | Follower를 저장된 홈 자세로 저속 이동 |
| `move_leader_to_home_candidate.py` | 실기 구동 | Leader를 저장된 홈 자세로 저속 이동 |
| `move_both_to_home_candidates.py` | 실기 구동 | Leader와 Follower를 각 홈 자세로 동시 이동 |
| `leader_input_dry_run.py` | 읽기 전용 | Follower 없이 Leader 보정 입력 출력 |
| `leader_single_joint_test.py` | 실기 구동 | 선택한 한 관절의 제한된 Leader 추종 시험 |
| `leader_body_3joint_test.py` | 실기 구동/기록 | 몸통·전체 추종과 선택적 파일럿 데이터 기록 |
| `leader_teleoperation.py` | 실기 구동/기록 | 6축 텔레오퍼레이션 진입점 |
| `gamepad_forward_back_test.py` | 실기 구동 | 게임패드 기반 XYZ·손목·그리퍼 제어 |
| `start_lekiwi_host_no_cameras.sh` | 실기 구동 | 카메라 없는 LeKiwi Pi host 실행 |
| `lekiwi_forward_pulse_test.py` | 실기 구동 | 짧은 저속 전진 pulse 시험 |
| `lekiwi_cardinal_pulse_test.py` | 실기 구동 | 전후좌우 짧은 pulse 시험 |
| `lekiwi_keyboard_drive.py` | 실기 구동 | ZMQ 기반 dead-man WASD 주행 |
| `set_motor_acceleration.py` | 설정 변경 | SO-101 모터 Acceleration 레지스터 변경 |

## 1. 모터와 캘리브레이션 점검

### `scan_motor_ids.py`

SO-101 Follower 또는 Leader 포트에서 Feetech ID 1~20에 ping 전송. 모터 이동과
레지스터 쓰기 없음

```bash
python scripts/scan_motor_ids.py --port /dev/ttyACM0
python scripts/scan_motor_ids.py --port /dev/ttyACM1
```

정상 SO-101 arm: ID 1~6 응답

### `scan_lekiwi_motor_ids.py`

Pi의 안정적인 by-id 포트에서 LeKiwi ID 1~9 확인. 기본 baudrate `1,000,000`

```bash
python -u scripts/scan_lekiwi_motor_ids.py
```

선택 옵션:

```bash
python scripts/scan_lekiwi_motor_ids.py \
  --port /dev/serial/by-id/<device> \
  --baudrate 1000000 \
  --first-id 1 \
  --last-id 9
```

### `read_raw_positions.py`

ID 1~6의 raw encoder position, torque ON/OFF와 통신 상태 출력

```bash
python scripts/read_raw_positions.py --port /dev/ttyACM0
```

### `read_calibrated_positions.py`

LeRobot calibration을 적용한 Follower 좌표 출력. 관절은 degree, gripper는
percent 단위. 기본 포트 `/dev/ttyACM0`

```bash
python scripts/read_calibrated_positions.py
```

### `check_lekiwi_calibration_match.py`

저장된 LeKiwi calibration과 실제 모터의 `id`, `drive_mode`, `homing_offset`,
`range_min`, `range_max` 비교. 모터 레지스터 쓰기와 torque 변경 없음

```bash
python scripts/check_lekiwi_calibration_match.py
```

정상 출력:

```text
calibration_matches_motors: True
```

### `inspect_motor_tuning.py`

Follower의 `Acceleration`, `Goal_Velocity`, P/I/D coefficient raw 값 출력

```bash
python scripts/inspect_motor_tuning.py
```

## 2. 홈 자세 기록과 이동

### `capture_follower_home_candidate.py`

Torque OFF 상태의 현재 Follower 보정 좌표를 읽어
`config/follower_home_candidate.json`에 저장. 모터 레지스터와 torque 상태 변경
없음. Enter 확인 후 로컬 파일 교체

```bash
python scripts/capture_follower_home_candidate.py --port /dev/ttyACM0
```

### `capture_leader_home_candidate.py`

Torque OFF 상태의 현재 Leader 자세를 여러 번 샘플링해
`config/leader_home_candidate.json`에 저장. 기존 파일 교체에는 `--overwrite` 필요

```bash
python scripts/capture_leader_home_candidate.py \
  --port /dev/ttyACM1 \
  --overwrite
```

### `move_to_home_candidate.py`

현재 위치를 첫 Goal Position으로 설정한 뒤 torque 활성화. 저장된 Follower 홈
후보까지 smoothstep으로 저속 이동

```bash
python scripts/move_to_home_candidate.py \
  --port /dev/ttyACM0 \
  --joint-speed 15 \
  --gripper-speed 25
```

마지막 Enter 입력 시 torque 해제. 팔을 받을 준비 필요

### `move_leader_to_home_candidate.py`

Leader를 저장된 홈 후보로 저속 이동한 뒤 torque 해제

```bash
python scripts/move_leader_to_home_candidate.py \
  --port /dev/ttyACM1
```

### `move_both_to_home_candidates.py`

Leader와 Follower의 현재 위치를 먼저 읽고 각 홈 후보로 동시에 이동

```bash
python scripts/move_both_to_home_candidates.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

두 팔 모두 실제로 움직이므로 주변과 아래 공간 확인 필수

## 3. FK, IK와 게임패드 dry-run

### `fk_home_candidate.py`

`config/follower_home_candidate.json`과 SO-101 URDF를 이용해 홈 자세의 gripper
frame 위치 계산. 하드웨어 연결 없음

```bash
python scripts/fk_home_candidate.py
```

### `ik_small_steps_dry_run.py`

홈 자세에서 각 방향 2 mm 이동의 IK 결과와 관절 변화량 계산. 하드웨어 연결 없음

```bash
python scripts/ik_small_steps_dry_run.py
```

### `inspect_gamepad_axes.py`

연결된 첫 번째 게임패드의 모든 axis 값을 15초 동안 출력

```bash
python scripts/inspect_gamepad_axes.py
```

### `gamepad_input_monitor.py`

DualShock 4의 스틱, trigger와 button을 현재 제어 매핑 기준으로 출력

```bash
python scripts/gamepad_input_monitor.py
```

### `gamepad_ik_dry_run.py`

게임패드 입력, workspace 제한과 IK 결과를 20 Hz로 확인. `/dev/ttyACM0` 접근 없음

```bash
python scripts/gamepad_ik_dry_run.py
```

## 4. Leader/Follower 제어

### `leader_input_dry_run.py`

Follower를 연결하지 않고 SO-101 Leader의 보정 입력만 출력. 시작 전 ID 1~6의
torque OFF 상태 확인

```bash
python scripts/leader_input_dry_run.py \
  --port /dev/ttyACM1 \
  --hz 10
```

종료: `Ctrl+C`

### `leader_single_joint_test.py`

Leader 움직임을 Follower의 선택한 한 관절에 제한적으로 전달. 지원 관절:
`shoulder_pan`, `wrist_flex`, `wrist_roll`, `gripper`

```bash
python scripts/leader_single_joint_test.py \
  --joint shoulder_pan \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

작은 offset과 속도 제한이 적용된 초기 실기 검증용. 종료: `Ctrl+C`

### `leader_body_3joint_test.py`

Leader/Follower 추종의 실제 구현 파일. `--mode`에 따라 몸통 3축, 전체 6축 또는
최종 teleoperation 구성 선택. 홈 오차, 관절 범위, 소프트 바닥과 추종 오차
E-stop 포함

```bash
python scripts/leader_body_3joint_test.py \
  --mode body \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

데이터 기록 옵션:

```bash
python scripts/leader_body_3joint_test.py \
  --mode teleop \
  --record-one-episode \
  --episode-seconds 20 \
  --task "Pick up the object and place it to the right."
```

### `leader_teleoperation.py`

사용자용 6축 텔레오퍼레이션 진입점. 내부에서
`leader_body_3joint_test.py --mode teleop` 실행

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

기록 옵션은 그대로 전달 가능:

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0 \
  --record-one-episode \
  --episode-seconds 20 \
  --task "Pick up the object and place it to the right."
```

### `gamepad_forward_back_test.py`

파일명은 초기 앞뒤 시험에서 유지된 이름. 현재는 DualShock 4로 gripper XYZ,
wrist flex/roll과 gripper 개폐를 모두 제어. workspace, 속도, 관절 step, IK jump,
추종 오차와 soft floor 제한 포함

```bash
python scripts/gamepad_forward_back_test.py
```

Options 버튼: 즉시 torque 해제 후 종료

## 5. LeKiwi 베이스

LeKiwi client 스크립트 실행 전 Pi에서 host 실행 필요

### `start_lekiwi_host_no_cameras.sh`

안정적인 by-id 모터 포트와 빈 camera 설정으로 LeKiwi host 실행. client 명령이
없으면 base velocity를 0으로 만드는 500 ms watchdog 적용

Pi:

```bash
conda activate lerobot
bash ~/start_lekiwi_host_no_cameras.sh 600
```

첫 번째 인수는 최대 실행 시간(초). 시작 대기 시간 아님

### `lekiwi_forward_pulse_test.py`

현재 arm state를 유지하면서 x축에 최대 0.5초, 최대 `0.05 m/s`의 짧은 전진
명령 전송. 첫 물리 방향 검증용

```bash
python scripts/lekiwi_forward_pulse_test.py \
  --ip 10.42.0.2 \
  --speed 0.02 \
  --duration 0.3
```

### `lekiwi_cardinal_pulse_test.py`

전진, 후진, 왼쪽과 오른쪽 평행 이동을 짧은 pulse로 순서대로 시험. 각 동작
사이에 정지 명령과 pause 적용

```bash
python scripts/lekiwi_cardinal_pulse_test.py \
  --ip 10.42.0.2 \
  --speed 0.02 \
  --duration 0.3 \
  --pause 1.5
```

### `lekiwi_keyboard_drive.py`

Pygame 창의 키 상태를 ZMQ 9차원 action으로 전송. 키 입력이 없거나 창이
포커스를 잃으면 정지하는 dead-man 동작 포함

```bash
python scripts/lekiwi_keyboard_drive.py \
  --ip 10.42.0.2 \
  --speed 0.05 \
  --turn-speed 25
```

| 키 | 동작 |
| --- | --- |
| `W/A/S/D` | 전진/왼쪽/후진/오른쪽 |
| `W+A`, `W+D` | 전진하며 좌회전/우회전 |
| `S+A`, `S+D` | 후진하며 선회 |
| `Space` | 즉시 정지 |
| `Esc` | 정지 명령 후 종료 |

## 6. 카메라와 데이터

### `test_wrist_camera.py`

Innomaker 손목 카메라를 `1280×720`, `30 FPS`, `MJPG`로 연결해 5초 동안
프레임 수와 실측 FPS 확인. 모터 접근 없음

```bash
python scripts/test_wrist_camera.py
```

안정적인 카메라 경로:

```text
/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0
```

파일럿 에피소드 기록은 `leader_teleoperation.py`의
`--record-one-episode` 옵션 사용. 자세한 출력 구조는
[데이터 수집](../DATA_COLLECTION.md) 참고

## 7. 모터 설정 변경

### `set_motor_acceleration.py`

> 주의: 읽기 전용 도구가 아닌 모터 레지스터 변경 스크립트

몸통과 손목 모터 Acceleration을 `50`, gripper를 `20`으로 변경. 기존 값과
변경 예정 값을 출력하고 Enter 확인 후 적용

```bash
python scripts/set_motor_acceleration.py
```

현재 장치에서는 가속도 `3 → 8 → 50` 변경에도 체감 진동 개선이 거의 없었음.
반복 실행이나 추가 PID 변경보다 [게임패드 제어](../GAMEPAD_CONTROL.md)의 튜닝
기록을 먼저 확인
