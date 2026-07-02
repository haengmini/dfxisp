---
type: experiment-report
title: "DFXISP 실험 보고서 — 조건부터 결과까지 (reset 아키텍처, SW 트랙)"
project: DFXISP
created: 2026-07-02
status: preliminary (SW proxy; pseudo-RAW; CPU; YOLOv8n/s)
scope: "Stage 1~3 (보드 불필요). Stage 4~6(HW)는 조건만 명시, 수치는 TODO(측정)."
---

# DFXISP 실험 보고서 — 조건부터 결과까지

> 2026-07-01 아키텍처 reset(**shared baseline ISP core + 상호배타 mode-specific
> tone RM slot**) 적용 후, 보드 없이 수행 가능한 SW 트랙(Stage 1~3) 실험을 조건·방법·
> 결과·해석까지 하나로 정리한 보고서. 정본 아키텍처는 `RESEARCH.md`, 단계 계획은
> `experiment-stages-2026-07-02.md`, 원자료 CSV는 `results/`.

---

## 1. 목적과 가설

**목적:** reset 아키텍처(gain/gamma를 baseline core에서 제거하고 상호배타 tone RM으로
분리)가 머신비전 관점에서 (H1) 저조도 정확도를 개선하는지, (H2) 중복제거 후에도 정확도를
유지하는지, (H3) DFX가 자원/전력 이득을 주는지를 실험적으로 분리 검증한다.

| 가설 | 내용 | 본 보고서 범위 |
|---|---|---|
| H1 (Algorithmic) | low-light tone RM이 저조도 mAP를 무처리/오모드 대비 개선 | **검증(Stage 3)** |
| H2 (Architecture) | gain/gamma를 tone RM으로 분리해도 정확도 유지 | **검증(Stage 2·3)** |
| H3 (DFX efficiency) | DFX가 register-only 대비 자원/전력 절감 | 조건만(Stage 4~6, TODO) |

---

## 2. 실험 조건

### 2.1 실행 환경
- CPU 전용(CUDA 드라이버 구버전으로 GPU 비활성), Python3, numpy/PIL/OpenCV/torch/
  torchvision/ultralytics/pycocotools 설치.
- 검출기: `yolov8n.pt`, `yolov8s.pt` (COCO 사전학습), ultralytics `model.val()`, imgsz=640.

### 2.2 데이터셋 (pseudo-RAW)
- `data/exdark_val` (저조도), `data/coco_val` (정상조도). 각 `raw_bin/`(RGGB16, headerless
  uint16, 16→8bit shift8) + `images/`(dims 출처) + `labels/`(YOLO).
- **라벨: 두 데이터셋 모두 COCO-80 id** `{0,1,2,3,5,8,15,16,39,41,56,60}` → **remap 없음**.
- 유효 프레임: raw_bin 크기와 jpg 해상도 일치분만 사용(Stage 3 ExDark n=71, COCO n=80;
  Stage 2 ExDark n=98, COCO n=113, limit=150~200).

### 2.3 검증 대상 아키텍처와 arm 정의
tone RM slot이 shared baseline core를 감싸는 구조(2026-07-01 확정). SW eval은 데이터셋
레이아웃에 맞춰 RGGB demosaic를 쓰며(C-sim golden은 GRBG), **arm 간 상대 behaviour**를 비교.

| arm | 정의 | 출력형상 | 조건표 매핑 |
|---|---|---|---|
| **none** | demosaic만(무처리) | H×W | A(ExDark)·D(COCO) |
| **normal** | RM_NORMAL_TONE(identity) + baseline core | H×W | B·E |
| **lowlight** | RM_LOW_LIGHT_TONE(2x2 RAW bin+gain+gamma4) + core | H/2×W/2 | C·F |
| **adaptive** | checker가 프레임별 normal/lowlight 선택 | mixed | G |

### 2.4 파이프라인 파라미터 (정수, 결정적)
- **baseline core(mode 무관):** BLC offset 16 → AWB Q8 (R=286, G=256, B=307) → CCM identity.
  **gain/gamma 없음.**
- **RM_LOW_LIGHT_TONE:** 2x2 RAW binning-demosaic(R=top-left, G=(top-right+bottom-left)/2,
  B=bottom-right) → baseline core → gain ×1.25(5/4) → gamma-4.0 LUT
  `floor((255^3·v)^(1/4))`(정수 4제곱근).
- **checker:** `Y=(R+2G+B)/4`, `dark_ratio = mean(Y<50)`, `dark_ratio>0.40 → lowlight`.

### 2.5 도구 (신규, 공용 모델)
`tools/newrm_pipeline.py`(numpy 벡터화 아키텍처 모델) 위에
`scheduler_sweep.py`(Stage 1) · `image_metrics_newrm.py`(Stage 2) ·
`eval_map_newrm.py`(Stage 3). C-sim golden bit-exact 모델은 `tools/gen_golden_vectors.py`.

### 2.6 평가 프로토콜
- Stage 1: 결정적 노이즈 luma 시퀀스(1000프레임, 고정시드) + 4정책 + 파라미터 스윕(27경우).
- Stage 2: arm별 출력 이미지 지표 집계(dataset×arm 평균).
- Stage 3: arm별 이미지 생성 → `model.val()` → mAP@[.5:.95]·mAP@50. 판단 근거는 **arm 순서**.

---

## 3. 방법(절차) 요약

```text
Stage 1  scheduler_sweep.py  → results/scheduler.csv, scheduler_sweep.csv
Stage 2  image_metrics_newrm.py --root <ds> --tag <T> → results/image_metrics_<t>.csv
Stage 3  eval_map_newrm.py --root <ds> --tag <T> --model <m> → results/map_newrm_<t>_<m>.csv
```

---

## 4. 결과

### 4.1 Stage 1 — checker/스케줄러

기본 4정책:

| 정책 | mismatch | switch/1k | thrashing | skipped |
|---|---|---|---|---|
| baseline_checker | 0.054 | 86.0 | 0.884 | 344 |
| plus_hysteresis | 0.021 | 28.0 | 0.571 | 112 |
| plus_temporal(N=5) | 0.140 | 4.0 | 0.000 | 16 |
| plus_min_dwell | 0.140 | 4.0 | 0.000 | 16 |

파라미터 스윕 27경우 상위:

| band | N | dwell | mismatch | switch/1k | thrashing |
|---|---|---|---|---|---|
| **narrow** | **3** | 15~60 | **0.015** | 6.0 | 0.000 |
| narrow | 5 | 15~60 | 0.072 | 6.0 | 0.000 |

→ **narrow 히스테리시스 밴드 + temporal_N=3**가 최적(mismatch 0.015, thrashing 0). 순간
임계의 thrashing 0.884를 제거하면서 기본값(medium/N=5, 0.140) 대비 mismatch 9배 개선.
재구성 지연 PR∈{2,4,8}에서 skipped=switch×PR(선형) → 전환수 최소화가 지연 비용의 축.

### 4.2 Stage 2 — 이미지 지표

| dataset | arm | out shape | Y mean | 포화율% | dark-ratio(전→후) | gain/γ 중복 |
|---|---|---|---|---|---|---|
| ExDark(n=98) | none | 778×606 | 14.0 | 1.87 | 0.919 | False |
| ExDark | normal | 778×606 | 11.0 | 0.72 | 0.919→0.932 | False |
| ExDark | lowlight | 389×303 | 25.5 | 2.61 | 0.919→0.842 | False |
| COCO(n=113) | none | 577×494 | 64.2 | 6.29 | 0.544 | False |
| COCO | normal | 577×494 | 54.7 | 1.44 | 0.544→0.611 | False |
| COCO | lowlight | 288×247 | 120.7 | 11.25 | 0.544→0.302 | False |

- lowlight tone이 저조도를 밝힘(ExDark Y 14→25.5, dark-ratio↓). Policy A 형상 반감 확인.
- **normal(gain 없는 baseline core)이 저조도를 더 어둡게**(Y 14→11) — BLC/AWB만으로는 악화.
- COCO lowlight 포화율 11.25% — 정상조도 과처리. gain/γ 중복=False(구조 불변식 유지).
- checker 과트리거: naive 임계로 COCO 89/113이 lowlight 판정 → dark-level 재보정 필요.

### 4.3 Stage 3 — 정확도 mAP, 조건표 A~G (3 detector)

mAP@[.5:.95] (YOLO 괄호는 mAP@50):

| 조건 | dataset·arm | YOLOv8n | YOLOv8s | SSDLite-MNv3 |
|---|---|---|---|---|
| **A** | ExDark·none | **0.1561** (0.3064) | **0.2236** (0.4059) | **0.1040** |
| **B** | ExDark·normal | 0.0680 (0.1490) | 0.1249 (0.2480) | 0.0443 |
| **C** | ExDark·lowlight | 0.0554 (0.1342) | 0.1276 (0.2595) | 0.0333 |
| **G** | ExDark·adaptive | 0.0554 (0.1342) | 0.1276 (0.2595) | 0.0333 |
| **D** | COCO·none | **0.3276** (0.4707) | **0.4280** (0.6105) | **0.2320** |
| **E** | COCO·normal | 0.2879 (0.4175) | 0.3775 (0.5244) | 0.2305 |
| **F** | COCO·lowlight | 0.2574 (0.3497) | 0.3402 (0.4590) | 0.2096 |
| **G** | COCO·adaptive | 0.2590 (0.3725) | 0.3486 (0.4717) | 0.2125 |

**세 detector(YOLOv8n/s + SSD+MobileNet)·두 데이터셋 모두에서 `none`(무처리)이 최고**,
순서 `none > normal ≳ lowlight`가 detector 계열에 무관하게 유지(guardrail 결론의 견고성 강화).
SSDLite-MNv3는 torchvision COCO 사전학습(구조가 다른 detector 계열). 정확한 Vitis-AI
`tf_ssdmobilenetv1`은 가중치 부재·TF1.15로 이 환경 실행 불가 → 보드 DPU end-to-end 단계용.

---

## 5. 분석 및 해석

1. **H2 부분 반증:** de-duplication으로 normal tone을 identity로 두니 저조도에서 mAP가
   크게 하락(ExDark none 0.156 → normal 0.068). gain 없는 baseline core가 dark scene을
   어둡게 만든 것이 원인(Stage 2와 정합). → **RM_NORMAL_TONE은 register gain을 담아야** 함.
2. **H1 미지지:** low-light tone RM(bin+gain+gamma-4.0, Policy A)이 저조도에서도 none을
   못 이김. gamma-4.0 과증폭 + H/2 해상도 손실이 원인으로 추정. → 더 약한 tone/denoise형
   RM, 또는 Policy B(형상보존)로 재설계 필요.
3. **스위칭 방향은 정당:** 정상조도(COCO)에서도 저조도 경로는 이득 없음(F<E<D) → 저조도
   RM은 어두울 때만 켜야 한다는 적응 방향 자체는 유효.
4. **방향 A 강화:** 본 SW 실측은 "mAP는 최소/register 처리가 담당, 구조적 tone RM은 mAP
   근거가 약함"을 재확인. ⇒ **DFX/RM의 정당화는 자원/전력(Stage 4~6)** 이라는 방향 A 서사와
   정합. mAP-guardrail이 현 RM 후보를 탈락시키는 것이 방법론의 작동 증거.

### 즉시 반영할 설계 수정
- (a) **RM_NORMAL_TONE = register gain**(identity 아님). de-dup은 유지하되 gain을 tone RM으로.
- (b) **low-light RM 재포지셔닝**: gamma 완화(γ≈2.5~3.0), Policy B 또는 denoise, bilinear 업샘플.
- (c) **checker dark-level 재보정**: COCO 과트리거 제거(adaptive의 lowlight 붕괴 방지).
→ 위 반영 후 Stage 3 재측정으로 guardrail 재판정.

---

## 6. Stage 4~6 (HW) — 조건 명시, 수치 TODO

Vivado/보드 필요로 본 보고서 범위 밖. 조건만 고정:
- Stage 4: `DFXISP_HLS_FLOW=csynth/cosim make hls` — baseline core/RM별 LUT·FF·BRAM·DSP·II·WNS,
  L0~L3 bit-exact(streaming line buffer 리팩터 선행).
- Stage 5: DFX PR FSM(drain→ICAP→swap) 멀티프레임 전환 sim, partial bitstream·재구성 지연.
- Stage 6: ZCU104 실증, arm1/2/3 자원·절대전력(W)·throughput·PR 오버헤드.
모든 HW 수치는 실측 전까지 `TODO(측정)`.

---

## 7. 재현

```bash
cd isppipeline/hls
python3 tools/scheduler_sweep.py --out results/scheduler_sweep.csv           # Stage 1
python3 tools/image_metrics_newrm.py --root ../../data/exdark_val --tag ExDark --limit 200  # Stage 2
python3 tools/eval_map_newrm.py --root ../../data/exdark_val --tag ExDark --model yolov8n.pt --limit 150 \
    --out results/map_newrm_exdark_yolov8n.csv                               # Stage 3 (COCO/yolov8s 동일)
```

---

## 8. 한계

- SW proxy: pseudo-RAW는 이미 ISP된 JPEG 역변환, RGGB nearest demosaic, n=71~113(크기
  불일치 스킵), CPU. **절대값이 아니라 arm 순서**가 판단 근거(guardrail).
- C-sim golden(GRBG) vs eval(RGGB) — 상대 behaviour 비교 관례(구 08-e2와 동일).
- 구 08/11(static/reg/bin/fp variant) 수치와 직접 비교 금지: arm 정의가 다름
  (여기 normal=baseline core no-gain / 구 reg_only=demosaic+gain).
- checker 임계 미보정 상태의 결과 — (c) 반영 시 adaptive 수치 변동 예상.

## 산출물
Stage 1 `scheduler{,_sweep}.csv` · Stage 2 `image_metrics_{exdark,coco}.csv` ·
Stage 3 `map_newrm_{exdark,coco}_{yolov8n,yolov8s}.csv` · 상세 `stage1-3-results-2026-07-02.md`.
