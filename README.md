# SO-101 

이 문서는 Ubuntu PC에 Feetech USB 컨트롤러와 SO-101 follower 팔 한 대를 연결한 뒤 다음 상태까지 확인하는 과정이다.

- Ubuntu에서 USB 직렬 포트 접근
- 모터 ID 1~6 확인
- LeRobot 캘리브레이션
- 현재 관절 좌표 읽기
- 저속으로 관절 하나씩 시험
- 마음에 드는 대기 자세를 홈 후보로 기록

leader 팔은 없어도 된다. 게임패드 제어를 붙이기 전 follower 팔 자체를 점검하는 과정이다.

## 준비물

- 조립된 SO-101 follower 팔
- Feetech USB 컨트롤러
- 모터용 전원
- 데이터 통신이 가능한 USB 케이블
- Ubuntu PC
- Python 또는 Conda 환경
- LeRobot 저장소와 `lerobot` 환경

팔 주변을 비우고 USB 케이블이 관절 움직임에 당겨지지 않게 둔다. 물리적 끝에 닿은 관절을 억지로 더 밀지 않는다.

## 1. USB 포트 권한 설정

Ubuntu에서 USB 직렬 장치는 보통 `dialout` 그룹만 사용할 수 있다.

```bash
sudo usermod -aG dialout "$USER"
```

이 명령을 실행한 뒤에는 완전히 로그아웃했다가 다시 로그인한다. 재부팅해도 된다.

```bash
groups
```

출력에 `dialout`이 있어야 한다. 현재 터미널에서만 임시로 적용하려면 다음 명령을 사용할 수 있다.

```bash
newgrp dialout
```

## 2. 포트 확인

컨트롤러를 연결하고 확인한다.

```bash
ls -l /dev/ttyACM* /dev/ttyUSB*
```

이 구성에서는 다음과 같이 잡혔다.

```text
crw-rw---- 1 root dialout ... /dev/ttyACM0
```

`/dev/ttyUSB*`가 없다는 메시지는 문제가 아니다. 장치가 `/dev/ttyACM0`으로 나타났으면 그 포트를 사용하면 된다.

장치가 전혀 나타나지 않으면 권한 문제가 아니라 USB 인식 문제일 가능성이 크다. 케이블, 전원, 컨트롤러 연결을 먼저 확인한다.

## 3. Feetech Python SDK 설치

Python import 이름은 `scservo_sdk`지만 PyPI 패키지 이름은 다르다.

```bash
python -m pip install ftservo-python-sdk
```

`pip install scservo-sdk`는 다음 오류가 난다.

```text
No matching distribution found for scservo-sdk
```

설치 확인:

```bash
python -c 'import scservo_sdk; print(scservo_sdk.__file__)'
```

포트를 열 수 있는지 확인한다.

```bash
python -u -c 'import scservo_sdk as s; p=s.PortHandler("/dev/ttyACM0"); print(p.openPort()); p.closePort()'
```

`True`가 나오면 PC에서 USB 컨트롤러까지의 연결과 권한은 정상이다. 아직 모터 응답을 확인한 것은 아니다.

## 4. 모터 ID 확인

모터 전원을 켠 뒤 다음 스크립트를 실행한다. 이 작업은 ping만 보내며 모터를 움직이지 않는다.

```bash
python scripts/scan_motor_ids.py
```

정상적으로 설정된 6축 follower 팔에서는 ID 1~6이 응답해야 한다.

```text
ID 1: shoulder_pan
ID 2: shoulder_lift
ID 3: elbow_flex
ID 4: wrist_flex
ID 5: wrist_roll
ID 6: gripper
```

이번 팔에서는 여섯 모터 모두 모델 번호 `777`, 오류 `0`으로 응답했다.

## 5. Raw 위치 읽기

캘리브레이션 전에도 모터 엔코더의 현재 값을 읽을 수 있다.

```bash
python scripts/read_raw_positions.py
```

STS3215 위치는 대략 `0~4095` 범위다. 숫자만으로 관절 각도나 정면 방향을 알 수는 없다. 조립 방향과 모터별 offset이 다르기 때문이다.

## 6. LeRobot 캘리브레이션

LeRobot 환경을 활성화하고 저장소로 이동한다.

```bash
conda activate lerobot
cd ~/lerobot
```

follower 팔 캘리브레이션을 시작한다.

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=follower
```

`follower`라는 ID는 캘리브레이션 파일 이름에 사용된다. 이후 읽기, 조작, 녹화에서도 같은 ID를 써야 한다.

### 중앙 자세

프로그램이 다음 문구에서 기다린다.

```text
Move follower SOFollower to the middle of its range of motion and press ENTER....
```

여기서 중앙은 팔 전체가 예쁘게 보이는 대기 자세가 아니다. 각 관절을 자기 가동범위 중간쯤에 두는 것이다.

- 베이스는 정면
- 어깨는 너무 눕거나 세우지 않기
- 팔꿈치는 완전히 펴거나 접지 않기
- 손목은 위아래 중간, 비틀리지 않게
- 그리퍼는 반쯤 열기

자세를 잡고 Enter를 누른다.

### 가동범위 기록

다음 안내가 나오면 관절을 손으로 하나씩 양쪽 끝 근처까지 천천히 움직인다.

```text
Move all joints except 'wrist_roll' sequentially through their entire ranges of motion.
Recording positions. Press ENTER to stop...
```

움직일 관절:

1. `shoulder_pan`: 베이스 좌우
2. `shoulder_lift`: 어깨 위아래
3. `elbow_flex`: 팔꿈치 펴기와 접기
4. `wrist_flex`: 손목 위아래
5. `gripper`: 완전히 열기와 닫기

`wrist_roll`은 움직이지 않아도 된다. LeRobot이 전체 범위 `0~4095`를 사용한다.

구조물과 부딪혀 더 움직일 수 없다면 억지로 밀지 않는다. 팔꿈치나 손목 자세를 바꿔 공간을 만든 뒤 해당 관절의 범위를 확인한다.

모두 기록한 뒤 Enter를 누르면 다음 위치에 저장된다.

```text
~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json
```

### 기록 중 USB가 끊겼다면

팔을 움직이다 케이블이 당겨지면 다음과 비슷한 오류가 날 수 있다.

```text
SerialException: device reports readiness to read but returned no data
```

저장 전에 끊겼다면 캘리브레이션 파일이 만들어지지 않는다. 케이블에 여유를 주고 `/dev/ttyACM0`이 다시 보이는지 확인한 뒤 처음부터 다시 실행한다.

## 7. 캘리브레이션 좌표 읽기

```bash
conda activate lerobot
python scripts/read_calibrated_positions.py
```

몸통 관절은 degree, 그리퍼는 percent로 표시한다. 모터를 움직이지 않는 읽기 전용 스크립트다.

LeRobot의 `0°`는 보기 좋은 기본 자세가 아니다. 기록된 `range_min`과 `range_max`의 수학적 중간이다.

```text
raw encoder → homing offset 및 범위 적용 → degree 또는 percent
```

따라서 모든 관절을 무조건 `0°`로 보내지 않는다. 여러 관절이 동시에 크게 움직이며 자기 충돌이 생길 수 있다.

## 8. 대기 자세 정하기

보관 자세와 조작 대기 자세는 다르게 잡는 편이 좋다.

- 보관 및 전원 OFF: 작게 접고 무게중심을 낮게
- 게임패드 조작 대기: 베이스 정면, 팔꿈치 약 90도, 팔을 살짝 든 반접힘 자세

이번에는 관절을 한 번에 움직이지 않았다. 베이스, 어깨, 손목, 그리퍼 순서로 작은 각도만 저속 이동하고 매번 실제 모습을 확인했다.

최종 후보 자세는 다음 파일에 기록했다.

```text
config/follower_home_candidate.json
```

이 값은 아래의 안전한 홈 복귀 스크립트에서 사용한다.

## 9. 홈 후보로 천천히 복귀하기

팔 베이스를 책상에 단단히 고정하고 팔 아래를 비운다. 다음 스크립트는 현재 위치를 먼저 읽고, 그 위치를 목표값으로 기록한 뒤 토크를 켠다. 오래된 모터 목표값으로 갑자기 움직이는 것을 막기 위한 순서다.

```bash
python scripts/move_to_home_candidate.py
```

홈 후보까지 부드러운 보간으로 이동한 뒤 실제 도착 위치와 오차를 출력한다. 자세를 확인할 때까지 토크를 유지하며, 마지막 Enter를 누르면 토크를 해제한다. 토크가 풀리면 팔이 내려올 수 있으므로 반드시 팔을 받을 준비를 한다.

기록된 홈 후보:

```text
shoulder_pan   -11.165 deg
shoulder_lift  -64.923 deg
elbow_flex     +66.198 deg
wrist_flex     +73.187 deg
wrist_roll      -2.857 deg
gripper        +29.774 %
```

## 10. 게임패드와 IK 준비

사용한 게임패드는 `Sony Interactive Entertainment Wireless Controller`, pygame 버전은 `2.6.1`이다.

```bash
python scripts/inspect_gamepad_axes.py
python scripts/gamepad_input_monitor.py
```

확인된 DualShock 4 매핑:

```text
axis 0: 왼쪽 스틱 좌우
axis 1: 왼쪽 스틱 위아래
axis 2: L2
axis 5: R2
button 0: Cross
button 1: Circle
button 8: Share
button 9: Options
hat 0: 방향키
```

SO-101 URDF는 공식 SO-ARM100 저장소의 다음 파일을 사용한다.

```text
~/SO-ARM100/Simulation/SO101/so101_new_calib.urdf
```

FK 확인:

```bash
python scripts/fk_home_candidate.py
```

홈 후보의 그리퍼 프레임 위치는 URDF 베이스 기준 약 다음과 같았다.

```text
x = +147.0 mm
y =  +21.7 mm
z =  +36.3 mm
```

실제 모터를 움직이기 전에 작은 카테시안 이동의 IK를 계산으로만 확인한다.

```bash
python scripts/ik_small_steps_dry_run.py
python scripts/gamepad_ik_dry_run.py
```

`gamepad_ik_dry_run.py`는 `/dev/ttyACM0`에 연결하지 않는다. 게임패드 입력, 좌표 변화, IK 결과와 관절 제한만 확인한다.

Placo가 시작할 때 출력하는 `self collisions in neutral position` 경고는 URDF 기본 자세의 인접 메시 충돌 경고다. 실제 팔이 현재 충돌했다는 판정으로 사용하지 않는다.

## 11. 게임패드로 실제 조작하기

```bash
python scripts/gamepad_forward_back_test.py
```

파일 이름은 초기 앞뒤 시험에서 시작되어 그대로 남아 있지만, 현재는 XYZ 이동, 손목, 그리퍼를 모두 제어한다.

```text
왼쪽 스틱       손끝 앞뒤·좌우
L2 / R2         손끝 아래·위
방향키 위/아래  손목 기울기
방향키 좌/우    손목 회전
Cross / Circle  그리퍼 닫기·열기
Share           현재 XYZ와 실제 관절값 출력
Options          즉시 토크 해제 후 종료
오른쪽 스틱      사용하지 않음; LeKiwi용으로 보존
```

현재 주요 설정:

```text
카테시안 최고속도       25 mm/s
x/y 작업범위            시작점 기준 ±80 mm
z 위쪽 작업범위         시작점 기준 +100 mm
최종 소프트 바닥        URDF base 기준 z=-33.2 mm
바닥 감속 구간          바닥 위 20 mm
관절 명령 최대 변화     1.0 deg/control frame
비정상 IK 점프 거절     10 deg 초과
추종 오차 일시정지      12 deg 초과
추종 오차 재개          6 deg 미만
자동 E-stop             25 deg 초과가 1초 지속
```

관절 명령이 프레임 제한보다 크지만 비정상 점프는 아닐 때는 명령을 버리지 않고 `1°`씩 잘라 보낸다. 이때 화면에 `LIMIT`가 표시된다. 실제 모터가 뒤처지면 `PAUSE`로 목표 생성을 잠시 멈추고 따라잡으면 자동 재개한다.

### 바닥 위치 기록

팔을 책상에 고정한 상태에서 실제 그리퍼를 원하는 바닥 위치까지 내리고 Share로 좌표를 기록했다. 최종 캡처는 다음과 같다.

```text
xyz absolute (m): [0.125784, 0.008551, -0.033160]
shoulder_pan  :  -5.802 deg
shoulder_lift : +38.813 deg
elbow_flex    : +17.407 deg
wrist_flex    : +76.967 deg
wrist_roll    :  +1.978 deg
gripper       :   5.658 %
```

이 바닥값은 현재 책상, 클램프 위치와 팔 설치 상태에만 유효하다. 베이스를 옮기거나 책상 높이가 달라지면 Share로 다시 측정해야 한다.

## 12. 모터 가속도 튜닝 기록

현재 모터 설정을 읽는다.

```bash
python scripts/inspect_motor_tuning.py
```

처음 확인한 값:

```text
motor            accel  velocity     P     I     D
shoulder_pan         3        60    16     0    32
shoulder_lift        3        60    16     0    32
elbow_flex           3        60    16     0    32
wrist_flex           3        40    16     0    32
wrist_roll           3        40    16     0    32
gripper              3        35    16     0    32
```

다음 스크립트로 팔 관절 가속도 `50`, 그리퍼 가속도 `20`을 시험했다.

```bash
python scripts/set_motor_acceleration.py
```

`3 → 8 → 50`으로 올려도 홈 복귀와 게임패드 이동의 부들거림은 체감상 거의 같았다. 따라서 현재 판단은 모터 가속도보다 호스트가 작은 `Goal_Position`을 20Hz로 계속 갱신하는 방식, 모터 엔코더 해상도에 가까운 명령 양자화 또는 IK 관절 목표의 미세 변화가 우선 원인이라는 것이다.

다음 작업은 PID를 바로 바꾸는 것이 아니라 다음 순서로 진행한다.

1. 홈 복귀에서 목표를 20Hz로 잘게 보내는 방식과 모터 내부 궤적을 사용하는 방식을 비교한다.
2. 게임패드 제어에서 관절 목표 변화가 일정 크기 이상일 때만 전송하거나 작은 변화를 누적한다.
3. 관절 목표에 별도 속도·가속도 필터를 적용한다.
4. 그 뒤에도 떨리면 P/D 값을 한 항목씩 비교한다.

## 현재까지 확인한 것

- [x] SO-101 follower 팔 확인
- [x] `/dev/ttyACM0` 인식
- [x] `dialout` 권한
- [x] Feetech SDK 설치
- [x] 모터 ID 1~6 응답
- [x] raw 위치 읽기
- [x] LeRobot 캘리브레이션
- [x] 캘리브레이션 좌표 읽기
- [x] 관절별 저속 시험
- [x] 홈 자세 후보 기록
- [x] 게임패드 연결 및 축·버튼 매핑
- [x] SO-101 FK와 작은 IK dry-run
- [x] 안전 제한을 적용한 홈 이동
- [x] 게임패드 XYZ 조작
- [x] 방향키 손목 기울기·회전
- [x] 게임패드 그리퍼 열기·닫기
- [x] Share 위치 캡처
- [x] 실제 설치 기준 소프트 바닥 기록
- [x] Options 비상정지
- [x] 가속도 3, 8, 50 비교
- [ ] Goal_Position 스트리밍으로 인한 부들거림 개선
- [ ] 가벼운 물체 집기 반복 시험

## 참고: 관련 LeRobot 코드

- 명령 진입점: `src/lerobot/scripts/lerobot_calibrate.py`
- SO follower 캘리브레이션: `src/lerobot/robots/so_follower/so_follower.py`
- 중앙값과 가동범위 기록: `src/lerobot/motors/motors_bus.py`
- 캘리브레이션 JSON 읽기·저장: `src/lerobot/robots/robot.py`
