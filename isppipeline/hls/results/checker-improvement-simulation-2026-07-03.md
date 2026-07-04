<!--
=============================================================================
File   : isppipeline/hls/results/checker-improvement-simulation-2026-07-03.md
Date   : 2026-07-03
Time   : 23:50 KST
Function: scene checker(checker_select_mode) 통계량 개선 정량 시뮬레이션 —
          1150프레임 실데이터 전수 스윕(ROC/AUC/operating point/subsampling/
          hysteresis/5-fold CV).
Goal   : design-limitations §"dark_pixel_threshold naive" 지적에 대한 응답 —
          현행 dark-ratio(Y<50 등가, >80%) 대비 HW 1-pass로 계산 가능한 대안
          통계량들을 실측 비교하고, 임계값+hysteresis+HW 비용까지 포함한
          순위화된 권고를 도출.
Rev    : 2026-07-04 — Codex adversarial review [high] 반영: 임계값의 RAW 도메인
          구분(데이터셋 pseudo-RAW16 vs HLS raw12)을 §1.0에 명시하고, §7 실행
          제안의 HLS 주입값을 raw12 도메인(256=16<<4)으로 정정. C-sim/golden
          경계 회귀 테스트 추가(tests/test_dfxisp_csim.cpp,
          tools/gen_golden_vectors.py: auto_raw12_thr256_*).
=============================================================================
-->
# checker 통계량 개선 시뮬레이션 (2026-07-03)

> ver2 재보정(`experiment_ver2_2026-07-02.md`)은 **통계량은 고정한 채**(dark-ratio,
> `Y<50` 등가) 비율 임계만 0.40→0.80으로 옮겼다. 이번에는 **통계량 자체**를 스윕한다.
> 제약: RAW 픽셀 1-pass 스트리밍 + 정수 연산(256-bin histogram BRAM 허용, full sort/
> float 불가). 데이터: `data/coco_val/raw_bin`(575, NORMAL 정답) +
> `data/exdark_val/raw_bin`(575, LOW_LIGHT 정답), 총 1150프레임 전수.

**핵심 결론 (요약):**

1. **현행 dark50(=`dark_pixel_threshold`=12800, 8-bit 50 등가) 기준선은 baseline으로
   재현됨** — 전수(575/575)에서 recall=0.918 / false-trigger(FT)=0.125, J=0.79로 문서값
   J=0.79와 일치. (단 recall/FT 개별값은 재보정 당시 부분집합 n=150~200과 ±0.02~0.04 차이.)
2. **같은 HW에서 dark 임계만 8-bit 16으로 내리면(dark16) AUC 0.963→0.977,
   J 0.809→0.849** (recall 0.937 / FT 0.089). **RTL 변경 0** — 런타임 레지스터
   `dark_pixel_threshold`를 8-bit 16 등가로(HLS raw12 도메인 **256**=16<<4;
   본 리포트의 데이터셋 pseudo-RAW16 도메인으로는 4096=16<<8, §1.0 도메인 주의
   참조) + `DARK_RATIO_PCT` 80→62.
3. log-mean(AE 표준 log-average luminance, AUC 0.978)·entropy(0.977)·p50(0.972)도
   dark16과 사실상 동급 — 추가 HW(LUT/histogram)를 정당화할 만큼의 이득은 없음.
4. **1/16 subsampling(Bayer-quad 보존)은 사실상 공짜** (ΔAUC ≤0.0001) — checker
   pass의 메모리 트래픽을 16배 줄일 수 있음. hysteresis는 dark-ratio ±0.02
   (진입 64% / 해제 60%)로 측정된 jitter(σ_p95=0.0055)에서 flapping을 0으로 만듦.

---

## 1. 방법론

### 1.0 RAW 도메인 주의 — 데이터셋 vs HLS (필독)

이 리포트의 모든 임계 절대값은 **데이터셋 도메인**이다. 두 도메인은 다르다:

| 도메인 | 스케일 | 8-bit 임계 T8의 값 | dark16 | dark50(현행) | 근거 |
|---|---|---|---|---|---|
| 데이터셋 pseudo-RAW (.bin, 본 리포트 스윕) | 16-bit = 8-bit<<8 | T8<<8 | **4096** | 12800 | `isp_pipeline_ver1.py` SHIFT=8 |
| **HLS 파이프라인 입력 (구현 대상)** | **12-bit (0..4095)** | **T8<<4** | **256** | 800 | `dfxisp_accel.cpp` RAW12_MAX=4095, BLC=16<<4 |

**데이터셋 도메인 값 4096을 HLS `dark_pixel_threshold` 레지스터에 그대로 넣으면
12-bit 경로의 모든 유효 픽셀(0..4095)이 `raw < 4096`으로 dark 판정되어 AUTO가
사실상 항상 LOW_LIGHT로 라우팅된다** (Codex adversarial review 2026-07-04 [high]
지적). HLS/C-sim/golden 픽스처에 주입할 값은 **256**(=16<<4)이며, 기존 픽스처의
512는 raw12 도메인의 8-bit 32 등가다. 이 도메인 변환을 검증하는 경계 회귀
테스트(임계 256에서 raw==256 전 픽셀 → NORMAL, raw==255 → LOW_LIGHT)를
`tests/test_dfxisp_csim.cpp`와 golden 벡터(`auto_raw12_thr256_*`)에 추가했다.

### 1.1 데이터 및 프레임 치수 복원

- 포맷: little-endian uint16 (`np.fromfile(f, dtype="<u2")`), pseudo-RAW Bayer RGGB.
- W,H는 같은 stem의 `data/*/images/` 원본에서 복원(PIL; ExDark는 jpg/JPG/jpeg/JPEG/png
  혼재 — 확장자 대소문자 불문 glob). **주의: raw_bin은 원본 대비 even-crop 되어 있음**
  (예: COCO `000000000632` jpg 640×483 → bin 640×482 = 308480px). 크기 불일치 시
  `w -= w%2, h -= h%2` fallback으로 전 1150프레임 매칭 성공.

### 1.2 후보 통계량 (전부 1-pass 정수 연산)

프레임마다 `(raw>>8)`의 **256-bin histogram** 하나를 쌓으면 아래가 전부 유도된다
(HW: BRAM 256×~21bit + frame-end CDF walk):

| 통계량 | 정의 | histogram으로부터 |
|---|---|---|
| darkT8 (T8∈16,24,32,48,50,64) | ratio(raw16 < T8·256) | `raw16<T8·256 ⇔ raw16>>8<T8`이므로 **CDF[T8−1] 읽기 한 번** — 별도 카운터 불필요 |
| mean8 | mean(raw)/256 | (누산기 별도, 40bit) |
| logmean | mean(log2(1+(raw>>8))) | 256-entry log2 LUT 내적 (AE 표준 log-average luminance) |
| p10/p25/p50/p75/p90 | percentile | CDF walk (정수) |
| entropy | −Σ pᵢ·log2 pᵢ | frame-end 256회 log LUT+곱 |

dark50(=8-bit 50, raw16<12800)이 **현행 checker와 동일 통계량**이다 — ver2 재보정이
쓴 지표는 golden model의 demosaic-Y<50 ratio이고, HW `checker_select_mode`는 RAW
직접 비교이므로 등가 임계는 `dark_pixel_threshold = 50<<8 = 12800`. 둘 다 계산해
교차 확인했다(§2).

### 1.3 평가 프로토콜

- 분류 과제: ExDark=LOW_LIGHT(positive), COCO=NORMAL(negative). 각 통계량을 단일
  score로 보고 ROC 전체를 스윕(예측 규칙은 HW와 동일한 strict `>` 비교).
- AUC: Mann-Whitney(동점 평균순위 보정). **J\***: Youden's J(=recall−FT) 최대점.
  **NP점**: Neyman-Pearson — FT≤0.05 / ≤0.10 제약 하 최대 recall.
- Subsampling: **Bayer 2×2 quad를 통째로 유지**하고 quad-grid stride (ky,kx)=(2,2)/
  (4,2)/(4,4) → 픽셀의 1/4, 1/8, 1/16 (RGGB 채널 구성비 보존). 1/16에서는 16개
  quad-phase offset 전부에 대해 통계량을 재계산해 phase 표준편차(=공간 샘플링 노이즈,
  per-frame jitter의 실측 proxy)를 얻음.
- 5-fold CV: 셔플(seed=0) 후 4/5에서 J\* 임계 적합, 1/5에서 recall/FT 평가.

### 1.4 재현성

- 스크립트(클린 버전, 재사용 가능): `isppipeline/hls/tools/checker_stat_sweep.py`
  — `--compute`(프레임별 통계 CSV 생성, 전수 약 1.5분) / `--analyze`(모든 표 출력).
- 이번 실행의 per-frame 통계 CSV(1150행 × 108열):
  `/tmp/claude-1000/-home-mini-workspace-dfxisp/d42e8f48-9372-4e82-b1c2-02162aa5e23d/scratchpad/checker_sim/frame_stats.csv`
  (세션 scratchpad라 휘발성 — 스크립트 `--compute`로 언제든 동일 재생성, 전 과정 결정적
  seed 고정).

---

## 2. Baseline 재현 상태

| 측정 | recall(ExDark) | FT(COCO) | J |
|---|---|---|---|
| 문서값 (ver2, n=150~200/class) | 0.900 | 0.110 | 0.790 |
| golden Y<50 ratio>0.80, **전수 575/575** | 0.915 | 0.130 | 0.784 |
| HW 등가 raw16<12800 ratio>0.80, 전수 | 0.918 | 0.125 | 0.793 |
| golden Y<50, 정렬 첫 150/class | 0.887 | 0.140 | 0.747 |
| golden Y<50, 정렬 첫 200/class | **0.900** | 0.150 | 0.750 |

**판정: 근사 재현, 정확 재현은 아님.** J=0.78~0.79는 문서값 0.79와 일치하고 recall도
n=200 부분집합에서 0.900로 정확히 맞으나, FT는 전수 0.125~0.130 / 부분집합 0.140~0.150로
문서값 0.110보다 +0.02~0.04 높다. ver2가 사용한 정확한 부분집합(150~200장 선별 기준)이
기록되어 있지 않아 그 차이로 판단(당시 스윕 스크립트 미보존). **이하 모든 비교는 전수
1150프레임 기준선(recall=0.918/FT=0.125, HW 등가)을 baseline으로 삼는다** — 결론(순위)은
이 오차에 영향받지 않음.

또한 golden Y<50 ratio와 HW raw16<12800 ratio는 판정 일치가 거의 완전(성능 차 ≤0.005)
— RAW 직접 비교인 현행 HW 구현이 demosaic-Y 기반 golden 지표의 유효한 대리임을 확인.

---

## 3. 통계량별 ROC / operating point (전수 1150프레임)

방향: dark\*, y50_ratio는 클수록 어두움; mean8/logmean/p\*/entropy는 작을수록 어두움
(표의 임계는 해당 방향 기준). NP열은 "달성 recall @ 임계".

| stat | AUC | J\* 임계 | recall | FT | J | NP FT≤0.05 | NP FT≤0.10 |
|---|---|---|---|---|---|---|---|
| **dark16** (raw16<4096) | **0.9766** | ratio>0.615 | 0.937 | 0.089 | **0.849** | 0.877 @ >0.701 | 0.941 @ >0.601 |
| dark24 | 0.9746 | >0.713 | 0.918 | 0.080 | 0.838 | 0.854 @ >0.768 | 0.930 @ >0.686 |
| dark32 | 0.9712 | >0.721 | 0.937 | 0.108 | 0.830 | 0.847 @ >0.817 | 0.929 @ >0.738 |
| dark48 | 0.9639 | >0.816 | 0.903 | 0.092 | 0.810 | 0.797 @ >0.888 | 0.904 @ >0.812 |
| **dark50 (현행)** | 0.9632 | >0.822 | 0.899 | 0.090 | 0.809 | 0.797 @ >0.891 | 0.904 @ >0.816 |
| dark64 | 0.9563 | >0.863 | 0.889 | 0.087 | 0.802 | 0.774 @ >0.919 | 0.896 @ >0.858 |
| mean8 | 0.9628 | <27.5 | 0.892 | 0.080 | 0.812 | 0.826 @ <20.8 | 0.896 @ <29.0 |
| **logmean** | **0.9780** | <3.218 | 0.939 | 0.090 | **0.849** | 0.863 @ <2.701 | 0.941 @ <3.316 |
| p10 | 0.8187 | <0.5 | 0.929 | 0.318 | 0.610 | 미달성 | 미달성 |
| p25 | 0.9416 | <1.5 | 0.922 | 0.143 | 0.779 | 미달성 | 0.812 @ <0.5 |
| p50 | 0.9721 | <9.5 | 0.953 | 0.106 | 0.847 | 0.840 @ <3.5 | 0.936 @ <7.5 |
| p75 | 0.9638 | <25.5 | 0.892 | 0.064 | 0.828 | 0.861 @ <20.5 | 0.917 @ <33.5 |
| p90 | 0.9363 | <76.5 | 0.859 | 0.092 | 0.767 | 0.786 @ <52.5 | 0.864 @ <79.5 |
| entropy | 0.9773 | <5.293 | 0.930 | 0.077 | **0.854** | 0.863 @ <4.869 | 0.948 @ <5.487 |
| y50_ratio (golden 지표) | 0.9588 | >0.825 | 0.896 | 0.097 | 0.798 | 0.781 @ >0.898 | 0.897 @ >0.823 |

**해석:**

- **현행 임계 50은 dark-ratio 계열에서 최악에 가깝다** — dark 임계를 낮출수록 단조
  개선(AUC 0.956→0.977), 8-bit 16(=raw16 4096)에서 최대. "정말 어두운 픽셀"의
  비율이 "약간 어두운 픽셀" 비율보다 두 클래스를 훨씬 잘 가른다. 재보정 문서
  (`design-limitations` §"dark_pixel_threshold 자체는 스윕 안 함")의 우려가 실측으로
  확인된 셈.
- logmean(0.9780)·entropy(0.9773)·dark16(0.9766)은 통계적으로 사실상 동률.
  p10/p25/p90은 열등(저백분위는 ExDark의 검은 배경과 COCO의 그림자를 구분 못 함).
- NP 관점: FT≤0.10 제약이면 dark16이 recall 0.941(현행 0.904 대비 +0.037), FT≤0.05
  제약이면 0.877(현행 0.797 대비 +0.080).

### 3.1 2-feature 조합 — 기각

| 규칙 | recall | FT | J |
|---|---|---|---|
| dark50>0.82 AND p90<156 | 0.899 | 0.090 | 0.809 |
| dark50>0.84 OR p90<68 | 0.889 | 0.078 | 0.810 |
| logistic(dark50, p90) | 0.903 | 0.092 | 0.810 (AUC 0.9632) |

세 방식 모두 J≈0.81 — dark50 단독과 동일하고 **dark16 단독(0.849)에 미달**. 두 번째
feature가 주는 정보가 dark 임계를 옮기는 것으로 이미 흡수된다. multi-feature의 HW
비용(카운터 2개+결합 로직 또는 곱셈기)을 정당화할 근거 없음 → 기각.

---

## 4. Subsampling (Bayer-quad 보존)

| stat | 1/1 | 1/4 | 1/8 | 1/16 (AUC / J) |
|---|---|---|---|---|
| dark16 | 0.9766 / 0.849 | 0.9766 / 0.849 | 0.9765 / 0.847 | 0.9766 / 0.847 |
| dark32 | 0.9712 / 0.830 | 0.9712 / 0.830 | 0.9711 / 0.828 | 0.9711 / 0.830 |
| dark50 | 0.9632 / 0.809 | 0.9631 / 0.809 | 0.9631 / 0.812 | 0.9631 / 0.810 |
| p50 | 0.9721 / 0.847 | 0.9722 / 0.847 | 0.9722 / 0.847 | 0.9722 / 0.845 |
| p90 | 0.9363 / 0.767 | 0.9363 / 0.769 | 0.9363 / 0.767 | 0.9366 / 0.769 |
| logmean | 0.9780 / 0.849 | 0.9780 / 0.849 | 0.9779 / 0.847 | 0.9779 / 0.847 |

**1/16까지 ΔAUC ≤ 0.0001, ΔJ ≤ 0.002 — 사실상 열화 없음.** 고정 운영점도 유지:
1/16 샘플에서 dark16>0.62는 recall 0.934 / FT 0.089 (전수 0.936/0.089와 동일 수준).

**샘플링 표준편차(1/16, 16개 quad-phase offset 전부 재계산, per-frame std):**

| stat | mean std | p95 std |
|---|---|---|
| dark16 (ratio) | 0.0025 | 0.0055 |
| dark32 | 0.0024 | 0.0054 |
| dark50 | 0.0022 | 0.0053 |
| p50 (8-bit bin) | 0.32 | 1.05 |
| p90 | 0.98 | 2.91 |
| logmean (bit) | 0.014 | 0.030 |

→ dark-ratio는 1/16 샘플에서도 ratio 기준 σ≈0.25%p(최악 0.55%p). checker pass가
읽는 픽셀을 16배 줄여도(예: 640×480 → 19,200px) 판정 품질 손실이 없다.

---

## 5. Margin / hysteresis 분석

### 5.1 경계 근접 밀도 (flapping 위험 노출량)

J\* 임계 t\* 기준 |stat−t\*|≤ε 프레임 비율:

| stat | ε=1% range | 2% | 5% |
|---|---|---|---|
| dark16 (t\*=0.615) | 1.0% | 2.1% | 5.9% |
| dark50 (t\*=0.822, 현행 통계량) | 1.9% | 3.9% | 9.5% |
| p50 (t\*=9.5) | 5.8% | 11.0% | 64.2% |
| logmean (t\*=3.218) | 1.0% | 2.3% | 7.2% |

dark16은 **경계 근접 밀도까지 현행 dark50의 절반** — 임계가 두 클래스 분포의 더 빈
골짜기에 놓인다. p50은 AUC는 좋지만 8-bit 정수 격자 위에 프레임이 몰려(±5%면 64%)
운영점이 취약 → 순위 하향 근거.

### 5.2 Flapping 시뮬레이션 및 hysteresis 폭 도출

per-frame jitter σ는 §4의 1/16 phase-std 실측으로 대입(median 0.0023 / p95 0.0055 /
보수적 3×p95 0.0164). 시나리오: **steady**(경계 ±0.05 내 실프레임 값 고정 + jitter,
100프레임, 이상적 전환 0회) / **ramp**(밝→어둠 선형 통과, 이상적 1회). 300 trial 평균,
dual threshold는 진입 t\*+δ / 해제 t\*−δ:

| stat | σ | δ=0 (single) | δ=1σ | δ=2σ | δ=3σ | δ=0.02 |
|---|---|---|---|---|---|---|
| dark16 | 0.0023 (med) | steady 2.15 / ramp 6.35 | 0.33 / 1.72 | 0.02 / 1.01 | 0.00 / 1.00 | 0.00 / 0.93 |
| dark16 | 0.0055 (p95) | 5.66 / 13.96 | 1.34 / 3.23 | 0.16 / 1.03 | 0.01 / 1.00 | 0.00 / 1.00 |
| dark16 | 0.0164 (3×p95) | 14.81 / 13.96 | 3.26 / 3.23 | 0.41 / 1.03 | 0.03 / 1.00 | 2.18 / 2.25 |
| dark50 | 0.0053 (p95) | 5.17 / 13.96 | 1.11 / 3.23 | 0.09 / 1.03 | 0.00 / 1.00 | 0.00 / 1.00 |

**권고 hysteresis 폭: δ = 0.02 (ratio 2%p), 즉 진입 >64% / 해제 <60% (중심 62%).**
근거: δ=0.02는 실측 p95 jitter의 3.6σ — steady flapping 0.00회/100프레임, ramp도
정확히 1회 전환. 경계 ±2%p 밀도가 2.1%(§5.1)라 상시 노출 프레임도 적음. 극단 가정
(3×p95)에서도 δ≥2σ=0.033이면 안전하나, 그 σ는 1/16 샘플링 노이즈의 3배로 실제 발생
근거가 없어 0.02로 충분하다고 판단. 부수 효과: 진입 64%는 FT를 0.082로 더 낮추고
(진입 결정), 해제 60%는 이미 LOW_LIGHT인 어두운 장면의 recall 유지(해제 결정)에 유리한
방향 — 비대칭이 분류 성능과 같은 방향으로 작용.

---

## 6. 5-fold cross-validation (J\* 임계를 4/5에서 적합, 1/5에서 평가)

| stat | recall (mean±std) | FT (mean±std) | 적합 임계 (mean±std) |
|---|---|---|---|
| **dark16** | 0.918 ± 0.008 | 0.080 ± 0.038 | 0.641 ± 0.021 |
| dark24 | 0.904 ± 0.027 | 0.082 ± 0.041 | 0.718 ± 0.014 |
| dark32 | 0.931 ± 0.005 | 0.110 ± 0.037 | 0.729 ± 0.007 |
| dark50 (현행 통계량) | 0.887 ± 0.020 | 0.090 ± 0.031 | 0.829 ± 0.006 |
| p50 | 0.954 ± 0.013 | 0.107 ± 0.027 | 9.5 ± 0.0 |
| p25 | 0.922 ± 0.026 | 0.144 ± 0.026 | 1.5 ± 0.0 |
| logmean | 0.935 ± 0.018 | 0.092 ± 0.034 | 3.207 ± 0.019 |
| mean8 | 0.890 ± 0.028 | 0.083 ± 0.022 | 27.4 ± 0.3 |
| entropy | 0.934 ± 0.014 | 0.096 ± 0.044 | 5.373 ± 0.175 |

- dark16의 held-out recall std ±0.008은 표 중 최소 — 운영점이 가장 안정적으로 일반화.
- 적합 임계 0.641±0.021은 전수 J\* 0.615와 정수 %로 61~66 사이 — 최종 임계는 hysteresis
  중심 62%(§5.2)로 채택(전수 기준 recall 0.936 / FT 0.089, J=0.847).
- 모든 후보의 held-out FT std가 ±0.03~0.04로 비슷하게 큰 것은 fold당 COCO 115장의
  표본 한계(±4장) — 통계량 간 차이가 아님.

---

## 7. 최종 권고 (순위)

| 순위 | 통계량 + 운영점 | 성능 (recall / FT / J) | HW 비용 (정성) |
|---|---|---|---|
| **1** | **dark16**: `dark_pixel_threshold`=**256**(=16<<4, HLS raw12 도메인 — 데이터셋 도메인 스윕값 4096의 등가, §1.0), 진입 dark_ratio>**64%** / 해제 <**60%** (hysteresis δ=2%p, 중심 62%) | 0.936 / 0.089 / 0.847 (@62%, 전수) — 현행 대비 recall +0.018, FT −0.036, J +0.038 | **변경 0**: 기존 비교기+카운터 그대로. 레지스터 값 4096 + `DARK_RATIO_PCT` 상수 80→62(hysteresis 시 64/60 두 상수 + mode FF 1개). pass 수 동일(1) |
| 2 | 위 + **1/16 Bayer-quad subsampling** (quad-grid stride 4×4) | 0.934 / 0.089 / 0.845 — 열화 무시 가능(σ_ratio≈0.25%p) | 카운터 1 + 주소 스킵 로직. checker pass 픽셀 읽기 **16배 감소** |
| 3 | logmean(log-average luminance) < 3.22 bit | 0.939 / 0.090 / 0.849 | 256-entry log2 LUT(Q8) + 40bit 누산기 + frame-end 나눗셈 1회. dark16 대비 이득 없음(ΔJ=0.000, ΔAUC +0.0014) → 비용 대비 기각 |
| 4 | 256-bin histogram + p50<9.5 (CDF walk) | 0.953 / 0.106 / 0.847 | BRAM 256×21bit + walk FSM. recall 최고지만 운영점이 정수 격자에 몰려 취약(§5.1), FT도 0.106 |
| 5 | entropy < 5.29 bit | 0.930 / 0.077 / 0.854 | histogram + frame-end 256× log-LUT/곱 — 최고 J이나 비용 최대, "저entropy=어두움" 의미론이 균일-밝음 장면에서 오동작 위험(OOD) → 기각 |
| — | 2-feature(dark+p90, AND/OR/logistic) | J≈0.81 | dark16 단독에 미달 → 기각 |

**실행 제안(1순위 반영 시 변경 지점):** `src/dfxisp_accel.cpp`·`tools/gen_golden_vectors.py`의
`DARK_RATIO_PCT` 80→62(hysteresis 채택 시 ENTER=64/EXIT=60), `tools/isp_pipeline_ver1.py`
`DARK_Y` 50→16·`DARK_RATIO` 0.80→0.62, C-sim/golden 테스트벤치의 `dark_pixel_threshold`
주입값 512→**256** (raw12 도메인, §1.0 — 데이터셋 도메인 스크립트/골든모델에서는
12800→4096), boundary regression fixture 2종(61%→NORMAL, 66%→LOW_LIGHT 등) 교체.
RAW 도메인 경계 회귀(`auto_raw12_thr256_*`: 임계 256에서 raw==256 → NORMAL /
raw==255 → LOW_LIGHT)는 2026-07-04에 선반영 완료.
hysteresis는 checker가 이전 mode를 입력으로 받아야 하므로 s_axilite `mode` 대신 내부
상태 FF 1개 추가가 필요 — AUTO 연속 프레임 운용 시나리오(보드)에서만 의미 있고,
단일 프레임 C-sim 의미론은 불변.

**한계:** (1) pseudo-RAW(sRGB 역변환) 기반 — real-RAW 센서에서 dark16 절대값
(HLS raw12 256 / 데이터셋 4096)은 black level/노출에 따라 재보정 필요(상대 결론인
"낮은 dark 임계가 우월"은 유지 전망).
(2) FT의 fold 간 분산(±0.04)이 크므로 소수점 둘째 자리 차이는 과신하지 말 것.
(3) hysteresis σ는 공간 샘플링 노이즈 proxy — 실제 시간축 jitter(센서 노이즈, AE 변동)는
보드 실측으로 확인 필요.

## 산출물

- 스크립트: `isppipeline/hls/tools/checker_stat_sweep.py` (`--compute`/`--analyze`,
  결정적, 전수 재계산 약 1.5분)
- per-frame 통계 CSV(1150×108): scratchpad
  `/tmp/claude-1000/-home-mini-workspace-dfxisp/d42e8f48-9372-4e82-b1c2-02162aa5e23d/scratchpad/checker_sim/frame_stats.csv`
  (휘발성 — 스크립트로 재생성 가능)
- 원 분석 로그: 같은 디렉토리 `analysis_out.md`
