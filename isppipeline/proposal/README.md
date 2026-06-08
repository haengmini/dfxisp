# task3 — Proposal ISP (Vitis Vision L1 + Custom Adaptive Blocks)

Baseline ISP 파이프라인에 조도 감지 FSM(`checker`) 및 모드별 재구성(DFX) 대상 블록(`Partial Module`)을 추가한 **제안(Proposal) 적응형 ISP 파이프라인**입니다.

## 파이프라인 구조

```
Bayer16 (RGGB, task1 raw)
  │
  ▼
[Static Front-End]
  scale_16to8 ──> blackLevelCorrection ──> gaincontrol (WB) ──> demosaicing ──> CCM ──> RGB8 (ccm)
  │
  ├─> [Checker] Y = (R+2G+B)>>2 휘도 히스토그램 분석 ──> 모드 결정 (NORMAL ↔ LOW_LIGHT)
  │
  ▼
[Partial Module (DFX 대상)]
  ├─ MODE_NORMAL    : gamma (γ2.2) ──> RGB8 (H×W)
  └─ MODE_LOW_LIGHT : binning2x2 + gain(×1.5) ──> gamma (γ4.0) ──> RGB8 (H/2 × W/2)
```

## 파일 구성

* `isp_proposal.hpp` / `isp_proposal_accel.cpp`: 제안 ISP 파이프라인 HLS 소스
* `isp_proposal_tb.cpp`: OpenCV 의존성 없는 호스트용 HLS C-Simulation 테스트벤치
* `checker.cpp` / `checker.hpp`: 조도 판정 FSM (디스플레이 감마 적용 휘도 기반)
* `binning_gain.cpp` / `binning_gain.hpp`: 2×2 공간 binning + ×1.5 게인 연산
* `pr_controller.cpp` / `pr_controller.hpp`: 부분 재구성 제어 FSM
* `prep_and_check.py`: C-sim 입력 바이너리 생성 및 Python 골든 모델 비트 대조 하니스
* `build.sh`: 컴파일 및 자동 검증 스크립트

## 검증 방법

컴파일 및 밝은 이미지(COCO), 어두운 이미지(ExDark)에 대한 자동 모드 결정 및 비트 대조 검증을 수행하려면 다음 스크립트를 실행합니다.

```bash
./build.sh
```

### 실행 결과 예시
```
[build] --- BRIGHT (COCO) auto-mode ---
[tb] checker mode = NORMAL (forced=-1)
[golden] mode=0 shape=(426, 640, 3) mismatch=0 (PASS)

[build] --- DARK (ExDark) auto-mode ---
[tb] checker mode = LOW_LIGHT (forced=-1)
[golden] mode=1 shape=(384, 512, 3) mismatch=0 (PASS)
```
* **mismatch=0 (PASS)**: C-Simulation 출력이 Python 골든 모델([isppipeline/unprocess/isp_pipeline.py](file:///home/mini/isp/pr_cnn/project/isppipeline/unprocess/isp_pipeline.py))과 픽셀 단위로 완벽하게 일치함을 보장합니다.
