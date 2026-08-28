# 다음 세션에 붙여 넣을 프롬프트

아래 내용을 새 세션 첫 메시지로 그대로 붙여 넣는다.

---

SO-101 Leader/Follower + LeKiwi 모바일 매니퓰레이션 프로젝트를 이전 작업에서 이어서 진행하고 싶어.

## 프로젝트와 목표

- 프로젝트: `~/so101-follower-guide`
- LeRobot: `~/lerobot`
- GitHub: <https://github.com/kangsuyeon42/so101-follower-guide>
- 노트북 Conda: `lerobot`
- Python 3.12.13, LeRobot 0.6.2
- 처음 확인한 LeRobot commit: `59ab28620f3f2385f808bd4bcac7fc50cf14217a`

최종 목표는 LeKiwi가 물체까지 이동하고 SO-101 팔로 집어서 오른쪽에 놓는 모바일 매니퓰레이션이다. ACT를 거치지 않고 `lerobot/smolvla_base`를 바로 파인튜닝한다. 작업 문장 후보는 `Drive to the object, pick it up, and place it to the right.`이다.

최종 데이터셋에는 손목/전면 카메라, 팔 6축, `x.vel/y.vel/theta.vel`, 자연어 작업 문장을 넣는다. 공식 LeKiwi 9차원 action/state를 사용하고 약 50개 이상의 고품질 통합 에피소드를 수집한다. 최초 10개는 데이터 구조·영상·action 정합성 검증용이다.

## 역할과 전원

- Pi 5: 바퀴, Follower arm, 카메라, LeKiwi host
- 노트북: Leader arm, LeKiwi client, 데이터 저장
- GPU PC/서버: SmolVLA 학습
- 모터 12V 전원과 Pi 전원은 분리한다.

Pi에는 `This power supply is not capable of supplying 5A; power to peripherals will be restricted` 경고가 있었다. RealSense와 Innomaker 두 대를 동시에 연결했을 때 Pi가 꺼졌다. RealSense나 두 카메라를 다시 한꺼번에 연결하지 않는다. 향후 공식 Pi 5 27W(5.1V/5A) 전원 사용을 권장한다.

## Ethernet — 성공 및 고정 완료

- 노트북: `10.42.0.1`
- Pi `eth0`: `10.42.0.2/24`
- SSH: `ssh moai5@10.42.0.2`
- Pi 사용자/호스트: `moai5@lekiwi`
- Pi netplan: `/etc/netplan/99-lekiwi-lan.yaml`
- Pi는 `systemd-networkd`, 노트북은 NetworkManager의 `Wired connection 1` shared 사용

```bash
ping -c 3 10.42.0.2
ssh moai5@10.42.0.2
```

Pi 환경은 Ubuntu Server 24.04, Conda `lerobot`, 올바른 Python은 `/home/moai5/miniforge3/envs/lerobot/bin/python`, LeRobot은 `/home/moai5/lerobot/src/lerobot/__init__.py`이다. LeRobot 0.6.2, core_scripts/lekiwi extra, ZeroMQ 27.2.0, `scservo_sdk`가 설치됐고 `moai5`는 `dialout` 그룹이다.

## 모터 — 검증 완료

- Feetech: `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AAF263511-if00`
- ID 1~6: Follower arm, ID 7~9: 바퀴
- 1~9 모두 model 777, ping `OK`
- `lerobot-setup-motors`를 실행하거나 ID를 변경하지 않는다.
- Feetech 보드에는 별도 12V 모터 전원이 필요하다.
- Wheeltech 배터리 표기: 4500mAh, 12V, 49.95Wh
- 전압/극성/분배를 추측하지 않고 Pi와 모터 전원을 합치지 않는다.

읽기 전용 스캔은 `python -u ~/scan_lekiwi_motor_ids.py`, 프로젝트 원본은 `scripts/scan_lekiwi_motor_ids.py`이다.

## 캘리브레이션 — 검증 완료

- Pi: `~/.cache/huggingface/lerobot/calibration/robots/lekiwi/follower.json`
- 팔의 기존 SO-101 calibration을 보존했다.
- 바퀴 7~9의 실제 `homing_offset`은 모두 85이고 파일도 85로 맞췄다.
- 모터 레지스터에는 쓰지 않았다.
- `python ~/check_lekiwi_calibration_match.py` 결과 `calibration_matches_motors: True`
- 캘리브레이션을 다시 덮어쓰지 않는다.

## 물리적 앞 방향 — 수정 및 검증 완료

실제 앞쪽은 바퀴 7과 9 사이다. 기존 모델 x축이 실제 장착과 반대여서 `~/lerobot/src/lerobot/robots/lekiwi/lekiwi.py`에서 action과 state x축을 함께 반전했다. 이후 앞/뒤/좌/우가 실제 방향과 일치했다.

복구 패치는 `patches/lekiwi_physical_front_x_axis.patch`이다. LeRobot 파일이 덮였을 때만 아래를 실행하고 중복 적용하지 않는다.

```bash
cd ~/lerobot
git apply ~/so101-follower-guide/patches/lekiwi_physical_front_x_axis.patch
python -m py_compile src/lerobot/robots/lekiwi/lekiwi.py
```

## 키보드 텔레오퍼레이션 — 성공 완료

카메라 없이 Pi host와 노트북 Pygame 창으로 실제 주행에 성공했고 조작감이 아주 좋았다. 함부로 동작을 바꾸지 않는다.

Pi:

```bash
conda activate lerobot
bash ~/start_lekiwi_host_no_cameras.sh 600
```

노트북 새 터미널:

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_keyboard_drive.py
```

- `W/A/S/D`: 전진/왼쪽 평행/후진/오른쪽 평행
- `W+A`, `W+D`: 전진 좌회전/우회전
- `S+A`, `S+D`: 후진 선회
- `Space`: 즉시 정지, `Esc`: 정지 후 종료
- 창 포커스를 잃어도 정지
- 기본 `0.05 m/s`, `25 deg/s`

자세한 문서: `LEKIWI_KEYBOARD_DRIVE.md`. Pi의 `No command available`은 client가 없을 때 정상 대기 경고다.

## 다음 세션 시작점: 손목 카메라 한 대

사용자는 기존 SO-101 arm에서 쓰던 **Innomaker 손목 카메라 한 대**를 팔에 그대로 장착하고 있다. 이 카메라 한 대를 Pi에 연결했을 때는 Pi가 꺼지지 않았다. 다음에는 이 손목 카메라만 사용해서 시작한다.

1. 모터가 정지한 상태에서 Pi에 손목 카메라 한 대만 연결했는지 확인
2. Pi 전력/저전압 상태를 읽기 전용으로 확인
3. `lsusb`, `/dev/v4l/by-id`, `/dev/video*`, 커널 로그로 인식 확인
4. 필요하면 `v4l-utils` 설치 여부를 확인하되 설치 전 설명
5. 안정적인 경로, 포맷, 해상도/FPS 확인
6. 프레임 한 장만 읽어 방향과 노출 확인
7. 손목 카메라 1대가 포함된 host/client 텔레오퍼레이션으로 전환
8. Leader arm과 통합하고 9차원 action/state 정합성 확인
9. 전면 카메라는 Pi 전원에 맞는 저전력 RGB 모델을 정한 뒤 추가

카메라 때문에 Pi가 재부팅되거나 Ethernet이 끊기면 반복하지 말고 전력 원인을 먼저 진단한다.

## 노트북 장치와 진행 원칙

- Leader: `/dev/ttyACM1`
- Follower는 Pi로 옮기기 전 `/dev/ttyACM0`
- 손목 카메라: 기존 Innomaker

- 한 번에 한 단계씩 안내한다.
- 모든 명령에 `[노트북]` 또는 `[Pi]`를 표시한다.
- 긴 명령/코드는 heredoc으로 주지 말고 `~/so101-follower-guide`에 VS Code 파일로 만든다.
- 실제 팔/바퀴가 움직이기 전에 명령, 예상 동작, 종료 방법, 주의점을 설명한다.
- 읽기 전용 확인을 우선한다.
- 모터 ID 변경, calibration 덮어쓰기, 전원 배선 변경은 확인 없이 하지 않는다.
- 기존 파일과 안전 설정을 덮거나 삭제하지 않는다.
- 문제 발생 시 반복 실행보다 원인을 먼저 진단한다.

먼저 Git 상태와 위 파일들을 확인한 뒤, 사용자에게 손목 카메라 한 대만 Pi에 연결했는지 물어보고 카메라 인식 단계부터 이어가자.

---

