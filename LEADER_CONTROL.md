# Leader 추종

Leader 입력은 raw encoder 값을 follower에 직접 복사하지 않고, 각 팔의 캘리브레이션을 거친 degree/percent 좌표로 전달한다.

## 입력만 확인

```bash
python scripts/leader_input_dry_run.py --port /dev/ttyACM1
```

이 스크립트는 follower에 연결하지 않고 leader의 보정된 관절 입력만 출력한다.

## 단일 관절 추종

```bash
python scripts/leader_single_joint_test.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

현재 시험은 `shoulder_pan`만 사용한다. 시작 전 양쪽 포트와 토크 상태를 확인하고, follower의 현재 자세를 첫 목표로 기록한 뒤 토크를 켠다. Leader 이동은 시작점 기준 ±2°, follower 속도는 1°/s로 제한된다. 오류나 Ctrl+C 발생 시 follower 토크 해제를 시도한다.

확장은 몸통 3축, 손목 2축, 그리퍼 순서로 진행한다. 기존 follower 캘리브레이션과 홈 후보는 변경하지 않는다.
