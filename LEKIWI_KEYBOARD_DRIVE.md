# LeKiwi 키보드 주행

현재 검증된 구성은 카메라 없이 Raspberry Pi가 LeKiwi 호스트를 실행하고,
노트북의 작은 Pygame 창에서 키보드 명령을 보내는 방식이다.

## 연결

- 노트북 Ethernet: `10.42.0.1`
- Raspberry Pi Ethernet: `10.42.0.2`
- SSH: `ssh moai5@10.42.0.2`
- 모터 ID: 팔 `1~6`, 바퀴 `7~9`
- LeKiwi의 물리적 앞쪽: 바퀴 `7`과 `9` 사이

## 실행

### 1. Raspberry Pi 터미널

```bash
conda activate lerobot
bash ~/start_lekiwi_host_no_cameras.sh 600
```

이 터미널은 계속 켜 둔다. `No command available`은 노트북 명령을 기다리는
정상 상태다.

### 2. 노트북의 새 터미널

```bash
conda activate lerobot
python ~/so101-follower-guide/scripts/lekiwi_keyboard_drive.py
```

열린 `LeKiwi WASD Drive` 창을 클릭한 뒤 조종한다.

## 조작

- `W`: 전진
- `A`: 왼쪽 평행 이동
- `S`: 후진
- `D`: 오른쪽 평행 이동
- `W+A`, `W+D`: 전진하면서 좌회전, 우회전
- `S+A`, `S+D`: 후진하면서 선회
- `Space`: 즉시 정지
- `Esc`: 정지 명령을 보낸 뒤 조종 프로그램 종료

창이 키보드 포커스를 잃으면 정지 명령을 보낸다.

## 종료

1. 조종 창에서 `Esc`
2. Pi 호스트 터미널에서 `Ctrl+C`
3. 비정상 움직임이 계속되면 모터 12V 전원을 차단

## 속도 조절

기본 이동 속도는 `0.05 m/s`, 회전 속도는 `25 deg/s`다. 더 빠른 시험은
주변을 충분히 비운 상태에서만 실행한다.

```bash
python ~/so101-follower-guide/scripts/lekiwi_keyboard_drive.py \
  --speed 0.07 \
  --turn-speed 30
```

허용 상한은 각각 `0.08 m/s`, `30 deg/s`다.

## LeRobot 앞/뒤 축 수정

현재 장착 방향에서는 공식 모델의 x축과 물리적 앞쪽이 반대라서
`~/lerobot/src/lerobot/robots/lekiwi/lekiwi.py`의 action/state x축을 함께
반전했다. LeRobot을 다시 설치하거나 해당 파일을 덮어쓴 경우 아래 패치를
다시 적용한다.

```bash
cd ~/lerobot
git apply ~/so101-follower-guide/patches/lekiwi_physical_front_x_axis.patch
python -m py_compile src/lerobot/robots/lekiwi/lekiwi.py
```

