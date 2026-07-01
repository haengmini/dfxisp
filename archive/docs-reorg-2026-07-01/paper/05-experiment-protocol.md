---
type: experiment-protocol
title: "DFXISP — 실험 프로토콜 및 ZCU104 실측 빈 레이아웃"
project: DFXISP
created: 2026-06-28
status: ready-to-execute (소프트웨어 단계) / awaiting-board (하드웨어 단계)
note: "실측 직전까지의 모든 절차 확정. measurements/*.csv는 보드에서 채울 빈 템플릿."
---

# 실험 프로토콜 (Experiment Protocol)

> 목적: 4-variant(Static/Reg-only/DFX-Bin/DFX-FP)를 동일 조건으로 비교. 측정값은 `measurements/*.csv`에 기록 → [Tab4–Tab7] 자동 반영.
> 단계 경계: **SW 단계(보드 불필요)** 와 **HW 단계(ZCU104 필요)** 를 명확히 구분한다.

## 0. 공통 설정
> **방향 A 확정(2026-06-29):** DFX 1순위 RM = **DFX-Bin(2×2 binning)**; 자원 main baseline = **static all-resident**(모든 블록 상주, DFX 없음); **mAP guardrail = register-only 대비 절대 1.0 mAP point(≈상대 5%) 이내**. 1차 지표는 자원/전력, mAP는 guardrail.
- 해상도: 개발 640×480, 평가 1280×720 @ 30fps (frame budget 33.3 ms).
- 입력: COCO_5000 / ExDark_5000 pseudo-RAW (정본 `DFXISP/dataset/`).
- 고정 seed, 동일 detector(예: YOLO 계열 또는 Vitis AI model zoo), 동일 NMS/conf threshold.
- 각 variant는 동일 front-end/back-end, low-light block만 교체.

## 1. SW 단계 (보드 불필요 — 지금 진행 가능)
### E1. Golden bit-exact
- Python golden ↔ HLS C-sim RGB888/RGB32 비교. DFX-Bin/DFX-FP 골든 케이스 포함(어두운 평탄부/에지/하이라이트/threshold 경계).
- 출력: `measurements/map.csv`의 `bit_exact_mismatch` 행.
### E2. pseudo-RAW mAP
- 파이프라인: dataset → (variant별 ISP C-model) → detector → mAP(COCO eval).
- variant별 COCO/ExDark mAP, low-light subset AP 기록 → `measurements/map.csv`.
- 주의: detector·평가코드 버전 고정, 동일 입력 정규화.
### E3. Scheduler 시뮬레이션
- 시퀀스(밝기 변화 포함)에 baseline checker vs hysteresis/temporal/min-dwell 적용.
- mode mismatch·switch count·thrashing·skipped frames → `measurements/scheduler.csv`.
- (frame trace는 SW로 가능; 실제 PR 중 frame stall만 HW 단계.)

## 2. HW 단계 (ZCU104 필요 — 빈 레이아웃)
### E4. HLS csynth/cosim (Vitis HLS 워크스테이션)
- variant별 II/latency/자원 추정. RTL cosim 통과.
- 명령: `make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls` / `... cosim hls`.
- 출력: `measurements/resource.csv`의 Fmax/timing, `pr_latency.csv` 초기 추정.
### E5. Vivado implementation + DFX flow
- static + RP, 부분 비트스트림 2종(DFX-Bin/DFX-FP) 생성.
- impl 후 LUT/FF/BRAM/DSP, partial bitstream size → `measurements/resource.csv`.
### E6. 보드 측정 (ZCU104)
- 전력(PMBus/보드 측정), FPS/throughput → `measurements/power_perf.csv`.
- PR latency(ICAP, drain 포함), frame stall → `measurements/pr_latency.csv`, `power_perf.csv`.
- 실제 시퀀스에서 scheduler 안정성 재측정 → `measurements/scheduler.csv` 갱신.

## 3. 분석 계획 (측정 후)
- [Fig8] mAP–resource–power trade-off 산점도.
- 핵심 주장 검증표:
  1. register-only가 못 메우고 DFX가 메우는 mAP gap이 존재하는가?
  2. DFX가 normal 모드 자원/전력을 register-only 대비 줄이는가?
  3. DFX-FP가 DFX-Bin 대비 mAP를 올리는가(해상도 보존 효과)?
  4. PR latency가 scene dwell 예산 내인가?
- 각 주장은 "확인/부분확인/반증" 중 하나로 결론(가설-결과 분리).

## 4. 측정 파일 인덱스 (measurements/)
| 파일 | 채우는 단계 | 대응 표/그림 |
|---|---|---|
| `map.csv` | E1,E2 (SW) | Tab6 |
| `scheduler.csv` | E3 (SW) + E6 (HW) | Tab7 |
| `resource.csv` | E4,E5 (HW) | Tab4 |
| `power_perf.csv` | E6 (HW) | Tab5 |
| `pr_latency.csv` | E4,E6 (HW) | Fig7, Tab5 |

> 모든 빈 셀은 `TODO(측정)`. 채울 때 단위·조건(해상도/seed/detector ver)을 같은 행 비고에 적는다.
