<!--
=============================================================================
File   : isppipeline/hls/results/checker-principles-2026-07-05.md
Date   : 2026-07-05 21:24 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3
Track  : CHK (goal command Part 1) — scene-checker의 수학적/과학적 원리 정본
Function: 씬 체커(NORMAL vs LOW_LIGHT 판정)를 어떤 원리 위에 세워야 하는가를
          결정이론·광도계·노이즈물리·표본론·시간축의 5개 축으로 정의하고,
          각 원리를 (수식) + (근거: 선행문서/직접 실행한 스크립트 수치)로 고정.
Sources: checker-improvement-theory-2026-07-03.md (이론)
         checker-improvement-simulation-2026-07-03.md (1150프레임 스윕)
         checker-improvement-analysis-2026-07-04.md (dark16 우월 원인규명)
         tools/checker_stat_sweep.py, tools/checker_versions.py (직접 실행)
         results/scratch_frame_stats.csv (본 캠페인 재계산, 1150×108)
=============================================================================
-->
# 씬 체커 설계 원리 정본 (principled-v3, 2026-07-05)

**작성:** 2026-07-05 21:24 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` ·
**캠페인:** `principled-v3`

> 대상: `src/dfxisp_accel.cpp` `checker_select_mode()` (line 145–156). 현행 구현은
> AUTO 모드에서 RAW 픽셀을 1-pass로 읽어 `raw[i] < dark_pixel_threshold`인 dark
> pixel을 세고, 그 비율이 `DARK_RATIO_PCT=80%`를 넘으면 LOW_LIGHT RM을 선택한다.
> 본 문서는 이 체커가 **어떤 원리 위에 서야 하는가**를 5개 축으로 정의하고, 각
> 주장을 수식과 (선행문서 또는 본 캠페인에서 직접 실행한 스크립트 수치)로 못박는다.
> 구현·실험은 `checker-principled-versions-2026-07-05.md`, 코드는
> `tools/checker_versions.py`.

**표기.** 프레임 픽셀 수 N, dark threshold τ(=`dark_pixel_threshold`), dark-pixel
ratio `T = (1/N)·Σᵢ 1[xᵢ < τ]`, 판정 임계 t₀. 두 가설 H₀=NORMAL(정상조도),
H₁=LOW_LIGHT(저조도). downstream 소비자는 object detector(YOLOv8n)이며 사람
시청자가 아니다. mode 전환은 partial reconfiguration(PR, ~ms) 비용을 유발한다.

**본 캠페인 재현 수치의 출처.** 이하 표의 recall/FT/J/AUC/overlap/flapping 값은
본 브랜치에서 `python3 tools/checker_stat_sweep.py --compute --csv
results/scratch_frame_stats.csv` (1150프레임 전수, 결정적) → `python3
tools/checker_versions.py --csv results/scratch_frame_stats.csv`로 **직접 재생성**한
것이며, 선행 3개 문서(2026-07-03/04)의 값과 일치함을 확인했다.

---

## 원리 1 — 결정이론: 체커는 비대칭 비용 이진 가설검정이다

### 1.1 수학적 서술

프레임 관측 x에 대해 Bayes 최적 판정은 likelihood-ratio test(LRT)다
(Neyman & Pearson 1933; Duda, Hart & Stork 2001, Ch.2):

```
Λ(x) = p(x|H₁)/p(x|H₀)  ≷  η,     η = (C₁₀−C₀₀)·π₀ / ((C₀₁−C₁₁)·π₁)
```

Cᵢⱼ = "Hⱼ가 참인데 i로 판정"의 비용, πⱼ = prior. 세 판정기준의 위계:

- **Youden's J** = TPR − FPR 최대화 (Youden 1950). 이는 **균등 prior(π₀=π₁) + 대칭
  0-1 loss일 때의 Bayes 기준과 동치** — balanced error rate 최소화. 현행 80% 보정이
  암묵적으로 채택한 기준이다.
- **Neyman–Pearson**: P_FA ≤ α 고정 하 P_D 최대화. PR로 인한 frame-drop budget이
  스펙에 명시될 때 올바른 프레임.
- **Bayes risk 최소화**: 위 η. 비용·prior를 모두 반영하며, 시스템 목표(기대 mAP
  최대화)에 직접 대응하는 **유일한** 기준. 이것이 체커가 궁극적으로 최적화해야 할
  목적함수다.

**충분통계량 조건 (dark-ratio는 언제 최적인가).** 픽셀을 iid로 보고 히스토그램
count를 관측이라 하면 log-LR = `Σⱼ nⱼ·log(qⱼ/pⱼ)`. 이것이 단일 dark count 임계로
정확히 환원되는 필요충분조건은 `log(qⱼ/pⱼ)`가 x<τ 구간 상수·x≥τ 구간 상수인 경우
(2-level 장면 모델)뿐이다. 일반 단조 우도비 모델에서는 Karlin–Rubin 정리(단측 UMP;
Lehmann & Romano 2005 §3.4)로 scalar 임계가 UMP가 되나, **그 scalar가 무엇이어야
하는지**(원리 2)가 관건이다. 이진 양자화는 data-processing inequality(Cover &
Thomas 2006, Thm 2.8.1)로 KL divergence를 감소시키므로 dark-ratio 검정의 error
exponent는 히스토그램 LRT 이하다 — tail 정보가 필요한 장면 구별에는 구조적으로 열등.
(theory-2026-07-03 §1.1–1.3)

### 1.2 근거: 실측 비용 비대칭 (Youden J는 우리 목표와 어긋난다)

레포의 ablation 실측(`results/map_ablation2_{coco,exdark}_yolov8n.csv`, mAP@0.5:0.95;
theory §1.2 / analysis §4):

| 상황 | normal arm | low-light arm | Δ = 오판 비용 |
|---|---|---|---|
| COCO(정상 장면) | 0.2476 | 0.2089 | **C_FA = 0.0387** (정상을 저조도로 오판) |
| ExDark(저조도) | 0.1053 | 0.2171 | **C_miss = 0.1118** (저조도를 정상으로 놓침) |

`C_miss ≈ 2.89 × C_FA` — 비용이 뚜렷이 **비대칭**하다. Bayes LR 임계:

```
η = C_FA·π₀ / (C_miss·π₁) = 0.346  (균등 prior)   → Youden 점보다 recall 쪽 완화
                          = 3.11   (π₀:π₁=9:1, 주간 배포) → 오히려 보수적으로
```

따라서 체커 목적함수는 프레임당 **기대 mAP 손실**이어야 한다:

```
R = ½·(miss·C_miss + FT·C_FA),   miss = 1 − recall
```

**본 캠페인 재실행값** (`checker_versions.py`, C_miss=0.1118 / C_FA=0.0387):

| 규칙 | recall | FT | J | R (mAP손실/frame) |
|---|---|---|---|---|
| C0 dark50>0.80 (현행) | 0.918 | 0.125 | 0.793 | 0.00699 |
| C1 dark16>0.62 (J*) | 0.936 | 0.089 | 0.847 | 0.00531 (**−24%**) |
| C2 dark16>0.553 (Bayes-opt) | 0.965 | 0.134 | 0.831 | 0.00454 (**−35%**) |

**원리 확정:** 운영점은 J가 아니라 R로 선택한다. J*는 균등-prior·대칭-비용의 특수해로
문서화하고, 비대칭 비용(2.89:1)을 반영한 Bayes-opt(C2, 55.3%)는 R을 추가 −11%p
낮추되 FT를 +4.5%p 올리는 트레이드를 명시한다. PR 전환비용 c_PR은 per-frame 임계가
아니라 원리 5(시간축)가 담당한다(분리원칙). (theory §1.2, analysis §4)

---

## 원리 2 — 광도계: pseudo-RAW는 linear-light이므로 dark 임계는 감마 공간에서 정의한다

### 2.1 수학적 서술

곱셈적 상 형성 `I = R·E`(reflectance × illumination; Gonzalez & Woods 2018 §2.3)에서
log를 취하면 `log I = log R + log E` — 조도(exposure) 변화가 log-히스토그램의
**평행이동**이 되어, 조도를 분류하려는 체커의 통계량은 log 공간에서 조도에
equivariant해야 한다. 사진 측광의 표준 밝기 척도는 log-average luminance
(Reinhard et al. 2002):

```
L̄_w = exp( (1/N)·Σ log(δ + L_w) ),   scaled L = (a/L̄_w)·L_w,  a=0.18(18% mid-gray)
```

ISO 12232의 노출 정의도 18% gray를 표준 출력레벨로 사상하며 모든 노출 산술이 log₂(EV,
stop)로 이뤄진다. dark-ratio `1−F̂(τ)`가 조도에 선형 반응하려면 τ가 **감마 공간의 진짜
암부**에 놓여야 한다.

### 2.2 근거: DARK_Y=50은 중간톤 경계였다 (photometry 실측)

raw_bin의 광도 의미를 원본 JPEG 재모자이크와 대조해 실측(analysis §1):

| 가설 | COCO MAE | ExDark MAE |
|---|---|---|
| raw>>8 = sRGB 값 그대로 | 45.5 | 33.1 |
| **raw>>8 = 역감마 2.2 선형화 값** | **6.0** | **4.3** |

→ pseudo-RAW는 **linear-light**다. linear 8-bit 임계의 지각적 의미:

| linear(RAW) | sRGB 등가 `255·(v/255)^(1/2.2)` | 의미 |
|---|---|---|
| 16 (dark16) | **≈72** | 어두운 픽셀(하위 톤) |
| 50 (현행 DARK_Y) | **≈122** | **중간톤** — 8-bit 스케일의 거의 절반 |

**즉 현행 dark50은 "어두운 픽셀"이 아니라 "중간톤 이하 픽셀"을 세고 있었다.** 정상
장면도 톤 질량 상당분이 sRGB 122 아래(그림자·중간톤)에 있어 dark50이 크게 오른다.

### 2.3 근거: [16,50) 대역은 반(反)신호다 (band decomposition)

8-bit linear 대역별 픽셀 질량(클래스 평균)과 그 대역 단독 AUC(analysis §2):

| 대역 | ExDark 질량 | COCO 질량 | 단독 AUC |
|---|---|---|---|
| **[0,16)** | **0.860** | 0.360 | **0.977** |
| [16,50) 합계 | 0.072 | **0.221** | **0.089** (<0.5, 역방향) |

판별 정보는 **[0,16)에 전부** 있다(AUC 0.977). [16,50) 대역은 COCO가 ExDark의 3배로,
질량이 클수록 오히려 정상조도 — dark50 = 신호(dark16) + 반신호([16,50))이므로
분리도가 낮다. 대역을 잘라내는 것만으로 AUC 0.963→0.977이 설명된다.

**원리 확정:** dark 임계는 감마 공간의 진짜 암부(dark16 ≈ sRGB 72)에서 계수한다.
**본 캠페인 재실행 overlap coefficient**(Bayes-오류 하한 proxy) C0(dark50)=0.193 vs
C1(dark16)=0.139 — 분포 겹침 자체가 축소된다(`checker_versions.py`). dark16이
dark50을 지배하는 물리적 실체는 "감마 공간에서 진짜 어두운 픽셀만 세라"이고, 이는
log-도메인 metering(원리 3)의 1-비교기 근사다.

---

## 원리 3 — 노이즈 물리: dark 임계는 read-noise 플로어에서 유도하고, metering은 log 도메인이다

### 3.1 수학적 서술 (EMVA 1288 / photon transfer)

EMVA 1288(Release 3.0)의 선형 카메라 모델:

```
µ_y = µ_y.dark + K·η·µ_p,   σ_y² = K²·σ_d² + σ_q² + K·(µ_y − µ_y.dark)  (마지막=shot)
SNR(µ_p) = η·µ_p / sqrt(σ_d² + σ_q²/K² + η·µ_p)
```

Shot-noise-limited 영역에서 SNR ≈ √(η·µ_p) (Poisson; Janesick 2007). **저조도의
물리적 본질은 "밝기가 낮다"가 아니라 "전자 수가 적어 SNR이 무너진다"이다.** SNR 목표
s에서 필요한 전자 수 `e*(s) = (s² + s√(s²+4σ_d²))/2`, DN 임계 `τ(s,g) = µ_dark.DN +
g·K₀·e*(s)` — **τ는 gain g에 선형**(같은 DN이라도 gain이 높으면 전자 수가 적어 SNR
낮음). Rose criterion(Rose 1948) s≈5가 신뢰 검출 하한.

τ를 SNR로 잡으면 dark-ratio는 "usable-SNR 미만 픽셀의 비율" — 원리적 low-light
정의가 되고, 이는 low-light RM의 이득 메커니즘과 직결된다: 2×2 binning은
shot-limited에서 SNR ×2, read-limited에서 ×4. 즉 "binning이 이득을 주는 조건 = 픽셀
SNR < 목표"이며 체커가 정확히 그것을 센다. (theory §3)

### 3.2 근거: log-도메인 metering이 선형 평균을 이긴다

**본 캠페인 재실행 per-statistic ROC** (`checker_stat_sweep.py`, 1150프레임):

| 통계량 | AUC | J* | 방향 |
|---|---|---|---|
| logmean (log-avg luminance) | **0.9780** | 0.849 | 낮을수록 어두움 |
| entropy | 0.9773 | 0.854 | 〃 |
| dark16 | 0.9766 | 0.849 | 높을수록 어두움 |
| mean8 (선형 평균) | 0.9628 | 0.812 | 낮을수록 어두움 |
| dark50 (현행) | 0.9632 | 0.809 | 높을수록 어두움 |

log-도메인(logmean AUC 0.978)이 선형 평균(mean8 0.963)을 이기고, dark16(0.977)은
그 log 정보를 비교기 1개로 근사한다 — 셋은 통계적으로 사실상 동률. **원리 확정:**
metering은 shadow 해상도를 강조하는 log 도메인에서 하며, dark 임계는 노이즈
플로어(감마 공간 진짜 암부)에 놓는다. pseudo-RAW엔 광자 통계가 없으므로 현행은 경험적
보정이 차선이고, 실센서 이행 시 τ(s,g)를 AXI-lite로 프레임마다 갱신(HW 변경 0).
(theory §3.2–3.3, simulation §3)

---

## 원리 4 — 표본론: 전 픽셀 판독은 불필요하다 (1/16 subsample 무손실)

### 4.1 수학적 서술 (Hoeffding / 이항 표본오차)

n 픽셀 표본의 dark-ratio 추정 p̂: `Var(p̂) = p(1−p)/n`. Hoeffding 부등식(1963):

```
P(|p̂−p|>ε) ≤ 2·exp(−2nε²)  →  ε=0.02, 신뢰 1−10⁻⁶에 n ≥ ln(2·10⁶)/(2·0.02²) ≈ 18,100
```

= 약 1/51 샘플링. 경계 근방 p는 Wilson 구간 권장(Brown, Cai & DasGupta 2001). 픽셀은
공간 상관을 가지나 양의 자기상관 필드에서 systematic(격자) 샘플링 분산은 단순임의추출
이하(Cochran 1977 Ch.8). Bayer 주의: 짝수 stride는 단일 채널만 표본하므로 2×2 quad를
통째로 유지한다. (theory §5)

### 4.2 근거: 1/16 서브샘플의 ΔAUC ≤ 0.0001

**시뮬레이션 재현값**(simulation §4, Bayer-quad 보존 1/4·1/8·1/16 스윕):

| stat | 1/1 AUC | 1/16 AUC | 1/16 phase-std(σ) |
|---|---|---|---|
| dark16 | 0.9766 | 0.9766 | 0.0025 (p95 0.0055) |
| dark50 | 0.9632 | 0.9631 | 0.0022 (p95 0.0053) |
| logmean | 0.9780 | 0.9779 | 0.014 |

1/16까지 ΔAUC ≤ 0.0001, ΔJ ≤ 0.002 — CI ±0.0065는 hysteresis 밴드(0.6)는 물론 임계
민감도(80% vs 83%)보다 한 자릿수 작다. **원리 확정:** 판정 품질 손실 없이 checker pass의
메모리 트래픽을 16배 줄인다(로직 절감은 미미하나 대역폭/지연이 실이득). 더 나은 대안은
체커를 본 스트리밍 패스에 접어넣고 통계를 다음 프레임 판정에 쓰는 것(1-frame lag, 추가
패스 0) — 원리 5의 시간축 필터가 어차피 수 프레임 지연을 도입하므로 무해.

---

## 원리 5 — 시간축: hysteresis는 전환비용 하 최적정책(Schmitt/Dixit)이며 δ=2%p로 flapping을 없앤다

### 5.1 수학적 서술 (Schmitt trigger / Dixit optimal-inaction)

PR 비용 c_PR이 있으므로 per-frame 독립 판정은 경계 근방에서 진동(flapping)한다.
통계량이 `T_t = p + ε_t, ε_t ~ N(0,σ_T²)`일 때 단일 임계 t₀에서 p≈t₀이면 프레임당
전환 확률 ≈ 1/2(최악의 flapping). 이력 밴드 `[t_lo, t_hi]` (폭 h)에서는 전환 직후
되돌아가려면 ε가 밴드를 관통해야 하므로 프레임당 오전환 확률 ≈ Q(h/σ_T). 설계 규칙:

```
h ≥ σ_T · Q⁻¹(α)     예: σ_T=0.0055(실측 p95), α=10⁻⁴ → h ≥ 0.0055·3.72 ≈ 0.020
```

전환비용이 0이 아닌 한 밴드 폭 0(단일 임계)은 결코 최적이 아니며, 최적 정책이 이력
밴드임은 전환비용 하 최적정지의 고전 결과다(Dixit 1989 — Brownian 극한에서 밴드 폭 ∝
비용^(1/3); 2-상태 POMDP의 posterior-공간 hysteresis, Rabiner 1989). 이 시스템은 이미
**per-frame Bayes 임계(원리 1)는 비용·prior를, 시간축 계층(Schmitt+dwell)은 전환비용을**
분담하는 계층 분리를 갖고 있어 이론적으로 옳다. 남은 일은 HW checker에 exit-side 임계와
min-dwell(≥⌈t_PR/t_frame⌉)을 넣는 것뿐이다. (theory §4)

### 5.2 근거: δ=2%p가 flapping을 0으로 만든다

**본 캠페인 flapping 시뮬레이션**(`checker_versions.py`, 실측 σ 기반, steady 이상값=0회):

| ver | jitter σ | δ 밴드 | 단일임계 flaps/100fr | hysteresis flaps |
|---|---|---|---|---|
| C0 dark50 | 0.0020 | 0.020 | 3.27 | **0.00** |
| C1 dark16 | 0.0023 | 0.020 | 1.50 | **0.00** |
| C2 dark16 | 0.0023 | 0.020 | 3.71 | **0.00** |
| C3 logmean | 0.0120 | 0.043 | 16.69 | **0.00** |

**권고 밴드: δ=0.02(ratio 2%p), 즉 진입 >64% / 해제 <60%(중심 62%).** 근거: δ=0.02는
실측 p95 jitter의 3.6σ — steady flapping 0회, ramp도 정확히 1회 전환(simulation §5.2).
부수 효과로 진입 64%는 FT를 낮추고 해제 60%는 이미 어두운 장면의 recall을 유지 — 비대칭이
분류 성능과 같은 방향으로 작용. hysteresis는 이전 mode를 입력으로 받아야 하므로 내부 상태
FF 1개 추가로 족하다(단일-프레임 C-sim 의미론 불변).

---

## 종합 — 원리→버전 사상

| 원리 | 핵심 명제 | 근거(문서/스크립트) | 버전 반영 |
|---|---|---|---|
| 1 결정이론 | 목적함수는 J가 아니라 비대칭 비용 Bayes risk R (2.89:1) | theory §1.2, ablation csv, `checker_versions.py` | C0→C2 운영점 |
| 2 광도계 | linear-light이므로 dark 임계는 감마 공간 진짜 암부(dark16), [16,50)은 반신호 | analysis §1–2 (MAE 6.0 vs 45.5; 대역 AUC 0.089) | C1/C2 |
| 3 노이즈물리 | low-light=SNR붕괴; τ↔read-noise 플로어; metering은 log 도메인 | theory §3, `checker_stat_sweep` ROC(logmean 0.978) | C3, C4 |
| 4 표본론 | 1/16 systematic subsample 무손실(Hoeffding) | simulation §4 (ΔAUC≤0.0001) | 전 버전 HW 옵션 |
| 5 시간축 | 전환비용 하 최적=Schmitt 밴드; δ=2%p로 flapping 0 | theory §4, `checker_versions.py` flap-sim | 전 버전 hysteresis |

**한 줄 요지:** 통계량 교체(dark50→dark16/logmean)보다 우선인 것은 (i) **임계의 유도
방식**(감마 공간 진짜 암부 = 노이즈 플로어)과 (ii) **판정 기준의 교정**(J → 실측 ΔmAP
가중 Bayes risk)이며, (iii) 전환비용은 per-frame 임계가 아니라 시간축(Schmitt+dwell)이
담당한다. 전수 판독은 통계적으로 불필요하다(1/16).

## 한계 (정직한 명시)

1. **pseudo-RAW 노이즈 통계 부재.** raw_bin은 sRGB JPEG 역감마 산물이라 광자 통계가
   없다 — 원리 3의 SNR 유도 τ는 실센서에서만 활성화 가능하고, 현 단계에선 경험적
   보정(dark16 절대값)이 차선. "낮은 dark 임계가 우월"이라는 **상대** 결론은 유지 전망이나
   절대값은 black level/노출로 재보정 필요.
2. **비용치 표본 한계.** C_miss/C_FA는 n=31/39 ablation 부분집합 기반 — 소수점 둘째 자리
   과신 금지. R 순위(C2<C1<C0)는 강건하나 55% vs 62% 선택은 보드 c_PR 실측 후 재검토.
3. **hysteresis σ는 공간 샘플링 노이즈 proxy.** 실제 시간축 jitter(센서 노이즈, AE 변동)는
   보드 실측 필요.
4. **CPU-only 환경.** 본 캠페인 mAP는 torch 2.12 CPU, yolov8n, n=150 부분집합 — 절대
   mAP보다 C0 대비 델타 해석에 무게.

## References (핵심)

Neyman & Pearson 1933; Youden 1950; Lehmann & Romano 2005; Duda, Hart & Stork 2001;
Cover & Thomas 2006; Reinhard et al. 2002; ISO 12232:2019; Gonzalez & Woods 2018;
EMVA 1288 R3.0 (2010); Janesick 2007; Rose 1948; Hoeffding 1963; Brown/Cai/DasGupta
2001; Cochran 1977; Schmitt 1938; Dixit 1989; Page 1954; Rabiner 1989.
(전체 서지: `checker-improvement-theory-2026-07-03.md` References 1–25.)
