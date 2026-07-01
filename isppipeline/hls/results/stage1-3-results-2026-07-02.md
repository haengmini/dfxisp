---
type: experiment-results
title: "DFXISP Stage 1~3 SW 실측 결과 — reset 아키텍처"
project: DFXISP
created: 2026-07-02
status: preliminary (SW proxy; pseudo-RAW; CPU; YOLOv8n/s)
note: "실제 실측. 핵심 가설을 부분 반증하는 결과 포함 — 정직하게 기록."
---

# Stage 1~3 SW 실측 결과 (reset 아키텍처)

> 대상: shared baseline core + 상호배타 tone RM slot(RM_NORMAL_TONE=identity /
> RM_LOW_LIGHT_TONE=2x2 bin+gain+gamma-4.0, Policy A). 도구: `tools/scheduler_sweep.py`,
> `image_metrics_newrm.py`, `eval_map_newrm.py`(공용 모델 `newrm_pipeline.py`).
> 데이터: `data/{coco_val,exdark_val}` pseudo-RAW(RGGB16). 계획: `experiment-stages-2026-07-02.md`.

---

## Stage 1 — checker + 히스테리시스 스케줄러

### 1a. 4개 정책 (기본 파라미터, `results/scheduler.csv`)
| 정책 | mode mismatch | switch/1k | thrashing | skipped |
|---|---|---|---|---|
| baseline_checker (순간 임계) | 0.054 | 86.0 | 0.884 | 344 |
| plus_hysteresis | 0.021 | 28.0 | 0.571 | 112 |
| plus_temporal (N=5) | 0.140 | 4.0 | **0.000** | 16 |
| plus_min_dwell | 0.140 | 4.0 | **0.000** | 16 |

순간 임계는 thrashing 0.884로 심각(전환 86회/1k). 히스테리시스+temporal이 thrashing을
0으로 없애지만 기본 N=5·medium 밴드에선 전환 지연으로 mismatch가 0.140까지 상승.

### 1b. 파라미터 스윕 27경우 (`results/scheduler_sweep.csv`)
밴드(narrow/medium/wide) × temporal_N(3/5/8) × min_dwell(15/30/60), plus_min_dwell 정책.
상위(무thrashing·저mismatch·소switch):

| band | N | dwell | mismatch | switch/1k | thrashing | skipped@PR4 |
|---|---|---|---|---|---|---|
| **narrow** | **3** | **15** | **0.015** | 6.0 | 0.000 | 24 |
| narrow | 3 | 30/60 | 0.015 | 6.0 | 0.000 | 24 |
| narrow | 5 | 15~60 | 0.072 | 6.0 | 0.000 | 24 |

**결론:** **narrow 히스테리시스 밴드 + temporal_N=3**가 최적(mismatch 0.015, thrashing 0,
전환 6회). 기본 medium/N=5(0.140)보다 9배 낮은 mismatch. 재구성 지연(PR_INVALID) 2·4·8
경우에서 skipped = switch×PR로 선형(6·12·24프레임) → 전환수를 줄이는 것이 지연 비용의 축.

---

## Stage 2 — 이미지 지표 (`results/image_metrics_{exdark,coco}.csv`)

| dataset | arm | out shape | Y mean | 포화율% | dark-ratio(전→후) | gain/γ 중복 |
|---|---|---|---|---|---|---|
| ExDark(n=98) | none | 778×606 | 14.0 | 1.87 | 0.919 | False |
| ExDark | normal | 778×606 | **11.0** | 0.72 | 0.919→0.932 | False |
| ExDark | lowlight | 389×303 | 25.5 | 2.61 | 0.919→0.842 | False |
| COCO(n=113) | none | 577×494 | 64.2 | 6.29 | 0.544 | False |
| COCO | normal | 577×494 | 54.7 | 1.44 | 0.544→0.611 | False |
| COCO | lowlight | 288×247 | 120.7 | **11.25** | 0.544→0.302 | False |

- **normal(baseline core)이 오히려 어둡게 만듦:** BLC(−16)+AWB에 gain이 없어 dark scene을
  더 어둡게(ExDark Y 14→11, dark-ratio 0.919→0.932). "정상 경로를 저조도에" = 악화.
- **lowlight tone은 밝힘:** ExDark Y 14→25.5, dark-ratio 0.919→0.842. 단 COCO에선 포화율
  11.25%로 과다(정상조도에 저조도 경로 = 과처리).
- **형상 반감(Policy A) 확인:** lowlight 출력이 H/2×W/2.
- **gain/γ 중복 = False**(구조적, baseline core 무침범) — 아키텍처 불변식 유지.
- **checker 과트리거 발견:** naive 임계(Y<50, 40%)로 pseudo-RAW COCO의 89/113이 low-light로
  트리거 → checker 임계 보정 필요(Stage 1 밴드와 별개로 dark-level 재보정).

---

## Stage 3 — 정확도 mAP, 조건표 A~G (2 detector)

`raw → arm → YOLO → mAP(ultralytics val)`. 라벨은 두 데이터셋 모두 COCO-80 id(remap 없음).

### mAP@[.5:.95] (핵심 지표)
| 조건 | dataset · arm | YOLOv8n | YOLOv8s |
|---|---|---|---|
| **A** | ExDark · none | **0.1561** | **0.2236** |
| **B** | ExDark · normal | 0.0680 | 0.1249 |
| **C** | ExDark · lowlight | 0.0554 | 0.1276 |
| **G** | ExDark · adaptive | 0.0554 | 0.1276 |
| **D** | COCO · none | **0.3276** | **0.4280** |
| **E** | COCO · normal | 0.2879 | 0.3775 |
| **F** | COCO · lowlight | 0.2574 | 0.3402 |
| **G** | COCO · adaptive | 0.2590 | 0.3486 |

(mAP@50: ExDark none 0.306/0.406, COCO none 0.471/0.611 — 순서 동일. CSV 참조.)

### 견고한 결론
1. **모든 조건·두 detector에서 `none`(무처리 demosaic)이 최고.** reset 아키텍처의
   baseline core(gain/gamma 제거)와 두 tone RM 모두 **plain demosaic 대비 mAP를 떨어뜨림.**
2. **de-duplication(정상 tone=identity)이 저조도 mAP를 악화:** gain 없는 baseline core가
   dark scene을 더 어둡게 만들어 normal arm이 none보다 크게 낮음(ExDark 0.156→0.068).
   → **RM_NORMAL_TONE을 identity가 아니라 register gain으로** 둬야 함(구 08-e2의 reg_only가
   최고였던 것과 정합).
3. **low-light tone RM(bin+gain+gamma-4.0, Policy A)은 guardrail 탈락:** 저조도에서도
   none을 못 이김(0.055~0.128 < 0.156~0.224). gamma-4.0 과증폭 + H/2 해상도 손실이 원인.
   → 더 약한 tone/denoise 지향 RM 또는 Policy B(형상보존)로 재설계 필요.
4. **정상조도(COCO)에서도 저조도 경로는 이득 없음**(F<E<D) → 장면 적응 스위칭의 방향
   자체는 정당(어두울 때만 켜야 함)하나, **현 RM 후보는 mAP 근거를 주지 못함.**

### 함의 (논문/설계, 방향 A와 정합)
- 본 실측은 방향 A 서사를 **강화**한다: **mAP는 최소·register 처리가 담당**하고, 구조적
  tone RM은 mAP 향상 근거가 약하다 → **DFX/RM의 정당화는 자원/전력**(Stage 4~6)이어야 함.
- 즉시 반영할 설계 수정:
  (a) **RM_NORMAL_TONE = register gain**(identity 아님) — de-dup은 유지하되 gain은 tone RM에.
  (b) **low-light RM 재포지셔닝** — gamma-4.0 완화(γ≈2.5~3.0), Policy B 또는 denoise형,
      binning 해상도 손실 완화(bilinear 업샘플).
  (c) **checker dark-level 재보정** — COCO 과트리거 제거(adaptive가 lowlight로 붕괴 방지).

### 주의 (결과 한계)
- SW proxy: pseudo-RAW는 이미 ISP된 JPEG 역변환, RGGB nearest demosaic, n=71~80(크기
  불일치 스킵), CPU. 절대값보다 **arm 순서**가 판단 근거(guardrail).
- C-sim golden은 GRBG, 본 eval은 RGGB — 상대 behaviour 비교용(구 08-e2와 동일 관례).
- 구 08/11(static/reg/bin/fp variant) 수치와 직접 비교 금지: arm 정의가 다름
  (여기 normal=baseline core no-gain, 구 reg_only=demosaic+gain).

---

## 산출물
- Stage 1: `results/scheduler.csv`, `results/scheduler_sweep.csv`
- Stage 2: `results/image_metrics_exdark.csv`, `results/image_metrics_coco.csv`
- Stage 3: `results/map_newrm_{exdark,coco}_{yolov8n,yolov8s}.csv`
- 도구: `tools/{newrm_pipeline,scheduler_sweep,image_metrics_newrm,eval_map_newrm}.py`

## 다음
1. 설계 수정 (a)(b)(c) 반영 후 Stage 3 재측정 → guardrail 재판정.
2. Stage 4~6(HW): 자원/전력/PR — DFX 정당화의 실제 축.
