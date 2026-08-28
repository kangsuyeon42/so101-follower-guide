# SO-101 Leader로 Follower 조작하기

이 문서는 Ubuntu에서 SO-101 Leader 팔로 Follower 팔을 조작하는 과정을 처음부터
순서대로 설명한다. 명령은 특별한 설명이 없는 한 다음 폴더에서 실행한다.

```bash
conda activate lerobot
cd /home/suyeon/so101-follower-guide
```

이 문서에서 사용하는 포트는 다음과 같다.

```text
Leader   /dev/ttyACM1
Follower /dev/ttyACM0
```

USB를 다시 연결하면 번호가 바뀔 수 있다. 실행 전에 항상 다시 확인한다.

## 1. 팔과 모터 이름 알아두기

두 팔은 같은 모터 ID와 관절 이름을 사용한다.

```text
ID 1  shoulder_pan    베이스 좌우 회전
ID 2  shoulder_lift   어깨 위아래
ID 3  elbow_flex      팔꿈치 굽힘
ID 4  wrist_flex      손목 위아래
ID 5  wrist_roll      손목 회전
ID 6  gripper         그리퍼 열기/닫기
```

## 2. 포트 확인하기

```bash
ls -l /dev/ttyACM*
```

`/dev/ttyACM0`과 `/dev/ttyACM1`이 보여야 한다. 이 문서의 구성에서는 Leader가
`ACM1`, Follower가 `ACM0`이다. 둘 중 하나가 없다면 프로그램을 실행하지 말고
전원, USB 케이블과 포트 번호부터 확인한다.

## 3. 모터 ID와 토크 확인하기

다음 명령은 모터를 움직이지 않는다. 먼저 Leader를 확인한다.

```bash
python scripts/scan_motor_ids.py --port /dev/ttyACM1
python scripts/read_raw_positions.py --port /dev/ttyACM1
```

Follower도 확인한다.

```bash
python scripts/scan_motor_ids.py --port /dev/ttyACM0
python scripts/read_raw_positions.py --port /dev/ttyACM0
```

정상 조건은 다음과 같다.

- 두 팔 모두 ID 1~6이 응답한다.
- 모든 ID의 통신 오류가 `0` 또는 `STATUS OK`다.
- 모든 모터가 `TORQUE OFF`다.

`Input voltage error`가 나오면 실행을 반복하지 않는다. 해당 팔의 전원을 끄고
전원 커넥터와 USB 케이블을 다시 연결한 다음 위 명령부터 확인한다.

## 4. 캘리브레이션하기

이미 캘리브레이션 파일이 있고 입력값이 정상이라면 이 단계는 반복하지 않는다.

Leader 캘리브레이션:

```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM1 \
  --teleop.id=leader
```

저장 위치:

```text
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader.json
```

Follower 캘리브레이션:

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=follower
```

저장 위치:

```text
~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json
```

캘리브레이션의 `middle` 단계에서는 보기 좋은 홈 자세가 아니라 각 관절의 실제
가동범위 중앙에 둔다. 범위 기록 단계에서는 관절을 하나씩 움직인다. 구조물에
닿으면 억지로 밀지 않는다. `wrist_roll`을 제외한 관절에서 범위가 이유 없이
`0~4095` 전체로 기록되면 중앙 자세나 엔코더 경계 통과 여부를 다시 확인한다.

현재 Follower 캘리브레이션과 소프트 바닥 `z=-33.2mm`는 임의로 변경하지 않는다.

## 5. Leader 입력만 확인하기

Follower를 연결하거나 움직이지 않고 Leader 값만 확인한다.

```bash
python scripts/leader_input_dry_run.py --port /dev/ttyACM1
```

Leader를 손으로 천천히 움직였을 때 해당 관절 이름의 값이 변하는지 본다.
종료는 `Ctrl+C`다. Leader 토크는 계속 OFF인 것이 정상이다.

## 6. 두 팔의 공통 시작 자세 저장하기

두 팔을 실제로 같은 반접힘 자세에 둔다. 숫자가 같아야 하는 것이 아니라 베이스,
링크와 그리퍼의 실제 모양이 같아야 한다. 완전히 접힌 기계적 끝점보다는 관절이
움직일 여유가 있는 자세가 좋다.

Follower 자세를 먼저 저장한다.

```bash
python scripts/capture_follower_home_candidate.py --port /dev/ttyACM0
```

출력된 좌표와 실제 자세를 확인한 다음 Enter를 누른다. 저장 파일:

```text
config/follower_home_candidate.json
```

Leader를 Follower와 같은 실제 자세에 맞추고 저장한다.

```bash
python scripts/capture_leader_home_candidate.py \
  --port /dev/ttyACM1 \
  --overwrite
```

저장 파일:

```text
config/leader_home_candidate.json
```

Follower 홈의 그리퍼 높이를 계산한다.

```bash
python scripts/fk_home_candidate.py
```

마지막 `z` 값이 `-33.2mm`보다 높아야 한다. 프로그램을 실행할 때 나오는 URDF
중립 자세의 self-collision 경고는 현재 홈 자세가 충돌했다는 뜻은 아니다. 실제
팔의 간섭 여부는 눈으로도 확인한다.

## 7. 저장된 홈으로 이동하기

Follower 홈 복귀:

```bash
python scripts/move_to_home_candidate.py --port /dev/ttyACM0
```

Leader 홈 복귀:

```bash
python scripts/move_leader_to_home_candidate.py --port /dev/ttyACM1
```

두 스크립트 모두 현재 위치를 첫 Goal Position으로 기록한 뒤 토크를 켠다.
기본 최고속도는 몸통과 손목 `15 deg/s`, 그리퍼 `25 %/s`이며 smoothstep으로
출발과 정지를 부드럽게 만든다. 마지막 Enter를 누르면 토크가 풀리므로 팔을
받을 준비를 한다.

속도를 직접 지정할 수도 있다.

```bash
python scripts/move_to_home_candidate.py \
  --port /dev/ttyACM0 \
  --joint-speed 10 \
  --gripper-speed 20
```

## 8. 처음 조립한 팔을 단계별로 시험하기

이미 최종 텔레오퍼레이션을 정상 확인한 장치라면 이 단계는 생략할 수 있다.

### 베이스 한 관절

```bash
python scripts/leader_single_joint_test.py \
  --joint shoulder_pan \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

### 몸통 3축

```bash
python scripts/leader_body_3joint_test.py \
  --mode body \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

### 손목과 그리퍼

```bash
python scripts/leader_single_joint_test.py --joint wrist_flex
python scripts/leader_single_joint_test.py --joint wrist_roll
python scripts/leader_single_joint_test.py --joint gripper
```

각 시험에서는 처음에 약 1° 또는 아주 작은 개폐량만 움직인다. 반대 방향 이동,
진동, 큰 소음이나 예상하지 못한 관절 움직임이 있으면 `Ctrl+C`로 종료한다.

## 9. 6축 텔레오퍼레이션 실행하기

최종 실행 명령은 다음과 같다.

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0
```

팔을 LeKiwi처럼 기존 탁상 설치면보다 높은 곳에 장착하면, 기존 소프트 바닥
`z=-0.0332 m`가 정상적인 하강 동작을 막을 수 있다. 실제 설치 높이를 아직
측정하지 않았다면 주변과 차체를 완전히 비운 짧은 시험에서만 바닥 제한을 끈다.
관절 캘리브레이션 끝점 제한과 추종 오차 E-stop은 계속 유지된다.

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0 \
  --disable-soft-floor
```

팔 베이스 원점에서 실제 바닥까지의 수직 거리를 측정했다면, 아래처럼 바닥의
base-frame z 좌표를 미터 단위 음수로 지정하는 편이 더 안전하다.

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0 \
  --soft-floor-z-m -0.20
```

스크립트가 먼저 확인하는 항목:

- Leader와 Follower 포트가 서로 다른지
- 양쪽 ID 1~6의 토크가 모두 OFF인지
- Follower가 저장된 홈 근처에 있는지
- 두 캘리브레이션 파일과 URDF를 읽을 수 있는지

화면의 안내를 확인하고 Enter를 누르면 Follower 토크가 켜진다. 이때부터 몸통
3축, 손목 2축과 그리퍼를 모두 추종한다.

최종 텔레오퍼레이션 설정:

```text
몸통/손목 최고속도       30 deg/s
그리퍼 최고속도          60 %/s
홈 기준 추가 이동 제한   없음
Follower 관절 범위        기록된 캘리브레이션 범위
소프트 바닥              z=-33.2 mm
종료                      Ctrl+C
```

두 팔은 실행 순간의 자세를 각각 기준으로 상대 이동한다. 거울처럼 보이게 하려면
실행 전에 두 팔을 같은 실제 자세에 둔다. 관절별 캘리브레이션 숫자가 서로 달라도
실제 자세가 같고 이동 방향이 같으면 된다.

그리퍼는 Leader 홈 파일에 저장된 닫힘 값을 Follower `0%`에 대응하고 Leader
`100%`를 Follower `100%`에 대응한다.

## 10. 종료하기

터미널에서 다음 키를 누른다.

```text
Ctrl+C
```

정상 종료 시 다음 문구를 확인한다.

```text
Follower 토크 OFF
연결 종료
```

토크 해제 후 팔이 내려올 수 있으므로 Follower를 받는다. 오류가 발생해도
스크립트는 Follower 토크 해제를 시도한다.

## 자주 발생하는 문제

### `No such file or directory`

스크립트 이름과 현재 폴더를 확인한다.

```bash
pwd
ls scripts
```

예를 들어 정확한 파일명은 `read_raw_positions.py`처럼 `positions`가 복수형이다.

### `unrecognized arguments`

옵션 철자를 확인한다. 정확한 옵션은 다음과 같다.

```text
--leader-port
--follower-port
```

### Follower가 움직이지 않는다

먼저 터미널의 마지막 오류를 확인한다. Follower가 홈에서 3° 이상 떨어져 있으면
시작하지 않는다. 홈으로 이동한 뒤 다시 실행한다.

```bash
python scripts/move_to_home_candidate.py --port /dev/ttyACM0
```

### 특정 관절만 멈춘다

기록된 캘리브레이션 끝점이나 `z=-33.2mm` 바닥 제한에 도달했을 수 있다. 반대
방향으로 천천히 움직여 제한에서 벗어난다. 한 관절이 제한되어도 베이스,
`wrist_roll`과 그리퍼 등 관계없는 관절은 계속 추종한다.

### Leader가 토크 OFF에서 내려온다

Leader는 손으로 움직이는 입력 장치라 토크 OFF에서 중력으로 내려올 수 있다.
링크가 모터 축과 함께 부드럽게 내려온다면 나사를 조여 마찰을 만들지 않는다.
저장 자세로 잠시 고정하려면 다음 스크립트를 사용한다.

```bash
python scripts/move_leader_to_home_candidate.py --port /dev/ttyACM1
```

마지막 Enter를 누르기 전까지 Leader 토크가 홈 자세를 유지한다. 텔레오퍼레이션을
시작할 때는 Leader 토크가 OFF여야 한다.
