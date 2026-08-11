# SO-101 follower 팔 연결 , Home_position 기록

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

이 값은 아직 자동 실행하지 않는다. 다음 단계에서 충돌 방지와 속도 제한을 넣은 홈 이동 코드를 별도로 만드는 것이 안전하다.

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
- [ ] 게임패드 연결
- [ ] 안전 제한을 적용한 홈 이동
- [ ] 게임패드로 저속 조작

## 참고: 관련 LeRobot 코드

- 명령 진입점: `src/lerobot/scripts/lerobot_calibrate.py`
- SO follower 캘리브레이션: `src/lerobot/robots/so_follower/so_follower.py`
- 중앙값과 가동범위 기록: `src/lerobot/motors/motors_bus.py`
- 캘리브레이션 JSON 읽기·저장: `src/lerobot/robots/robot.py`

