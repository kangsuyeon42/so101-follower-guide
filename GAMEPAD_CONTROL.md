# 게임패드 제어

## 준비와 IK dry-run

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

## 실제 조작

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

## 모터 가속도 튜닝 기록

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

### Goal_Position 미세 명령 누적

`scripts/gamepad_forward_back_test.py`는 더 이상 계산된 목표를 무조건 20Hz로
전송하지 않는다. 관절 목표는 마지막 전송값에서 `0.15°`, 그리퍼는 `0.15%`
이상 달라질 때까지 작은 변화를 누적한다. 게임패드 입력을 놓는 순간에는 남은
변화를 한 번 전송해 최종 목표를 일치시킨다. 화면의 `tx`는 실제 목표 전송
횟수이므로, 같은 동작에서 기존 20Hz 연속 전송보다 얼마나 줄었는지 확인할 수
있다.

실기 시험 전에는 스크립트가 `/dev/ttyACM0` 존재 여부와 각 모터의 현재 토크
상태를 먼저 출력한다. 모터 하나라도 이미 토크가 켜져 있으면 기존 목표를 쓰거나
토크 상태를 바꾸지 않고 중단한다. 포트가 없는 상태에서는 실행하지 않는다.



