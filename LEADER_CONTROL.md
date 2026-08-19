# Leader 추종

Leader 입력은 raw encoder 값을 follower에 직접 복사하지 않고, 각 팔의 캘리브레이션을 거친 degree/percent 좌표로 전달한다.

## Leader 캘리브레이션

Leader 포트와 전체 모터의 토크가 OFF인지 확인한 뒤 follower와 다른 전용 ID로 캘리브레이션한다.

```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM1 \
  --teleop.id=leader
```

안내에 따라 관절을 중앙에 놓고, 각 관절을 물리적 충돌이 없는 범위에서 천천히 움직여 가동범위를 기록한다. 결과는 아래 파일에 저장된다.

```text
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader.json
```

## 입력만 확인

```bash
python scripts/leader_input_dry_run.py --port /dev/ttyACM1
```

이 스크립트는 follower에 연결하지 않고 leader의 보정된 관절 입력만 출력한다.

## 홈 후보 기록

공통 시작 자세는 `config/teleop_home_candidate.json`에 정의되어 있다. Follower를 기존 홈 후보에 두고 leader를 실제로 같은 자세에 맞춘 뒤 leader 좌표를 별도로 기록한다.

```bash
python scripts/capture_leader_home_candidate.py --port /dev/ttyACM1
```

결과는 `config/leader_home_candidate.json`에 저장된다. 기존 파일은 `--overwrite`를 명시하지 않으면 교체하지 않는다.

## 단일 관절 추종

```bash
python scripts/leader_single_joint_test.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

현재 시험은 `shoulder_pan`만 사용한다. 시작 전 양쪽 포트와 토크 상태를 확인하고, follower의 현재 자세를 첫 목표로 기록한 뒤 토크를 켠다. Leader 이동은 시작점 기준 ±2°, follower 속도는 1°/s로 제한된다. 오류나 Ctrl+C 발생 시 follower 토크 해제를 시도한다.

확장은 몸통 3축, 손목 2축, 그리퍼 순서로 진행한다. 기존 follower 캘리브레이션과 홈 후보는 변경하지 않는다.
