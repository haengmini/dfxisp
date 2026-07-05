<!--
File   : isppipeline/hls/results/lowlight-feature-principles-2026-07-05.md
Date   : 2026-07-05 21:28 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3
Track  : Low-light RM (goal 명령 Part 2) — 원리 정의 정본
-->
# 저조도 영상의 머신비전 지향 처리 원리 및 feature 추출 기준 (정본)

**작성:** 2026-07-05 21:28 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` · **캠페인:** `principled-v3`

본 문서는 goal 명령 Part 2의 (a)(b)(c) — *저조도 이미지를 머신비전용으로 처리할 때 무엇을
가장 무겁게 가중해야 하는가*, *어떤 기준으로 feature를 추출해야 하는가*, *각각의
수학적·과학적 근거는 무엇인가* — 를 단일 정본으로 응결한 것이다. 근거 문헌은
`lowlight-mv-isp-survey-2026-07-03.md`(이하 [SURVEY])의 참고문헌 번호를 그대로 인용한다.
이 원리로부터 구현한 RM 버전(R1/R2/R3)과 그 mAP 실험은
`lowlight-rm-principled-versions-2026-07-05.md`에 있다.

---

## 0. 한 문장 요약

> 저조도 처리의 목적 함수는 "밝게"가 아니라 **"SNR을 올리고(binning/edge-preserving denoise),
> 남은 신호의 대비를 검출기가 학습한 입력 분포로 분산안정화(VST/tone)하여 재배치하되,
> CNN이 의존하는 고주파 구조를 파괴하지 않는 것"** 이다.

---

## 1. 원리 P0 — 저조도의 본질은 어둠이 아니라 낮은 SNR

### 1.1 노이즈 물리 모델 (근거: Foi 2008 [1]; EMVA1288 [3]; Janesick [2])

센서 raw 관측 모델(heteroscedastic Poisson-Gaussian):

```
z = y + σ(y)·ξ,     σ²(y) = a·y + b
  a·y : photon shot noise (Poisson) — 신호에 비례
  b   : read noise 등 (Gaussian)   — 신호 무관, 극저조도에서 지배
```

총 분산의 선형 모델(EMVA1288): `σ²_total = σ²_read + σ²_quant + K·μ` (K=system gain).

### 1.2 SNR-신호 곡선 — 저조도에서 신호 손실은 SNR에 2배 기울기로 타격

전자 수 N_e에서 `SNR = N_e / √(N_e + σ²_read + N_dark)`:

- 밝은 영역(shot-limited): `SNR ≈ √N_e` → 광량 10× 당 **+10 dB**.
- 어두운 영역(read-limited): `SNR ≈ N_e / σ_read` → 광량 10× 당 **+20 dB**.

즉 read-noise floor 근처(=저조도)에서는 신호가 줄면 SNR이 **slope-2 페널티**로 급락한다.
저조도 프레임은 Photon Transfer Curve의 **왼쪽 끝**(read-floor↔shot 전이 구간)에서 촬영된
영상이며, 12-bit raw라도 실효 정보량은 6–8 bit 수준으로 압축된다([SURVEY] A.1.3, A.2).

### 1.3 결론 (a)에 대한 1차 답

**가장 무겁게 가중해야 할 것 = SNR과 local contrast의 보존/복원이지 화면 밝기가 아니다.**
근거: Rodríguez-Rodríguez 2024 [12]은 noise 종류 × 밝기 축소를 직교 ablation하여
**noise의 영향이 밝기 축소의 영향을 능가**함을 정량 확인했고, Hong 2021 [11]은 초저조도
detection 실패 원인을 *significantly low SNR*로 명시했다. Dodge-Karam 2016 [13]은 CNN이
blur·noise에 특히 취약하고 contrast·JPEG에는 상대적으로 강인함을 보였다.

---

## 2. 원리 P1 — 사람용 enhancement ≠ 머신용 전처리

- Wu 2024 [14]: 다수 LLIE 기법을 detection/classification 앞단에 붙인 실증 연구 —
  **LLIE는 인간 시각 해석은 개선하나 vision task에는 비일관적이며 때로 유해**.
- Diamond 2021 [21] (Dirty Pixels): 분류 최적 파이프라인은 fine detail을 살리는 대신
  **PSNR/SSIM은 오히려 나빠짐** — "vision 최적 ≠ IQ 최적"의 극단적 증거.
- 함의: tone/denoise를 *보기 좋게*가 아니라 *검출 손실 함수*로 정당화해야 한다. 밝기
  자체를 목표로 삼는 retinex류 단독 lift는 노이즈를 함께 증폭하므로 회피([SURVEY] B.2.7).

---

## 3. 원리 P2 — vision-ISP에서 결정적 stage는 demosaic와 tone(gamma)

- Buckler 2017 [16] (ICCV): 8개 vision 알고리즘 × ISP stage ablation에서 **demosaic와
  gamma 압축 두 stage만 task 성능에 결정적**; denoise·color/gamut mapping은 대부분 생략 가능.
- ISP4ML [17]: HDR 입력에서 **tone mapper가 단일 stage 최대 기여(+5.8%)**.
- ROD [26], Ljungbergh 2023 [23]: raw detection의 병목은 **dynamic range 조정(tone)**;
  learnable gamma/Yeo-Johnson **단일 연산**만으로 RGB baseline 초과, **특히 저조도에서 우위**.

### 3.1 결론 (b)에 대한 답 — feature 추출 기준

추출/보존해야 할 feature = **"적정 SNR 하의 고주파 구조(에지·텍스처)"** 와
**"검출기 학습 분포로 매핑된 dynamic range"** 두 가지다. 구체적 기준:

1. **고주파 우선(고SNR 조건부):** CNN detection은 에지·텍스처(high-frequency) feature에
   의존한다(Buckler [16]; Dodge-Karam [13]). 따라서 해상도와 국소 대비를 지키는 것이
   1순위다 — 단, 신호가 read-floor 이하인 영역에서는 고주파가 곧 노이즈이므로 무차별
   보존이 아니라 **SNR이 확보된 곳의 고주파만** 선택적으로 보존한다(edge-preserving).
2. **분산안정화된 톤 공간에서의 대비:** feature의 판별력은 코드 공간의 분산이 신호준위와
   무관하게 균일할 때 극대화된다 → VST(§4) 도메인에서 대비를 정의한다.
3. **검출기 입력 분포 정합:** 최종 톤은 detector가 pretrain된 sRGB류 분포(대략 gamma≈2.2,
   지수 0.45)에 맞춰야 domain shift를 최소화한다(Loh-Chan [9]: 저조도 low-level 통계가
   달라 밝은 데이터로 학습한 feature가 전이되지 않음).

---

## 4. 원리 P3 — 원리적 연산 4종과 그 수학

각 연산은 위 원리에서 유도되며, 모두 정수·HW 매핑 가능(BRAM LUT / line buffer)해야 한다.

### 4.1 Binning — 잉여 공간해상도를 SNR로 교환 (근거: [28][29]; [SURVEY] B.2.2)

2×2 same-color 합산 시 신호 4배. Read-noise-limited에서 노이즈는 √4=2배(독립 read noise
합) → **SNR +6 dB**. Shot-limited에서는 +3 dB. 대가는 해상도 1/2(H/2×W/2).

- 정량 트레이드오프: 객체 픽셀 면적이 1/4로 줄어 32–64px 객체를 small-object 구간으로
  밀어 넣는다. Rodríguez-Rodríguez 2024 [12]는 **작은 객체가 열화 이전에도 검출 취약**함을
  보였다 → binning의 손익분기점은 **(조도, 객체 크기 분포)의 함수**.
- 이 손익분기를 **size별 AP 분해(small/med/large)로 실측**하는 것이 본 캠페인의 named
  기여([SURVEY] B.2.2). CFA semantics 보존을 위해 same-color 2×2 집계여야 함(Jin-Hirakawa
  [28]).

### 4.2 VST / Anscombe tone — gamma≈0.5는 원리적 분산안정화기 (근거: [7][8]; Diamond [21])

Anscombe 변환 `f(x)=2√(x+3/8)`은 Poisson을 근사 단위분산 Gaussian으로 변환한다. Poisson-
Gaussian용 Generalized Anscombe Transform(GAT):

```
f(z) = (2/a)·√(a·z + 3/8·a² + b)       (a>0)
```

- 핵심: **제곱근형(gamma≈0.5) 톤은 "보기 좋게"가 아니라 노이즈 분산을 코드 공간에서
  균일화하는 원리적 연산**이다. 상수항 `3/8·a²+b`(read-floor 오프셋)는 곡선의 최하부를
  평탄화하여 **read-noise floor를 과증폭하지 않게** 한다 — 신호 없는 곳의 노이즈를 들어올리지
  않는다는 §3.1(1)의 "고SNR 조건부"를 톤 단계에서 구현하는 항.
- HW: VST는 **1D LUT 하나**(BRAM 1개). gamma LUT slot에 GAT형 곡선을 넣으면 tone과 VST를
  동시에 얻는다(Diamond 2021 [21]의 Anscombe network 선례). 상부 **soft-knee**(highlight
  roll-off)를 더하면 소수의 밝은 픽셀이 hard-clip되어 구조를 잃는 것을 막는다.
- 참고: 현행 R0의 gamma2.5(지수 0.4)는 sRGB에 가깝게 더 강하게 lift하나 VST 정합은 아니다.
  gamma2.0=√는 정확한 Poisson VST다 — 본 캠페인이 두 톤을 실측 비교하는 이유.

### 4.3 Gain 배치 — 상류(raw, 양자화 이전) (근거: Chen 2018 [22]; [SURVEY] B.2.4)

gain은 SNR을 바꾸지 못한다(신호·노이즈 동배율). 실익은 (1) 후단 양자화/클리핑 전에 코드
공간 확보, (2) 검출기 입력 분포 정합뿐이다. 따라서 **비트폭이 넓은 raw 상류에서, demosaic·
양자화 이전에** 적용해야 quantization 손실이 최소다. 저조도+고gain에서 `σ²_quant`가 g배로
벌어지므로 배치 순서가 중요.

### 4.4 Conditional light denoise — edge-preserving만 (근거: Diamond [21]; [32][33]; [SURVEY] B.2.1)

노이즈가 인과 사슬의 주범이므로 denoise는 1순위 개입점이나, **과도한 denoise는 CNN이
의존하는 고주파를 제거하여 성능을 떨어뜨린다**(Diamond 2021 [21]: IQ 기준 "덜 지운" 상태가
분류 최적; WaveCNet [32]; Li 2021 [33]). BM3D류 비지역 탐색은 FPGA streaming 부적합.
→ 실용해 = **binning과 결합한 경량 edge-preserving 3×3**(Lee sigma filter / 정수 bilateral
근사): 에지를 넘는 이웃은 평균에서 제외해 flat 영역 노이즈만 억제. binning 후 폭이 절반이라
line buffer도 절반(시너지).

---

## 5. 원리 → 버전 매핑 (구현: `tools/rm_versions.py`)

| 버전 | 구성 | 사용 원리 | 검증 가설 |
|---|---|---|---|
| **R0** baseline | 2×2 bin + BLC8+WB+gain2.0 + gamma2.5 | 현행 canonical | 대조군 |
| **R1** RM_TONE_LUT_PARAM | full-res + gain(상류)+soft-knee + **VST/GAT sqrt LUT** | P2·P3(§4.2/4.3) | 해상도 보존(small object↑) + VST가 gamma2.5보다 노이즈 관점 우월 |
| **R2** RM_LL_BIN_DN | 2×2 bin + edge-preserving 3×3 + VST tone | P0·P3(§4.1/4.4/4.2) | binning +6dB + 경량 denoise가 저조도 SNR 개선 |
| **R3** RM_TONE_CLAHE | full-res + gain+soft-knee + **CLAHE local tone** | P2·P3(§4.2 local) | 저대비·불균일 조명 국소 보상 |

---

## 6. 한계 및 정직한 유보

1. **pseudo-RAW 노이즈 부재:** 데이터셋 raw_bin은 sRGB의 역변환 pseudo-RAW로 실제 센서
   Poisson-Gaussian 노이즈가 없다. 따라서 VST·denoise의 "노이즈 억제" 이득은 **과소평가**될
   수 있고(억제할 노이즈가 적음), 결론의 방향성은 유효하나 절대 이득은 real-RAW로 재검증
   필요(Rawgment [25] 취지). binning의 해상도 비용과 tone의 분포 정합 효과는 pseudo-RAW로도
   유효하게 측정된다.
2. **size-AP 방법:** 모든 arm을 공통 full-res 좌표계에서 pycocotools COCOeval로 평가해
   객체 크기 버킷을 arm 간 동일하게 고정(방법 상세는 결과 문서 §방법).
3. **CPU-only, n=150(최종 winner는 575 가능):** 경향(부호·상대크기) 검증이 목적.
4. VST의 read-offset·soft-knee, denoise 임계는 소수의 정수 하이퍼파라미터로, 실측 튜닝
   대상이나 본 캠페인은 원리적 기본값으로 고정해 비교의 공정성을 확보한다.

---

## 참고문헌

번호는 `lowlight-mv-isp-survey-2026-07-03.md`의 References와 동일. 핵심:
[1] Foi 2008 (Poisson-Gaussian) · [2] Janesick 2007 · [3] EMVA1288 · [7] Anscombe 1948 ·
[8] Mäkitalo-Foi TIP'11/13 (GAT inverse) · [9] Loh-Chan CVIU'19 (ExDark) ·
[11] Hong BMVC'21 (low SNR) · [12] Rodríguez-Rodríguez Sensors'24 (noise>brightness) ·
[13] Dodge-Karam QoMEX'16 · [14] Wu 2024 (LLIE≠vision) · [16] Buckler ICCV'17 ·
[17] ISP4ML · [21] Diamond SIGGRAPH'21 (Dirty Pixels/Anscombe) · [22] Chen CVPR'18 (SID) ·
[23] Ljungbergh SCIA'23 (learnable gamma) · [26] Xu CVPR'23 (ROD) · [28] Jin-Hirakawa'12 ·
[29] Teledyne binning · [31] Wang JCDE'23 (YOLOX+CLAHE +1.13%p) · [32][33] denoise-harm.
