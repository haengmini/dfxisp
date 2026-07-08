<!--
=============================================================================
File   : isppipeline/hls/results/checker-principled-versions-2026-07-05.md
Date   : 2026-07-05 21:30 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3
Track  : CHK (goal command Part 1) — 원리 기반 체커 버전 C0..C4 구현·실험 결과
Function: checker-principles-2026-07-05.md의 5개 원리를 코드 버전으로 구현
          (tools/checker_versions.py)하고, 1150프레임 통계 + adaptive-arm mAP로
          검증. C0(현행) vs C1(원리 winner) downstream 비교 포함.
Repro  :
  python3 tools/checker_stat_sweep.py --compute --csv results/scratch_frame_stats.csv
  python3 tools/checker_versions.py --csv results/scratch_frame_stats.csv
  python3 tools/scratch_adaptive_map_principled.py --root ../../data/exdark_val \
        --tag ExDark --limit 150 --out results/scratch_adaptive_map_principled.csv
  python3 tools/scratch_adaptive_map_principled.py --root ../../data/coco_val \
        --tag COCO --limit 150 --out results/scratch_adaptive_map_principled.csv
=============================================================================
-->
# 원리 기반 체커 버전 실험 결과 (principled-v3, 2026-07-05)

**작성:** 2026-07-05 21:30 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` ·
**캠페인:** `principled-v3`

> 원리 정본: `checker-principles-2026-07-05.md`. 구현: `tools/checker_versions.py`
> (기존 `dfxisp_accel.cpp`/`checker_stat_sweep.py` 파괴적 편집 없음 — 후자를 import).
> 데이터: `data/{coco_val,exdark_val}`(각 575, 총 1150) 전수 통계 + n=150/클래스
> adaptive-arm mAP(yolov8n, torch 2.12 CPU). 모든 수치는 본 브랜치에서 직접 재실행.

## 1. 버전 정의 (원리→규칙)

| 버전 | 규칙 | 원리 근거 | HW 비용 |
|---|---|---|---|
| **C0** (현행) | dark50 ratio > 0.80 | 기존 1D Youden 스윕(균등비용) | 비교기1+카운터1 |
| **C1** (J*) | dark16 ratio > 0.62 | 원리2 감마공간 진짜 암부, [16,50) 반신호 제거 | **C0와 동일 RTL**(레지스터값·PCT만) |
| **C2** (Bayes) | dark16 ratio > 0.553 | 원리1 비대칭비용(miss 2.89×) Bayes-opt | C1과 동일 |
| **C3** (log) | logmean < θ* (θ*=−3.218 bit) | 원리3 log-도메인 metering | 256-엔트리 log2 LUT+누산기+나눗셈1 |
| **C4** (2-feat) | dark16>0.48 AND entropy<5.55 | 원리1 결합검정(이론 기각 예측 실측 확인) | 256-bin 히스토그램 BRAM+비교기2+AND |

전 버전 공통: hysteresis 밴드 δ=2%p(Schmitt, 원리5). C4의 (a,b)=(0.48, 5.55)는
`checker_versions.py`가 데이터에서 J-max로 그리드 적합한 값.

## 2. 통계 실험 (전수 1150프레임, `checker_versions.py`)

| 버전 | AUC | 운영점 | recall | FT | J | overlap↓ | **R (mAP손실/frame)** |
|---|---|---|---|---|---|---|---|
| C0 dark50>0.80 | 0.9632 | 0.800 | 0.918 | 0.125 | 0.793 | 0.193 | 0.00699 (기준) |
| **C1 dark16>0.62** | 0.9766 | 0.620 | 0.936 | 0.089 | 0.847 | 0.139 | **0.00531 (−24.0%)** |
| C2 dark16>0.553 | 0.9766 | 0.553 | 0.965 | 0.134 | 0.831 | 0.139 | 0.00454 (−35.1%) |
| C3 logmean<−3.218 | 0.9780 | (J-fit) | 0.939 | 0.090 | 0.849 | 0.146 | 0.00515 (−26.3%) |
| C4 dark16∧entropy | 0.9784 | (J-fit) | 0.958 | 0.101 | 0.857 | 0.136 | 0.00429 (−38.6%) |

- **R = ½(miss·C_miss + FT·C_FA)**, C_miss=0.1118 / C_FA=0.0387 (ablation 실측,
  analysis §4). overlap = 두 클래스 score 분포 겹침(Bayes-오류 하한 proxy, 낮을수록 우월).
- **모든 원리 버전(C1~C4)이 C0를 J·R·AUC·overlap 전 지표에서 지배.** dark 임계를
  감마공간 진짜 암부로 내린 것(C0→C1)만으로 R −24%, overlap 0.193→0.139.
- **C2(Bayes-opt)**: 비대칭비용을 반영해 R을 −35%까지 낮추나 FT를 0.089→0.134로
  올림(원리1 트레이드) — recall 최우선(꼬리 암전장면 최소화) 배포에 적합.
- **C4(2-feature)**: J·R 지표상 근소 최상(J 0.857, R 0.00429)이나 (i) C1 대비 ΔJ=+0.010은
  5-fold CV의 FT fold-분산(±0.03~0.04, simulation §6)에 묻히는 크기, (ii) entropy는
  256-bin 히스토그램 BRAM + frame-end log-LUT를 요구하고 "저entropy=어두움" 의미론이
  균일-밝음 장면에서 오동작할 OOD 위험(simulation §7). → **이론 예측대로 실측에서도
  통계량 결합의 순이득은 HW/robustness 비용을 정당화하지 못함.** (theory 예측 "2-feature
  기각"을 정량 확인: 단독 대비 유의 이득 없음.)

## 3. Hysteresis flapping (원리5, steady 이상값=0회/100fr)

| 버전 | 실측 jitter σ | δ 밴드 | 단일임계 flaps | hysteresis flaps |
|---|---|---|---|---|
| C0 | 0.0020 | 0.020 | 3.27 | **0.00** |
| C1 | 0.0023 | 0.020 | 1.50 | **0.00** |
| C2 | 0.0023 | 0.020 | 3.71 | **0.00** |
| C3 | 0.0120 | 0.043 | 16.69 | **0.00** |
| C4 | 0.0023 | 0.020 | 6.43 | **0.00** |

- σ는 1/16 Bayer-quad phase-std 실측(simulation §4). δ=2%p(=실측 p95 jitter의 3.6σ)로
  전 버전 steady flapping 0회. **C3(logmean)은 단일임계 flapping이 16.7회로 최악** —
  연속값이라 경계 밀도가 높음; hysteresis 없이는 부적합. C1은 단일임계에서도 flapping이
  가장 낮음(1.50) — 경계가 두 분포의 더 빈 골짜기에 놓임(원리2 overlap 축소의 부수효과).

## 4. Downstream adaptive-arm mAP — C0 vs C1 (yolov8n, n=150/클래스)

가장 실용적(HW 변경 0) 원리 winner **C1**을 현행 **C0**와 adaptive arm에서 직접 비교.
동일 normal/lowlight 렌더러(`newrm_pipeline.run_arm`)를 쓰고 **per-frame 선택만** 다르게
하여 mAP 델타가 오롯이 체커에서 나오게 함(`scratch_adaptive_map_principled.py`).

| 데이터셋 | 체커 | LOW_LIGHT 라우팅 | mAP@[.5:.95] | mAP@50 |
|---|---|---|---|---|
| ExDark(저조도) | C0 dark50>0.80 | 133/150 | 0.0589 | 0.1300 |
| ExDark | **C1 dark16>0.62** | 134/150 | 0.0512 | 0.1191 |
| COCO(정상) | C0 dark50>0.80 | 20/150 | 0.3304 | 0.4555 |
| COCO | **C1 dark16>0.62** | **11/150** | **0.3308** | **0.4596** |

**라우팅 불일치 분해**(결정적, CSV 재계산):

| 데이터셋 | 불일치 프레임 | C0만 저조도 | C1만 저조도 | 순 변화 |
|---|---|---|---|---|
| ExDark | 8 | 4 | 4 | **0 (대칭 스왑)** |
| COCO | 11 | **10** | 1 | **−9 저조도(=FT 감소)** |

**해석 (정직):**

1. **COCO에서 원리 예측이 그대로 실현.** C1은 정상장면 false-trigger를 20→11 프레임으로
   줄인다(불일치 11장 중 10장이 "C0가 정상 COCO를 저조도로 오판→C1이 교정"). 통계
   실험의 FT 0.125→0.089와 방향·크기 일치. downstream 효과: COCO mAP 0.3304→**0.3308**,
   mAP@50 0.4555→**0.4596**(+0.004) — 정상장면을 불필요히 binning(반해상도)하지 않아 소폭
   상승. **부수 이득: PR 전환 프레임 수 20→11(−45%)로 c_PR 노출 감소**(원리1·5).
2. **ExDark에서는 C0≈C1.** 순 라우팅 동일(133/133 저조도, 둘 다 ~89% 암부 포착), 8장이
   경계 근방에서 대칭 스왑. mAP 차(0.0589 vs 0.0512)는 이 8장의 near-boundary 스왑에서
   오는 것으로 **n=150 노이즈 대역(±0.02, analysis §5) 안**이며 방향성 신호가 아니다.
   ExDark에서 checker를 더 공격적으로(dark16) 내려도 대부분 이미 저조도로 가므로 recall
   여지가 작다 — 이는 통계 실험(ExDark recall이 이미 0.92~0.94로 포화)과 정합.
3. **결론:** checker 개선의 downstream 가치는 analysis §5 예측대로 **평균 mAP가 아니라
   (i) 정상장면 false-trigger·PR 빈도 감소, (ii) 꼬리 암전장면 포착**에 있다. C1은 (i)을
   HW 변경 0으로 명확히 달성하고 ExDark에서 손해가 없다(노이즈 내 동률).

## 5. 권고 (RECOMMENDATION)

**1순위 채택: C1 (dark16 ratio > 0.62) + hysteresis δ=2%p(진입 64% / 해제 60%).**

- **근거:** (a) 통계 전지표에서 C0 지배(R −24%, J +0.054, overlap 0.193→0.139),
  (b) downstream에서 COCO FT 20→11·mAP +0.004, ExDark 무손해, (c) **HW 변경 0** —
  `dark_pixel_threshold` 레지스터를 HLS raw12 도메인 **256**(=16<<4, 데이터셋 도메인
  4096 등가; 원리 문서 도메인 주의), `DARK_RATIO_PCT` 80→62(hysteresis 시 ENTER=64/
  EXIT=60 + mode FF 1개). 원리4의 1/16 subsample은 무손실 옵션으로 병행 가능.
- **2순위(배포 조건부): C2 (dark16 > 0.553, Bayes-opt).** miss 비용이 지배적(야간
  안전 등 recall 최우선) 배포에서 R을 추가 −11%p 낮춤. 단 FT +4.5%p(PR 빈도↑)를
  감수하며, 55% vs 62% 최종 선택은 **보드에서 c_PR 실측 후 확정** 권고.
- **기각: C3(logmean)·C4(2-feature).** C3는 dark16 대비 이득 없이(ΔJ≈0.002) log2 LUT+
  나눗셈+최악 flapping을 요구. C4는 J 근소 우위가 fold 분산에 묻히고 히스토그램 BRAM+
  entropy OOD 위험 — 이론의 "통계량 결합 기각" 예측이 실측으로 재확인됨.

## 6. 한계

1. **pseudo-RAW 노이즈 통계 부재** — dark16 절대값은 실센서에서 black level/노출로
   재보정 필요(상대 결론 "낮은 dark 임계 우월"은 유지 전망; 원리3 τ(s,g)는 실센서 활성화).
2. **n=150 CPU 서브셋** — ExDark mAP 델타는 노이즈 대역 내. 전수 n=575 어댑티브 런이면
   FT 감소의 mAP 효과를 더 또렷이 볼 수 있으나 본 캠페인 wall-clock 예산 외.
3. **비용치(C_miss/C_FA) n=31/39 ablation 기반** — R 순위는 강건하나 55% vs 62% 미세선택엔
   부족. c_PR은 R에 미포함(원리5 시간축이 담당).
4. **hysteresis σ는 공간 샘플링 proxy** — 실제 시간축 jitter 보드 실측 필요.

## 산출물

- `tools/checker_versions.py` — C0..C4 구현 + 통계/flapping 평가 (신규).
- `tools/scratch_adaptive_map_principled.py` — C0 vs C1 adaptive mAP 러너 (신규 scratch).
- `results/scratch_frame_stats.csv` — 1150×108 per-frame 통계 (재생성 가능).
- `results/scratch_adaptive_map_principled.csv` — adaptive mAP 결과.
