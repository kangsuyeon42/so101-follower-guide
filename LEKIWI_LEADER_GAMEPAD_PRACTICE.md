# LeKiwi Leader + 게임패드 통합 연습

이 문서는 노트북에 연결한 SO-101 Leader로 Pi의 Follower arm을 조작하고,
DualShock 4 왼쪽 스틱으로 LeKiwi 베이스를 동시에 조작하는 현재 검증 구성을
정리한다. 연습 UI는 손목·전면 RGB 영상을 함께 표시하지만 데이터를 저장하지
않는다.

## 현재 장치 역할

- Raspberry Pi 5
  - LeKiwi Follower arm과 바퀴 ID 1~9
  - Innomaker 손목 RGB 카메라
  - LeKiwi host와 손목 영상 송신기
- 노트북
  - SO-101 Leader arm
  - DualShock 4 게임패드
  - Logitech C920 전면 RGB 카메라
  - 통합 조작 및 연습 UI

현재 안정적인 장치 경로:

```text
Pi Feetech: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF219171-if00
Laptop Leader: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF219186-if00
Pi wrist camera: /dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0
Laptop body camera: /dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_2F21131F-video-index0
```

두 카메라는 모두 단안 RGB USB 카메라다. 스테레오 또는 depth 카메라가 아니며,
현재 연습과 향후 SmolVLA 데이터에는 RGB 영상만 사용한다.

## 안전 및 보존 사항

- `lerobot-setup-motors`를 실행하지 않는다.
- 모터 ID와 calibration을 변경하거나 덮어쓰지 않는다.
- Pi와 모터 12V 전원 배선을 변경하지 않는다.
- 실제 조작 전에 두 팔과 베이스 주변을 비운다.
- 이상 동작 시 게임패드 `OPTIONS`, Pi host `Ctrl+C`, 필요하면 모터 12V
  전원 차단 순으로 대응한다.
- 게임패드 입력은 베이스에만 사용한다. Follower arm은 Leader 입력만 따른다.

현재 유지되는 소프트웨어 보호:

- 스틱 중앙에서 베이스 정지
- 클라이언트 종료 시 정지 action 반복 전송
- Pi host의 500 ms command watchdog
- 팔 목표 속도 제한 및 저장된 calibration 범위 제한

## Pi 준비

노트북에서 Pi 터미널 두 개를 연다.

```bash
ssh moai5@10.42.0.2
```

첫 번째 Pi 터미널에서 카메라 없는 LeKiwi host를 실행한다.

```bash
bash ~/start_lekiwi_host_no_cameras.sh
```

숫자를 생략하면 사실상 시간 제한 없이 실행되며 `Ctrl+C`로 종료한다. 제한된
시험이 필요하면 초 단위 시간을 지정할 수 있다.

```bash
bash ~/start_lekiwi_host_no_cameras.sh 600
```

두 번째 Pi 터미널에서 손목 영상 송신기를 실행한다.

```bash
/home/moai5/miniforge3/envs/lerobot/bin/python -u \
  ~/wrist_camera_stream_server.py
```

정상 시작 메시지:

```text
Wrist camera streaming on tcp://*:5560. Ctrl+C stops.
```

## 두 팔을 홈 자세로 이동

통합 조작 전에 게임패드 전용 또는 통합 클라이언트가 실행 중이지 않은지
확인한다. Pi host를 실행한 상태에서 노트북의 별도 터미널에 다음을 입력한다.

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_move_arms_to_home.py
```

이 스크립트는 베이스 속도를 0으로 유지하면서 노트북 Leader와 Pi Follower를
각각 `config/leader_home_candidate.json`과
`config/follower_home_candidate.json`의 자세로 저속 이동한다. 화면의 예상
이동을 확인하고 주변과 팔 아래를 비운 뒤에만 `Enter`를 누른다. 완료 확인 후
두 번째 `Enter`를 누르면 Leader 토크가 해제된다.

## 카메라 없는 통합 조작

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_leader_gamepad_teleop.py
```

조작 매핑:

- Leader 6축: Follower arm 6축
- 왼쪽 스틱 위·아래: 전진·후진
- 왼쪽 스틱 좌·우만: 옴니 평행이동
- 왼쪽 스틱 대각선: 곡선 주행
- 스틱 중앙: 베이스 정지
- `OPTIONS` 또는 창 닫기: 베이스 정지 후 클라이언트 종료

기본 이동 속도는 `0.05 m/s`, 기본 회전 속도는 `25 deg/s`다.

## 두 카메라 통합 연습 UI

Pi host와 손목 영상 송신기를 모두 실행한 뒤 노트북에서 다음을 실행한다.

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_practice_ui.py
```

화면 구성:

- 왼쪽: Logitech C920 전면 RGB 영상
- 오른쪽: Pi Innomaker 손목 RGB 영상
- 아래: 베이스 속도와 팔 목표 상태

이 UI는 실제 수집 화면을 연습하기 위한 것으로, 데이터셋·영상·에피소드 파일을
생성하지 않는다.

## 종료 순서

1. 게임패드 `OPTIONS`로 노트북 통합 클라이언트를 종료한다.
2. `Final base STOP sent` 메시지를 확인한다.
3. 손목 영상 Pi 터미널에서 `Ctrl+C`를 누른다.
4. LeKiwi host Pi 터미널에서 `Ctrl+C`를 누른다.

Pi host 종료 시 베이스 정지와 Follower 토크 해제가 실행된다.

## 향후 데이터 수집 작업

첫 데이터 수집 작업 문장:

```text
Drive to the green block, pick it up, and place it in the gray tray.
```

향후 기록기는 전면·손목 RGB 영상, 팔 6축과 베이스 3축의 공식 9차원
observation/action, 위 작업 문장을 동일한 에피소드 시간축에 저장할 예정이다.
현재 연습 UI에는 기록 기능이 없다.
