<!--
=============================================================================
File   : isppipeline/hls/results/experiment_ver2_2026-07-02.md
Date   : 2026-07-02
Time   : 13:05 KST
Function: ver2 checker dark-level 재보정 결과 보고서 (ver1 아키텍처 위의 파라미터 수정)
Goal   : SPEC §11 (c)로 남겨뒀던 "checker dark-level 재보정"을 실측 기반으로 수행하고,
         COCO 과트리거를 줄여 adaptive arm이 실제 조도에 맞게 동작하는지 검증
=============================================================================
-->
# ver2 — checker dark-level 재보정

> ver1(RAW-domain-first)은 HW/C-sim 정본에 반영 완료(`58aa611`). 남은 항목 (c) checker
> dark-level 재보정을 이번에 수행. 대상: `dfxisp_accel.cpp`/`gen_golden_vectors.py`의
> `DARK_RATIO_PCT`, `isp_pipeline_ver1.py`의 `DARK_RATIO`.

## 1. 문제

Stage 2 실측(2026-07-02 이전)에서 발견: naive 임계(`dark_ratio > 0.40`, `Y<50`)로 **정상조도
COCO의 89/113(79%)이 low-light로 오판**됨. checker가 사실상 거의 모든 프레임을 저조도로
분류해 adaptive arm이 무의미해짐.

## 2. 재보정 방법

`data/{coco_val,exdark_val}`(각 n=150~200)에서 `Y<50` dark-ratio 분포를 실측하고, 후보
임계 `t ∈ [0.40, 0.95]`에 대해 **Youden's J = ExDark recall(dark_ratio>t) − COCO
false-trigger(dark_ratio>t)** 를 스윕.

| t | ExDark recall | COCO false-trigger | J |
|---|---|---|---|
| 0.40(구) | 1.000 | 0.795 | 0.205 |
| 0.70 | 0.945 | 0.230 | 0.715 |
| 0.75 | 0.915 | 0.160 | 0.755 |
| **0.80** | **0.900** | **0.110** | **0.790** |
| 0.83(J-max) | 0.870 | 0.070 | 0.800 |
| 0.90 | 0.780 | 0.040 | 0.740 |

**채택: 0.80**(round, J-max 0.83에 근접, recall 0.90 유지).

## 3. 반영

- HW/C-sim 정본: `DARK_RATIO_PCT 40 → 80`(`src/dfxisp_accel.cpp`, `tools/gen_golden_vectors.py`).
- SW ver1: `DARK_RATIO 0.40 → 0.80`(`tools/isp_pipeline_ver1.py`).
- golden vector에 **경계 회귀 케이스 2종 추가**(`auto_boundary_ratio_75_8x8`=75%dark→NORMAL 유지
  검증, `auto_boundary_ratio_86_8x8`=86%dark→LOW_LIGHT 트리거 검증) — 새 임계값이 실제로 동작함을
  fixture 레벨에서 증명.
- `make verify`: **bit-exact 통과(646px, 11 cases)**. 아키텍처 gate 전부 PASS.

## 4. mAP 재측정 (adaptive arm만, 다른 arm은 checker 영향 없음)

| dataset | arm | ver1(구 checker 0.40) | ver2(신 checker 0.80) | Δ |
|---|---|---|---|---|
| ExDark | adaptive | 0.0586 | 0.0606 | +3% |
| COCO | adaptive | 0.2522 | **0.2752** | **+9%** |

참고(동일 dataset의 다른 arm, checker 무관): COCO none=0.3276, normal=0.2772, lowlight=0.2647.
→ **COCO adaptive(0.2752)가 이제 normal(0.2772)에 근접** — 재보정 전에는 대부분 lowlight로
잘못 라우팅되어 lowlight(0.2647)에 가까웠음. checker가 의도대로 동작하기 시작함을 확인.

## 5. 결론

1. **재보정 성공:** COCO 과트리거 79.5%→11%로 감소, adaptive arm이 실제 조도에 맞게
   normal/lowlight를 선택하기 시작.
2. **여전히 `none`(무처리)이 최고**(SW proxy 공통 한계, ver1 보고서와 동일 결론) — checker
   재보정은 "올바른 arm을 고르는" 문제를 풀 뿐, ISP arm 자체가 사전학습 검출기 분포에서
   mAP를 개선하지 못하는 문제는 그대로.
3. SPEC §11의 계획된 개정 (c) 완료. 남은 항목: (d) Policy B/denoise형 RM, 최종 판정(보드
   DPU+real-RAW).

## 산출물
- 코드: `src/dfxisp_accel.cpp`, `tools/gen_golden_vectors.py`, `tools/isp_pipeline_ver1.py`,
  `tests/test_dfxisp_csim.cpp`(경계 회귀 assert)
- 결과: `results/map_ver2_{exdark,coco}_yolov8n_adaptive.csv`
- 문서: `SPEC.md`, `RESEARCH.md`, `isppipeline/hls/README.md` 임계 갱신
