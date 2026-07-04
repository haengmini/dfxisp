# Checker 개선 이론 연구 — 수리적/과학적 근거 기반 제안 (2026-07-03)

대상: `isppipeline/hls/src/dfxisp_accel.cpp` `checker_select_mode()` (line 145–156).
현재 구현: AUTO 모드에서 RAW 16-bit(실데이터 12-bit, 0..4095) 픽셀을 단일 스트리밍 패스로 읽어
`raw[i] < dark_pixel_threshold`인 dark pixel을 세고, dark-pixel ratio가 `DARK_RATIO_PCT=80%`를
초과하면 LOW_LIGHT RM을 선택한다. 80%는 2026-07-02 Youden's J sweep으로 재보정
(ExDark recall=0.90, COCO false-trigger=0.11, J=0.79; `results/experiment_ver2_2026-07-02.md`).

본 보고서는 이 checker를 6개 관점(decision theory / photometry / sensor physics /
temporal hysteresis / sampling / adaptivity)에서 수리적으로 분석하고, 각 제안의
공식·HLS 하드웨어 비용·출처를 제시한 뒤 impact-vs-cost 순위를 매긴다.

표기: 프레임 픽셀 수 N, dark threshold τ (=`dark_pixel_threshold`), dark-pixel ratio
T = (1/N)·Σᵢ 1[xᵢ < τ], 판정 임계 t₀ = 0.80. downstream 소비자는 object detector
(YOLOv8n/SSD, 사람 시청자 아님), mode 전환은 partial reconfiguration(PR, ~ms) 비용을 유발.

---

## 1. Decision theory — 단일 통계량·단일 임계는 언제 최적인가

### 1.1 이진 가설검정으로서의 NORMAL/LOW_LIGHT 판정

프레임 x에 대해 H₀: NORMAL scene, H₁: LOW_LIGHT scene. Bayes 최적 판정은
likelihood-ratio test(LRT)다 (Neyman & Pearson 1933; Duda, Hart & Stork 2001, Ch.2):

```text
Λ(x) = p(x|H₁)/p(x|H₀)  ≷  η,   η = (C₁₀−C₀₀)·π₀ / ((C₀₁−C₁₁)·π₁)
```

여기서 Cᵢⱼ = "H_j가 참인데 i로 판정"의 비용, πⱼ = prior. 세 가지 기준의 관계:

- **Bayes risk 최소화**: 위 η. 비용·prior를 모두 반영. 시스템 목표(기대 mAP 최대화)와
  직접 대응하는 유일한 기준.
- **Neyman–Pearson**: P_FA ≤ α 고정 하에 P_D(recall) 최대화 — LRT와 같은 형태이나 η를
  α로부터 결정 (Neyman & Pearson 1933). "불필요한 PR 이벤트 빈도에 하드 예산이 있을 때"
  올바른 프레임. 예: PR로 인한 frame drop budget이 스펙에 명시되는 경우.
- **Youden's J** = TPR − FPR 최대화 (Youden 1950, Cancer 3:32–35). 이는 **균등 prior(π₀=π₁)
  + 대칭 0-1 loss일 때의 Bayes 기준과 동치**다: J 최대화 ⇔ balanced error rate 최소화.
  즉 현재 보정은 "false-trigger와 miss의 비용이 같고, 배포 환경에서 dark/normal 장면이
  반반"이라는 암묵적 가정을 내포한다.

### 1.2 실측 mAP로 본 비용 비대칭 — Youden J는 우리 목표와 어긋난다

이 시스템의 진짜 효용은 downstream detection mAP다. 기대 효용:

```text
E[mAP] = π₀·[(1−FPR)·U(N|N) + FPR·U(LL|N)] + π₁·[(1−TPR)·U(N|LL) + TPR·U(LL|LL)]
```

레포의 실측치 (`results/map_ablation2_{coco,exdark}_yolov8n.csv`, mAP@50-95):

| 상황 | normal arm | low-light arm(최적: ll_bin_only) | Δ (오판 비용) |
|---|---|---|---|
| COCO(normal scene) | 0.2476 | 0.2089 | **C_FA = 0.0387** |
| ExDark(dark scene) | 0.1053 | 0.2171 | **C_miss = 0.1118** |

C_miss ≈ 2.9 × C_FA — 비용이 뚜렷이 **비대칭**이다. Bayes LR 임계:

```text
η = C_FA·π₀ / (C_miss·π₁)
  = 0.346   (π₀=π₁ 균등 prior)     → Youden 점보다 recall 쪽으로 완화해야 함
  = 3.11    (π₀:π₁ = 9:1, 주간 위주 배포) → 반대로 더 보수적이어야 함
```

즉 **현재 80%(≈Youden 최적점 83%)가 옳은지는 배포 prior에 달려 있고, Youden J 자체는
이를 표현할 수 없다**. 제안: threshold sweep 스크립트의 목적함수를 J에서
`E[mAP] − r_switch·c_PR` (실측 ΔmAP 가중)로 교체. HW 비용 0 — 바뀌는 것은
`DARK_RATIO_PCT` 상수뿐. PR 비용 c_PR은 per-frame 판정이 아니라 §4의 temporal 계층에서
처리하는 것이 분리원칙상 옳다(아래 4.5).

### 1.3 dark-pixel ratio는 언제 sufficient statistic인가

픽셀을 iid로 보고 B-bin histogram count n = (n₁,…,n_B)를 관측이라 하면 (multinomial),
log-LR은

```text
log Λ = Σⱼ nⱼ · log( qⱼ / pⱼ ),   pⱼ = P(bin j|H₀), qⱼ = P(bin j|H₁)
```

이것이 dark count n_dark = Σ_{j<τ} nⱼ 하나에 대한 임계 판정으로 **정확히 환원되는 필요충분
조건은 log(qⱼ/pⱼ)가 두 값만 갖는 것** — 즉 x<τ 구간에서 상수, x≥τ 구간에서 상수인 경우다.
이는 "장면 모델이 사실상 2-level 양자화"라는 뜻으로, 실제 자연 장면(연속 luminance 분포,
lognormal-계열)에서는 성립하지 않는다. 일반 단조 모델에서는 Karlin–Rubin 정리
(monotone likelihood ratio ⇒ 단측 UMP test; Lehmann & Romano 2005, §3.4)에 따라 scalar
통계량 임계 판정이 UMP가 되지만, 그 scalar가 무엇이어야 하는지가 관건이다.

정보이론적으로: dark-ratio는 empirical CDF의 **한 점** F̂(τ)이고, histogram은 CDF 전체다.
양자화는 KL divergence를 감소시키므로 (data-processing inequality; Cover & Thomas 2006,
Thm 2.8.1) 이진 양자화 기반 검정의 error exponent(Chernoff–Stein)는 histogram 기반 LRT보다
항상 같거나 나쁘다. 구체적 실패 모드: **F(τ)는 같지만 tail 분포가 다른 두 장면**
(예: "절반이 완전 흑 + 절반이 매우 밝음" vs "전체가 τ 바로 위 회색")은 dark-ratio로
구별 불가능하다 — 전자는 low-light 처리 이득이 없고 후자는 클 수 있다.

**결론**: dark-ratio 단일 임계는 (i) 2-level 장면 모델 하에서만 정확한 LRT이고,
(ii) 비용/prior 반영은 임계값 재배치로 가능하나, (iii) tail 정보가 필요한 장면 구별에는
구조적으로 열등하다. 보강 통계량은 §2(log-mean), §6(coarse histogram)에서 도출한다.

---

## 2. Photometry / exposure theory — 왜 log-domain 통계가 표준인가

### 2.1 log-average luminance (geometric mean)

Tone mapping과 카메라 AE의 표준 scene-brightness 척도는 log-average luminance다
(Reinhard, Stark, Shirley & Ferwerda 2002, ACM TOG/SIGGRAPH;
https://www.cs.utah.edu/docs/techreports/2002/pdf/UUCS-02-001.pdf):

```text
L̄_w = exp( (1/N) · Σ log(δ + L_w(x,y)) ),   δ ≈ 10⁻⁴ (log(0) 방지)
scaled: L(x,y) = (a / L̄_w) · L_w(x,y),      a = 0.18 (key value, 18% mid-gray)
```

log-domain이 표준인 이유는 세 가지다.

1. **곱셈적 상 형성 모델**: I = R·E (reflectance × illumination; Gonzalez & Woods 2018,
   §2.3, §3.3 homomorphic filtering). log를 취하면 log I = log R + log E로 분리되고,
   조도(exposure) 변화는 log-histogram의 **평행이동**이 된다. 따라서 log-mean은 조도에
   equivariant: logmean(k·I) = log k + logmean(I). 우리가 분류하려는 변수(장면 조도)에
   대해 선형으로 반응하는 통계량이다. 반면 dark-ratio 1−F̂(τ)의 조도 반응은 τ 근방의
   국소 CDF 기울기에 좌우되어 장면 내용에 얽힌다(§1.3).
2. **사진 측광 관행**: ISO 12232:2019(사진 노출지수/SOS)는 18% 반사율 gray를 표준 출력
   레벨로 사상하는 것을 노출의 정의로 삼고, EV = log₂(L·S/K) 등 모든 노출 산술이 log₂
   단위(EV, stop)로 이루어진다. AE 알고리즘 서베이(Bernacki 2020, Multimedia Tools and
   Applications 79; https://link.springer.com/article/10.1007/s11042-019-08318-1)에서도
   metering의 기본형은 (가중) 평균 luminance를 mid-gray 목표에 맞추는 것이며, 변형들
   (matrix/center-weighted/spot, luminance-histogram 기반 AE)은 모두 **CDF의 여러 점 또는
   히스토그램 전체**를 쓴다 — 한 점만 쓰는 방식은 표준 관행에 없다.
3. **Weber–Fechner**: 밝기 지각과 (detector가 학습한 sRGB 입력의) gamma 인코딩 모두
   근사 log이므로, log-domain 통계가 downstream 성능과의 상관이 자연스럽다.

### 2.2 percentile metering과 CDF 다점 샘플링

Highlight 보호형 AE는 상위 percentile(예: 99%)을, shadow 판단은 하위 percentile을 쓴다
(Bernacki 2020). dark-ratio는 "F̂(τ) > 0.8"이므로 **"20th percentile < τ"와 동치** —
즉 현재 checker는 사실상 20th-percentile 검정이다. 이렇게 보면 자연스러운 강화는
percentile 수를 늘리는 것: 예컨대 {F̂(τ/4), F̂(τ), F̂(4τ)} 세 점이면 "τ 근방 회색 장면"과
"진짜 암흑 + highlight" 장면을 분리할 수 있다(§1.3의 실패 모드 해소).

### 2.3 HW-cheap log₂-mean: leading-one detector

부동소수점 log 없이 스트리밍 log₂-mean을 구현할 수 있다:

```text
lg(x) ≈ msb(x) + frac,  msb = position of leading 1 (priority encoder, 16→4 bit)
                        frac = 다음 3 bit (mantissa 근사; 오차 < 0.086 bit)
S = Σᵢ lg(xᵢ+1)  →  logmean = S / N  (N이 2의 거듭제곱이면 shift)
```

비용: 16-bit priority encoder + 7-bit 값의 32-bit accumulator 1개 — **비교기 1개인 현재
checker에 가산기 하나 추가하는 수준**, II=1 스트리밍 유지, BRAM 불필요. 판정은
`logmean < θ_L` 단일 비교. 이는 Reinhard L̄_w의 정수 근사이며 조도 equivariance(§2.1)를
그대로 갖는다. dark-ratio와 함께 쓰면 2차원 통계 (T, logmean)이 되고, 두 임계의 AND/OR
결합(비교기 2개)만으로도 §1.3의 tail 실패 모드를 크게 줄인다.

---

## 3. Sensor noise physics — 원리적 low-light 정의는 밝기가 아니라 SNR

### 3.1 EMVA 1288 카메라 모델

EMVA 1288 표준 (Release 3.0, 2010; https://www.emva.org/wp-content/uploads/EMVA1288-3.0.pdf;
개요 https://www.baslerweb.com/en/learning/emva-1288-standard/)의 선형 카메라 모델:

```text
µ_y = µ_y.dark + K·η·µ_p            (µ_p: 픽셀당 광자수, η: QE, K: gain [DN/e⁻])
σ_y² = K²·σ_d² + σ_q² + K·(µ_y − µ_y.dark)     ← 마지막 항이 shot noise (Poisson)
SNR(µ_p) = η·µ_p / sqrt( σ_d² + σ_q²/K² + η·µ_p )
```

Shot-noise-limited 영역에서 SNR ≈ sqrt(η·µ_p) — **신호의 제곱근** (Poisson 통계;
Janesick 2007, *Photon Transfer*, SPIE Press; EMVA 1288 §3). 저조도의 물리적 본질은
"픽셀이 어둡다"가 아니라 "전자 수가 적어 SNR이 무너진다"이다.

### 3.2 SNR 목표 → dark_pixel_threshold 역산

전자 수 e = η·µ_p, read noise σ_d [e⁻]에서 SNR = e/√(e+σ_d²) = s를 풀면:

```text
e*(s) = ( s² + s·sqrt(s² + 4σ_d²) ) / 2
```

예 (σ_d = 3 e⁻, 일반적 CMOS):

| SNR 목표 s | 근거 | e* [e⁻] |
|---|---|---|
| 3 | 검출 하한 근방 | 14.6 |
| 5 | Rose criterion — 신뢰성 있는 검출 최소 SNR (Rose 1948, JOSA 38:196–208) | 32.0 |
| 10 | ISO 12232 "acceptable image quality" noise-based speed 기준 | 108.3 |
| 40 | ISO 12232 "excellent" 기준 | 1,646 |

DN 도메인 임계 (black level 보정 후, K [DN/e⁻], analog gain g):

```text
τ(s, g) = µ_dark.DN + g·K₀·e*(s)
```

예: 12-bit, K₀=0.4 DN/e⁻(full well ~10k e⁻), s=10 → τ ≈ BLC + 43 DN (unity gain),
gain 8×에서는 τ ≈ BLC + 346 DN. **τ는 gain에 선형으로 스케일해야 한다** — 같은 DN이라도
gain이 높으면 전자 수가 적어 SNR이 낮기 때문이다.

### 3.3 시스템에의 함의

1. **dark-ratio 통계 자체가 정당화된다**: τ를 SNR 역산으로 잡으면 dark-ratio는
   "usable SNR 미만인 픽셀의 비율" — 원리적 low-light 정의가 된다. 게다가 이는 low-light
   RM의 실제 이득 메커니즘과 직결된다: 2×2 binning은 shot-limited에서 SNR ×2,
   read-limited에서 ×4 (전자 합산으로 e→4e; √4=2 또는 read noise 상대 감소) — 즉
   "binning이 이득을 주는 조건 = 픽셀 SNR < 목표"이며 checker가 정확히 그것을 세게 된다.
2. **현 pseudo-RAW의 한계 명시**: 8-bit sRGB JPEG에서 만든 pseudo-RAW에는 광자 통계가
   없으므로 현재의 경험적 보정(Youden sweep)이 차선책으로 타당하다. 실센서 이행 시에는
   위 공식으로 τ를 설정하고, **이미 존재하는 AXI-lite runtime port가 정확히 올바른
   메커니즘**이다: host가 AE의 (exposure, gain) 메타데이터로 τ(s,g)를 프레임마다 갱신.
   HW 변경 0.
3. SW eval의 `Y<50`(8-bit)과 HW의 RAW-domain τ 사이 proxy 불일치(SPEC §3.1)도 SNR 정의로
   통일 가능: 양쪽 모두 "SNR<s 픽셀 비율"의 근사로 문서화.

---

## 4. Temporal stability / hysteresis — flapping의 수리

PR 비용 c_PR(~ms 재구성 + 해당 구간 frame 무효)이 있으므로 per-frame 독립 판정은
경계 근방에서 진동(flapping)한다. RESEARCH §5.2에 스케줄러 계층 hysteresis(0.80/0.20 밴드
+ temporal_N=3)가 이미 있으나 **HW checker(`checker_select_mode`)는 enter-side 단일
임계만 구현**한다. 원리적 정리:

### 4.1 Schmitt trigger (dual threshold) — 밴드 폭의 결정

Schmitt 1938 (J. Sci. Instruments 15:24–26)의 이력 비교기. 통계량이 T_t = p + ε_t,
ε_t ~ N(0, σ_T²) (프레임 간 잡음)일 때:

- 단일 임계 t₀에서 p ≈ t₀이면 프레임당 전환 확률 ≈ 1/2 → 최악의 flapping.
- 밴드 [t_lo, t_hi] (폭 h = t_hi − t_lo)에서는, 전환 직후 되돌아가려면 ε가 밴드를
  관통해야 하므로 프레임당 spurious re-switch 확률 ≈ Q(h/σ_T) (Q: 표준정규 tail).

**설계 규칙**: 허용 오전환율 α (per frame)에 대해

```text
h ≥ σ_T · Q⁻¹(α)        예: σ_T=0.05, α=10⁻⁴ → h ≥ 0.05·3.72 ≈ 0.19
```

σ_T는 로그(`frame_id, dark_ratio` 메타데이터, RESEARCH §5.2)에서 실측하면 된다.
경제학의 고전 결과(Dixit 1989, J. Political Economy 97(3):620–638 — 전환비용 하의 최적
정책은 hysteresis 밴드이며, Brownian 극한에서 **밴드 폭 ∝ (전환비용)^(1/3)**)가
"왜 밴드가 최적 구조인가"를 보증한다: 전환비용이 0이 아닌 한 밴드 폭 0(단일 임계)은
결코 최적이 아니고, 비용이 커질수록 밴드는 완만하게(세제곱근으로) 넓어져야 한다.
현행 0.80/0.20 (h=0.6)은 σ_T가 0.16 이하인 한 α<10⁻⁴를 만족 — 충분히 보수적.

### 4.2 K-of-N voting / min-dwell

연속 N 프레임 동의 요구 시 iid 가정 하에 오전환 확률은 αᴺ으로 지수 감소; 지연은 N 프레임.
실측(scheduler_sim, temporal_N=3: mismatch 0.015, thrashing 0)과 정합.
**min-dwell 하한은 물리적으로 결정된다**: dwell ≥ ⌈t_PR / t_frame⌉ — PR보다 빨리 장면이
바뀌면 전환 자체가 무의미하므로.

### 4.3 EWMA 필터

S_t = λ·T_t + (1−λ)·S_{t−1}. 정상상태 분산 σ_S² = σ_T²·λ/(2−λ), 군지연 ≈ (1−λ)/λ 프레임.
λ=1/4 (shift 2회, 곱셈 불필요): 분산 ×0.143 (σ ×0.38), 지연 3프레임. HW: 레지스터 1개 +
가산기/시프터 — 사실상 무료이며, 밴드 폭 h를 같은 α에서 1/2.6로 줄이거나 같은 h에서
α를 급감시킨다.

### 4.4 CUSUM change detection

Page 1954 (Biometrika 41:100–115; https://en.wikipedia.org/wiki/CUSUM):

```text
g_t = max(0, g_{t−1} + LLR_t),   alarm if g_t > h_c
LLR_t = log p(T_t|H₁) − log p(T_t|H₀)   (dark-ratio 구간별 정수 LUT로 근사 가능)
```

성능은 ARL(average run length) trade-off로 설계: 무변화 시 ARL₀ ≈ e^{h_c} 스케일
(오경보 간격), 변화 시 지연 ≈ h_c/E₁[LLR]. Moustakides 1986 (Ann. Statist. 14:1379–1387)이
CUSUM의 minimax 최적성(주어진 ARL₀에서 최악-경우 검출지연 최소)을 증명. HW: LUT(작음) +
가산기 + max + 비교기 — 가능하지만 상태 검증이 복잡해짐.

### 4.5 2-state Markov/HMM + 전환비용 (POMDP)

장면 상태를 2-state Markov chain으로 두고 forward recursion으로 posterior π_t를 갱신
(Rabiner 1989, Proc. IEEE 77(2):257–286), 전환은 posterior가 비용 유도 임계를 넘을 때만.
전환비용이 있는 2-상태 POMDP의 최적 정책 역시 **posterior 공간의 hysteresis 밴드**라는
구조 결과가 알려져 있어, 4.1의 Schmitt 밴드는 이 최적 구조의 1차 근사다. 결론적으로
**per-frame Bayes 임계(§1.2)는 비용·prior를, temporal 계층(Schmitt+dwell)은 전환비용을
분담**하는 현재의 계층 분리가 이론적으로도 옳고, 남은 일은 (i) HW checker에 exit-side
임계와 min-dwell을 실제로 넣는 것, (ii) h를 σ_T 실측으로 정당화하는 것뿐이다.

---

## 5. Estimator variance / subsampling — 전 픽셀을 읽을 필요가 없다

### 5.1 이항 표본오차

n 픽셀 표본의 dark-ratio 추정 p̂: Var(p̂) = p(1−p)/n. 최악 p=0.5, 관심 영역 p≈0.8 기준
(N = 1280×720 = 921,600):

| 샘플링 | n | σ(p̂) @p=0.8 | 95% CI 반폭 |
|---|---|---|---|
| 전수 | 921,600 | 0.00042 | ±0.0008 |
| 1/16 | 57,600 | 0.0017 | ±0.0033 |
| 1/64 | 14,400 | 0.0033 | ±0.0065 |
| 1/256 | 3,600 | 0.0067 | ±0.013 |

Hoeffding 부등식 (Hoeffding 1963, JASA 58:13–30): P(|p̂−p|>ε) ≤ 2·exp(−2nε²) →
ε=0.02, 신뢰 1−10⁻⁶에 필요한 n ≥ ln(2·10⁶)/(2·0.02²) ≈ **18,100** (≈1/51 샘플링).
경계 근방 p에서의 신뢰구간은 Wald 대신 Wilson 구간 사용 권장 (Brown, Cai & DasGupta 2001,
Statistical Science 16(2):101–133;
https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.full).

**판정 신뢰성 결론**: 1/64 샘플링의 CI ±0.0065는 hysteresis 밴드 폭 0.6은 물론 Youden
sweep의 임계 민감도(80% vs 83%, 3%p)보다도 한 자릿수 작다 — **판정 품질 손실이 사실상 0**.

### 5.2 공간 상관과 샘플 설계

픽셀은 iid가 아니라 공간 상관을 가지므로 유효 n이 줄어든다. 다만 양의 자기상관 필드에서
**systematic(격자) 샘플링의 분산은 단순임의추출 이하**임이 표본론의 고전 결과다
(Cochran 1977, *Sampling Techniques* 3e, Ch.8). 설계 시 Bayer 주의: 짝수 stride는 단일
채널(RGGB의 R)만 표본하므로, (i) G 픽셀만 표본(전통 metering처럼 G≈luminance proxy —
RESEARCH의 Y=(R+2G+B)/4에서 G 가중 1/2와 정합) 하거나 (ii) 16×16 타일당 2×2 quad를 읽어
4채널을 유지한다.

### 5.3 HW 절감의 실체

비교기는 어차피 1개이므로 로직 절감은 미미하다. 실제 절감은 **메모리 대역폭과 지연**:
현재 checker는 본 파이프라인 이전에 m_axi로 프레임 전체(≤2,073,600 read)를 한 번 더
읽는다. 1/64 타일 샘플링이면 이 사전 패스가 64× 짧아진다. 더 좋은 대안은 **checker를
본 스트리밍 패스에 접어 넣고 통계를 다음 프레임 판정에 쓰는 것**(1-frame lag, 추가
패스/대역폭 0): §4의 temporal 필터(EWMA, N-frame voting)가 어차피 수 프레임 지연을
도입하므로 1-frame lag은 무해하다.

---

## 6. Threshold adaptivity — Otsu/entropy는 이 문제에 역효과

### 6.1 Otsu의 수리와 HW 비용

Otsu 1979 (IEEE Trans. SMC 9(1):62–66, DOI 10.1109/TSMC.1979.4310076): between-class
variance 최대화

```text
σ_B²(t) = ω₀(t)·ω₁(t)·[µ₀(t) − µ₁(t)]²,  t* = argmax_t σ_B²(t)
```

256-bin histogram(BRAM 256×32-bit) 1-pass 축적 + 256-step 누적 스캔으로 정수 구현 가능
(누적합 ω, 누적 1차모멘트로 µ₀,µ₁ 계산; 나눗셈 회피 위해 교차곱 비교). HLS 비용:
BRAM 1개 + MAC 소수 — 불가능하지 않다.

### 6.2 왜 부적합한가 — 조도 불변성의 역설

Otsu는 **프레임 내부의 이봉 분리**("이 장면에서 어두운 영역/밝은 영역의 경계는 어디인가")
에 답한다. 전역 조도를 k배 낮춘 프레임에서도 정규화된 분리점은 거의 그대로 따라
내려가므로, **Otsu-adaptive τ 기반 dark-ratio는 전역 조도 변화에 근사 불변**이 된다 —
그런데 checker의 임무가 바로 그 전역 조도를 측정하는 것이다. 즉 scene-adaptive threshold는
분류 대상 신호를 정규화로 지워버리는 순환 구조다. 추가 결함: 저조도 프레임의 histogram은
흑 근방 단봉(unimodal)인데, Otsu는 단봉/심한 불균형 클래스에서 임의적 분리점을 내는 것으로
잘 알려져 있다 (Kittler & Illingworth 1986, Pattern Recognition 19(1):41–47의 minimum-error
thresholding 논의). 엔트로피 기반 임계 (Kapur, Sahoo & Wong 1985, CVGIP 29:273–285)도
동일한 조도-불변성 반론이 적용된다.

### 6.3 정당한 adaptivity 축은 장면이 아니라 센서 상태

2-RM 시스템의 결정경계는 자유도 1이면 충분하고, 소규모 보정셋에서 파라미터를 늘리면
결정규칙의 분산(overfitting)만 커진다 (bias–variance; Duda, Hart & Stork 2001, Ch.9).
**τ가 적응해야 할 대상은 장면 내용이 아니라 센서 동작점** — §3.2의 τ(s, g)처럼 AE의
exposure/gain 메타데이터에 따라 host가 AXI-lite로 갱신하는 slow adaptation이 원리적으로
옳고 fragility가 없다. Otsu histogram 하드웨어를 넣을 가치가 있다면 그것은 adaptive τ가
아니라 §2.2의 **다점 percentile 통계**(고정 bin 경계의 coarse 16-bin log-histogram)로
쓰는 경우다.

---

## 7. 종합 권고 (impact vs HLS cost 순위)

| # | 제안 | 근거 | 공식/절 | HLS 비용 | 판단 |
|---|---|---|---|---|---|
| 1 | **HW checker에 exit 임계+min-dwell 추가** (Schmitt 0.80/0.20 + dwell ≥ ⌈t_PR/t_frame⌉ + λ=1/4 EWMA) | Schmitt 1938; Dixit 1989; Page 1954 ARL | §4.1–4.3 | 레지스터 2 + 비교기 1 + 시프터 (거의 0) | **즉시 채택**. 현재 scheduler에만 있는 기능의 HW 이관; flapping 확률 Q(h/σ_T)로 정량 보장 |
| 2 | **임계 재보정 목적함수를 Youden J → 기대 mAP(Bayes risk)로** (C_FA=0.0387, C_miss=0.1118 실측 반영, 배포 prior 명시) | Neyman & Pearson 1933; Duda et al. 2001; §1.2 실측 | §1.1–1.2 | 0 (상수 변경) | **즉시 채택**. 비용비 2.9:1이 이미 측정돼 있음 |
| 3 | **τ의 SNR 유도 + gain 스케일링 문서화/적용**: τ(s,g) = BLC + g·K₀·e*(s), e*=(s²+s√(s²+4σ_d²))/2 | EMVA 1288; Janesick 2007; Rose 1948; ISO 12232 | §3.2 | 0 (기존 AXI-lite port 활용) | **채택**. pseudo-RAW 단계에선 문서화, 실센서에서 활성화. dark-ratio를 "low-SNR pixel ratio"로 승격 |
| 4 | **1/64 systematic 샘플링 또는 본 패스 통합(1-frame lag)** | Hoeffding 1963; Brown et al. 2001; Cochran 1977 | §5 | 로직 동일, 대역폭 64× 절감 또는 사전 패스 제거 | **채택**. CI ±0.0065 ≪ 밴드 0.6; #1의 지연과 결합 시 lag 무해 |
| 5 | **스트리밍 log₂-mean 병행 통계** (leading-one encoder + accumulator), (T, logmean) 2-임계 결합 | Reinhard et al. 2002; Gonzalez & Woods 2018 | §2.1, 2.3 | priority encoder + 32-bit 가산기 (매우 작음) | **권장**. §1.3 tail 실패 모드 해소; 조도 equivariant |
| 6 | coarse 16-bin log-histogram (BRAM) → 다점 percentile | §2.2; Cover & Thomas 2006 (양자화-divergence) | §2.2, 6.3 | BRAM 1 + RMW (II 주의) | 보류: 2-RM에는 #5로 충분, RM 종류 확장 시 재검토 |
| 7 | CUSUM / HMM posterior 판정 | Page 1954; Moustakides 1986; Rabiner 1989 | §4.4–4.5 | LUT + 상태 가산기 | 보류: #1 이후에도 flapping 관측될 때만 |
| 8 | Otsu/entropy scene-adaptive τ | Otsu 1979; Kittler & Illingworth 1986 | §6.2 | BRAM + MAC | **비권장**: 조도 불변성이 checker 목적과 모순, 단봉 histogram에서 퇴화 |

핵심 논지 요약: (1) dark-ratio 통계 자체는 τ를 SNR로 유도하면 물리적으로 정당한
"usable-SNR 미만 픽셀 비율"이 된다 — 통계량 교체보다 **임계의 유도 방식과 판정 기준의
교정**이 우선이다. (2) 판정 기준은 Youden J가 아니라 실측 ΔmAP 가중 Bayes risk여야 하며
비용비 2.9:1이 이미 손에 있다. (3) 전환비용은 per-frame 임계가 아니라 temporal 계층
(Schmitt+dwell)이 담당하는 현재 구조가 이론적으로 옳고, 이를 HW로 이관하는 것이 최저
비용·최대 효과 개선이다. (4) 전수 판독은 통계적으로 불필요하다(1/64로 충분).

---

## References

1. Neyman, J. & Pearson, E.S. (1933). "On the Problem of the Most Efficient Tests of
   Statistical Hypotheses." *Philosophical Transactions of the Royal Society A* 231:289–337.
   doi:10.1098/rsta.1933.0009
2. Duda, R.O., Hart, P.E. & Stork, D.G. (2001). *Pattern Classification*, 2nd ed. Wiley.
   (Ch.2 Bayes decision theory; Ch.9 model complexity)
3. Youden, W.J. (1950). "Index for Rating Diagnostic Tests." *Cancer* 3(1):32–35.
   doi:10.1002/1097-0142(1950)3:1<32::AID-CNCR2820030106>3.0.CO;2-3
   https://acsjournals.onlinelibrary.wiley.com/doi/10.1002/1097-0142(1950)3:1%3C32::AID-CNCR2820030106%3E3.0.CO;2-3
4. Lehmann, E.L. & Romano, J.P. (2005). *Testing Statistical Hypotheses*, 3rd ed. Springer.
   (§3.4 Karlin–Rubin / MLR UMP tests)
5. Cover, T.M. & Thomas, J.A. (2006). *Elements of Information Theory*, 2nd ed. Wiley.
   (Thm 2.8.1 data-processing inequality; Ch.11 Chernoff–Stein)
6. Reinhard, E., Stark, M., Shirley, P. & Ferwerda, J. (2002). "Photographic Tone
   Reproduction for Digital Images." *ACM Transactions on Graphics* 21(3):267–276 (SIGGRAPH).
   https://www.cs.utah.edu/docs/techreports/2002/pdf/UUCS-02-001.pdf
7. ISO 12232:2019. *Photography — Digital still cameras — Determination of exposure index,
   ISO speed ratings, standard output sensitivity, and recommended exposure index.* ISO.
8. European Machine Vision Association (2010). *EMVA Standard 1288 — Standard for
   Characterization of Image Sensors and Cameras*, Release 3.0.
   https://www.emva.org/wp-content/uploads/EMVA1288-3.0.pdf
   (해설: https://www.baslerweb.com/en/learning/emva-1288-standard/)
9. Janesick, J.R. (2007). *Photon Transfer: DN → λ*. SPIE Press.
10. Rose, A. (1948). "The Sensitivity Performance of the Human Eye on an Absolute Scale."
    *Journal of the Optical Society of America* 38(2):196–208. (Rose criterion, SNR≈5)
11. Page, E.S. (1954). "Continuous Inspection Schemes." *Biometrika* 41(1/2):100–115.
    (CUSUM, average run length) https://en.wikipedia.org/wiki/CUSUM
12. Moustakides, G.V. (1986). "Optimal Stopping Times for Detecting Changes in
    Distributions." *Annals of Statistics* 14(4):1379–1387.
13. Wald, A. (1945). "Sequential Tests of Statistical Hypotheses." *Annals of Mathematical
    Statistics* 16(2):117–186. (SPRT, sequential 판정의 원형)
14. Dixit, A. (1989). "Entry and Exit Decisions under Uncertainty." *Journal of Political
    Economy* 97(3):620–638. (전환비용 하 최적 hysteresis 밴드, 폭 ∝ 비용^(1/3))
15. Rabiner, L.R. (1989). "A Tutorial on Hidden Markov Models and Selected Applications in
    Speech Recognition." *Proceedings of the IEEE* 77(2):257–286.
16. Schmitt, O.H. (1938). "A Thermionic Trigger." *Journal of Scientific Instruments*
    15(1):24–26.
17. Brown, L.D., Cai, T.T. & DasGupta, A. (2001). "Interval Estimation for a Binomial
    Proportion." *Statistical Science* 16(2):101–133.
    https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.full
18. Hoeffding, W. (1963). "Probability Inequalities for Sums of Bounded Random Variables."
    *Journal of the American Statistical Association* 58(301):13–30.
19. Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley. (Ch.8 systematic sampling)
20. Otsu, N. (1979). "A Threshold Selection Method from Gray-Level Histograms." *IEEE
    Transactions on Systems, Man, and Cybernetics* 9(1):62–66. doi:10.1109/TSMC.1979.4310076
21. Kapur, J.N., Sahoo, P.K. & Wong, A.K.C. (1985). "A New Method for Gray-Level Picture
    Thresholding Using the Entropy of the Histogram." *Computer Vision, Graphics, and Image
    Processing* 29(3):273–285.
22. Kittler, J. & Illingworth, J. (1986). "Minimum Error Thresholding." *Pattern
    Recognition* 19(1):41–47.
23. Gonzalez, R.C. & Woods, R.E. (2018). *Digital Image Processing*, 4th ed. Pearson.
    (§2.3 image formation I=R·E; §3.3 homomorphic; Ch.10 thresholding)
24. Bernacki, J. (2020). "Automatic Exposure Algorithms for Digital Photography."
    *Multimedia Tools and Applications* 79:12751–12776.
    https://link.springer.com/article/10.1007/s11042-019-08318-1
25. Loh, Y.P. & Chan, C.S. (2019). "Getting to Know Low-light Images with the Exclusively
    Dark Dataset." *Computer Vision and Image Understanding* 178:30–42.
    http://cs-chan.com/doc/cviu.pdf

내부 근거 자료: `results/map_ablation2_{coco,exdark}_yolov8n.csv` (오판 비용 실측),
`results/experiment_ver2_2026-07-02.md` (Youden sweep), `RESEARCH.md` §5,
`SPEC.md` §3.1, `tools/scheduler_sim.py` (temporal 정책 실측).
