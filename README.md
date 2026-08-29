# SO-101 + LeKiwi Mobile Manipulation

SO-101 Leader/Follower와 LeKiwi를 결합한 모바일 매니퓰레이션 프로젝트

목표: LeKiwi로 물체까지 이동 → SO-101 팔로 물체 파지 → 오른쪽에 배치

> Drive to the object, pick it up, and place it to the right.

## 프로젝트 범위

- SO-101 Leader를 이용한 Follower 6축 텔레오퍼레이션
- LeKiwi 옴니휠 베이스의 `x.vel`, `y.vel`, `theta.vel` 제어
- 손목 카메라와 전면 카메라를 이용한 시각 관측
- 팔 6축과 베이스 3축을 합친 공식 LeKiwi 9차원 action/state
- 자연어 작업 문장이 포함된 LeRobotDataset 수집 및 검증
- `lerobot/smolvla_base` 파인튜닝

## 시스템 구성

| 장치 | 역할 |
| --- | --- |
| Raspberry Pi 5 | LeKiwi 바퀴, Follower arm, 카메라, LeKiwi host |
| 노트북 | Leader arm, LeKiwi client, 데이터 저장 |
| GPU PC 또는 서버 | SmolVLA 파인튜닝 |

노트북과 Raspberry Pi Ethernet 직접 연결

```text
노트북  10.42.0.1
Pi      10.42.0.2
SSH     ssh moai5@10.42.0.2
```

## 현재 상태

- SO-101 Leader/Follower 6축 텔레오퍼레이션 검증 완료
- 손목 카메라 파일럿 에피소드 기록 검증 완료
- LeKiwi 모터 ID 1~9와 캘리브레이션 정합성 확인 완료
- 물리적 앞 방향에 맞춘 action/state x축 패치 적용 완료
- Pi host와 노트북 client를 이용한 키보드 주행 검증 완료
- 다음 단계: 손목 카메라를 포함한 LeKiwi 통합 텔레오퍼레이션

## 문서 안내

| 문서 | 내용 |
| --- | --- |
| [Follower 설정](FOLLOWER_SETUP.md) | 독립형 Follower 연결, 모터 확인, 캘리브레이션과 홈 자세 |
| [Leader/Follower 제어](LEADER_CONTROL.md) | Leader 입력 확인, 두 팔 정렬과 6축 텔레오퍼레이션 |
| [게임패드 제어](GAMEPAD_CONTROL.md) | IK 기반 Follower 조작과 제어 튜닝 기록 |
| [LeKiwi 키보드 주행](LEKIWI_KEYBOARD_DRIVE.md) | Pi host, 노트북 client와 WASD 주행 |
| [데이터 수집](DATA_COLLECTION.md) | 손목 카메라 점검과 파일럿 에피소드 기록 |
| [다음 세션 인수인계](NEXT_SESSION_PROMPT.md) | 검증된 환경, 장치 상태와 다음 작업 시작점 |

## 빠른 시작

### SO-101 Leader/Follower

실행 전 두 팔의 포트, 자세와 토크 상태 확인. 초기 설정은
[Leader/Follower 제어](LEADER_CONTROL.md)를 위에서부터 순서대로 진행

```bash
conda activate lerobot
cd ~/so101-follower-guide
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

종료: `Ctrl+C`. Follower 토크 해제에 대비해 팔을 받을 준비

### LeKiwi 키보드 주행

Pi에서 host 먼저 실행

```bash
conda activate lerobot
bash ~/start_lekiwi_host_no_cameras.sh 600
```

노트북의 새 터미널에서 client 실행

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_keyboard_drive.py
```

- 이동: `W/A/S/D`
- 즉시 정지: `Space`
- 정지 명령 후 client 종료: `Esc`
- 자세한 조작법과 축 패치: [LeKiwi 키보드 주행](LEKIWI_KEYBOARD_DRIVE.md)

## 데이터 수집 방향

최종 LeRobotDataset에 같은 프레임 기준으로 기록할 항목

- 손목 및 전면 카메라 observation
- SO-101 팔 6축 action/state
- LeKiwi 베이스 `x.vel`, `y.vel`, `theta.vel`
- 자연어 작업 문장

- 목표: 고품질 통합 에피소드 50개 이상
- 최초 10개: 정책 학습보다 데이터 구조, 영상, 타임스탬프와
  observation/action 정합성 검증에 사용

## 안전 원칙

- Raspberry Pi 전원과 12V 모터 전원 분리
- 확인되지 않은 전압, 극성과 전원 분배선 연결 금지
- 모터 ID 변경 및 기존 캘리브레이션 덮어쓰기 금지
- 실제 팔이나 바퀴 구동 전 예상 동작과 종료 방법 확인
- 카메라 연결 후 Pi 재부팅 또는 Ethernet 단절 시 반복 재연결 금지
- 현재 전원 구성에서 RealSense와 다른 USB 카메라 동시 연결 금지

## 주요 환경

- Ubuntu 24.04
- Python 3.12.13
- LeRobot 0.6.2
- Raspberry Pi 5
- SO-101 Leader/Follower
- LeKiwi

프로젝트 경로와 상세 장치 상태: [다음 세션 인수인계](NEXT_SESSION_PROMPT.md)
