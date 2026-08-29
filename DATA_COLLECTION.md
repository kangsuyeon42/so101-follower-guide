# 데이터 수집

이 문서는 SO-101 및 LeKiwi의 LeRobotDataset 수집과 검증 절차를 기록한다.
현재는 독립형 SO-101 Leader/Follower와 손목 카메라를 사용한 파일럿 기록까지
검증했다. LeKiwi 베이스와 전면 카메라 통합 절차는 검증 후 추가한다.

## 손목 카메라 점검

모터를 연결하지 않은 상태에서 손목 카메라가 정상 동작하는지 먼저 확인한다.

```bash
conda activate lerobot
cd ~/so101-follower-guide
python scripts/test_wrist_camera.py
```

## 파일럿 에피소드 기록

다음 예시는 6축 텔레오퍼레이션 중 관절 상태, Follower 명령과 손목 영상을
20초 동안 20 FPS로 기록한다.

```bash
python scripts/leader_teleoperation.py \
  --leader-port /dev/ttyACM1 \
  --follower-port /dev/ttyACM0 \
  --record-one-episode \
  --episode-seconds 20 \
  --task "Pick up the object and place it to the right."
```

실행 전 두 팔의 포트, 시작 자세와 토크 상태를 확인한다. 종료는 `Ctrl+C`다.
Follower 토크가 풀릴 때 팔이 내려올 수 있으므로 받을 준비를 한다.

결과는 다음 형식의 로컬 디렉터리에 저장된다.

```text
outputs/datasets/so101_wrist_pilot_YYYYMMDD_HHMMSS/
```

데이터셋에는 Parquet 동작 데이터와 MP4 손목 영상이 포함된다. `outputs/`는
로컬 수집 데이터이므로 Git에서 추적하지 않는다.

## 영상 확인

LeRobot이 생성한 영상은 AV1 코덱을 사용할 수 있다. Ubuntu 기본 플레이어에서
열리지 않으면 `ffplay`로 재생한다.

```bash
ffplay outputs/datasets/<dataset>/videos/observation.images.wrist/chunk-000/file-000.mp4
```

필요하면 검토용 H.264 사본을 만든다. 원본 데이터셋 영상은 변경하지 않는다.

```bash
ffmpeg \
  -i outputs/datasets/<dataset>/videos/observation.images.wrist/chunk-000/file-000.mp4 \
  -c:v libx264 \
  -crf 18 \
  -pix_fmt yuv420p \
  outputs/datasets/<dataset>/videos/observation.images.wrist/chunk-000/file-000-h264.mp4
```

## 통합 데이터셋 목표

최종 데이터셋은 같은 프레임과 타임스탬프 기준으로 다음 항목을 포함한다.

- 손목 카메라와 전면 카메라 observation
- SO-101 팔 6축 action/state
- LeKiwi 베이스 `x.vel`, `y.vel`, `theta.vel`
- 자연어 작업 문장

공식 LeKiwi 9차원 action/state 구조를 유지한다. 50개 이상의 고품질 통합
에피소드를 목표로 하며, 최초 10개는 학습보다 데이터 구조, 영상과
observation/action 정합성 검증에 사용한다.
