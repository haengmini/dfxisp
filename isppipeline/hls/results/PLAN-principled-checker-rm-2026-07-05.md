<!--
File   : isppipeline/hls/results/PLAN-principled-checker-rm-2026-07-05.md
Date   : 2026-07-05 21:18 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3 (successor to ver1/ver2)
-->
# 실행 계획 — Checker & Low-light RM 원리 기반 재설계 + 실험 (principled-v3)

**작성:** 2026-07-05 21:18 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` · **캠페인 버전:** `principled-v3`

## 0. 목표 (goal 명령 4파트)

1. **Checker**의 수학적·과학적 원리를 정의하고 근거를 명확히 → 원리에 따른 새 버전 구현 + 실험.
2. **저조도 이미지의 CV/MV 처리 원리 + feature 추출 기준**을 정의하고 근거를 명확히 → 원리에 따른 low-light RM ISP 새 버전 구현 + 실험.
3. 모든 탐색·실험 후 **이전 버전과 비교 분석** 실험 + 결과 분석.
4. 에이전트 팀 병렬 배치(모델 효율 배분), 계획 우선, 결과는 **날짜/시간/버전 포함 md**.

## 1. 현 상태 진단 (why this plan)

이론은 이미 상당히 축적됨(선행 문서):
- `checker-improvement-theory/simulation/analysis-2026-07-0{3,4}.md` — dark16>0.62(Youden J*), Bayes-opt 55%, logmean 후보까지 이론·시뮬 완료.
- `lowlight-mv-isp-survey-2026-07-03.md` — SNR/VST/binning 원리 + 3rd/4th RM 후보(RM_TONE_LUT_PARAM, RM_LL_BIN_DN) 서베이 완료.

**갭:** 이 권고들이 아직 (a) 단일 정본 "원리 정의" 문서로 응결되지 않았고, (b) **실제 코드 버전 + 실험(mAP/통계)으로 구현·검증되지 않음.** 현행 canonical checker는 여전히 `DARK_RATIO_PCT=80` + dark 임계(=중간톤), 현행 low-light RM은 bin+gain+gamma 단일안. 본 캠페인은 원리→버전→실험→비교의 갭을 메운다.

## 2. 데이터·환경 (실험 가능성 확인됨)

- 데이터: `data/coco_val`(575 raw_bin+img+label), `data/exdark_val`(575 raw_bin, 491 img). pseudo-RAW little-endian uint16 RGGB.
- Detector: `model/detectors/yolo/yolov8n.pt`, `yolov8s.pt`; SSD-MobileNetV1 frozen graph. ultralytics 8.4.82, torch 2.12 (CPU only — GPU 드라이버 구버전), 16 core.
- 평가 인프라(검증됨): `tools/eval_map_newrm.py`, `checker_stat_sweep.py`, `newrm_pipeline.py`, `checker_cause_analysis.py`.

## 3. 버전 정의 (무엇을 만들 것인가)

### 3.1 Checker 버전 (Agent CHK)
| 버전 | 규칙 | 원리 근거 |
|---|---|---|
| C0 (baseline, 현행) | dark50 ratio>0.80 | 기존 Youden J 1D 스윕 |
| C1 | dark16 ratio>0.62 (J*) | 감마공간 진짜 암부만 계수(광도계), [16,50) 반신호 제거 |
| C2 | dark16 ratio>0.553 (Bayes-opt) | 비대칭 비용(miss 2.9×) 반영 위험 최소 |
| C3 | logmean 임계 | log-도메인 metering (AUC 0.978), 암부 해상도 강조 |
| C4 | 2-feature(dark16+분산/entropy) | 결합 판별 검정(이론은 기각 예측 — 실측 확인) |
+ 전 버전 공통: hysteresis 밴드(δ=2%p, Schmitt) 적용/미적용 ablation.

### 3.2 Low-light RM 버전 (Agent RM)
| 버전 | 구성 | 원리 근거 |
|---|---|---|
| R0 (baseline, 현행) | 2×2 bin + gain2 + gamma2 | 현행 canonical |
| R1 RM_TONE_LUT_PARAM | full-res, GAT/Anscombe형 VST LUT(+soft-knee), no binning | tone=최중요 stage(ISP4ML), VST=Poisson 분산안정화, 해상도 보존 |
| R2 RM_LL_BIN_DN | 2×2 bin + edge-preserving 3×3 denoise + VST tone | 저조도 실패주범=low SNR, binning+경량 denoise 시너지(반폭 line buffer) |
| R3 (option) RM_TONE_CLAHE | local tone(tile hist, frame-lag) | 저대비 보상, YOLOX+CLAHE +1.13%p |

## 4. 실험 설계 (어떻게 검증)

- **Checker 실험:** `checker_stat_sweep` 통계로 각 버전 AUC/recall/FT/J + overlap coefficient + hysteresis flapping rate. 상위 2개 + baseline은 adaptive-arm mAP(ExDark+COCO, yolov8n, n≥150)로 downstream 검증.
- **RM 실험:** 각 RM 버전 × {ExDark, COCO} × yolov8n mAP@0.5 / @0.5:0.95. object-size별 AP 분해(small/med/large — binning 해상도 손실 정량화). 상위안 yolov8s 또는 SSD 교차검증.
- **비교(Part 3):** C0 vs C1..C4, R0 vs R1..R3 표. 기대 mAP 손실(비용가중), 자원(csynth 가능 시), 결론.

## 5. 에이전트 팀 배치 (병렬)

| 에이전트 | 모델 | 트랙 | 산출물 | 실행 |
|---|---|---|---|---|
| **CHK** | opus | Checker 전 트랙 (원리 정의 → C1..C4 구현 → 통계+mAP 실험 → 결과 md) | `checker-principles-2026-07-05.md`, `checker-principled-versions-2026-07-05.md`, `tools/checker_versions.py` | 병렬 (Phase 1) |
| **RM** | opus | Low-light RM 전 트랙 (원리 정의 → R1..R3 구현 → mAP 실험 → 결과 md) | `lowlight-feature-principles-2026-07-05.md`, `lowlight-rm-principled-versions-2026-07-05.md`, `tools/rm_versions.py` | 병렬 (Phase 1) |
| **CMP** | opus (orchestrator 직접) | 교차 비교·종합 | `principled-comparison-2026-07-05.md` | Phase 2 |
| **XCHK** | sonnet | 상위안 교차 detector(yolov8s/SSD) 검증 | 비교 md에 병합 | Phase 2 (선택) |

**충돌 회피:** CHK/RM은 서로 다른 새 파일만 생성(기존 `dfxisp_accel.cpp`/`newrm_pipeline.py` 파괴적 편집 금지, 필요 시 import/복제). 동일 브랜치 동시 작업.

## 6. 산출물 규칙

모든 결과 md는 상단에 **날짜/시간(KST)/브랜치/캠페인 버전** 헤더 포함. 재현 커맨드 명시. 근거 문헌·수치는 스크립트 출력에서 직접 인용(결정적).

## 7. 완료 정의

- [ ] Checker 원리 정본 md + C1..C4 구현 + 실험 결과 md
- [ ] Low-light 원리 정본 md + R1..R3 구현 + mAP 실험 결과 md
- [ ] 이전 버전 대비 비교 분석 md (mAP/J/자원)
- [ ] 전 산출물 커밋 + GitHub 백업
