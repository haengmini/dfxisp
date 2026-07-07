# Low-light 영상 특성과 머신비전 지향 ISP 문헌 조사

작성일: 2026-07-03
프로젝트: DFXISP — 공유 baseline ISP core + mode-specific tone RM (ZCU104, DFX partial reconfiguration)
Downstream consumer: YOLOv8n / SSD-MobileNetV1 object detector (human viewer 아님)
관련 정본 문서: `RESEARCH.md`

---

## 요약 (TL;DR)

1. Low-light 영상의 근본 문제는 "어둡다"가 아니라 **낮은 SNR**이다. Photon shot noise는 신호에 비례해 분산이 커지는 heteroscedastic Poisson 성분이고, 극저조도에서는 read noise floor가 지배한다 (Foi et al. 2008; EMVA 1288; Janesick 2007).
2. Detector 성능 저하의 주범도 밝기 자체보다 **noise와 저대비(local contrast 상실)** 라는 ablation 증거가 있다 (Rodríguez-Rodríguez et al. 2024; Hong et al. 2021). 단순히 "밝게 만드는" enhancement는 detection에 일관되게 도움이 되지 않는다 (Wu et al. 2024 empirical study; LIME-Eval).
3. Human-viewing ISP ≠ vision ISP. CNN vision에는 **demosaic와 gamma(tone) 두 stage만이 결정적**이고 나머지는 생략/약화 가능하다는 것이 Buckler et al. (ICCV 2017)의 핵심 결과이며, ISP4ML은 HDR 입력에서 **tone mapper가 단일 stage로 최대 기여(+5.8%)** 임을 보였다.
4. 본 프로젝트의 `RM_LOW_LIGHT_TONE` (2x2 binning + gain + gamma)은 문헌상 근거가 탄탄하다: binning은 read-noise-limited 영역에서 **+6 dB SNR**, gamma는 Poisson noise에 대한 근사적 variance stabilizer로 작동한다 (Anscombe/GAT 계열; Ljungbergh et al. 2023의 learnable gamma).
5. 3rd/4th RM 후보로는 (1) parametric global tone LUT (학습된 1D LUT), (2) CLAHE-계열 local tone, (3) binning+경량 spatial denoise 강화판이 (detection gain) × (FPGA feasibility) 곱에서 최상위이다. Temporal denoise는 이득 잠재력은 크지만 frame buffer 비용 때문에 후순위.

---

# Part A — Low-light 영상의 특성

## A.1 물리적 노이즈 모델

### A.1.1 구성 성분

센서 raw 신호의 노이즈는 표준적으로 다음 성분으로 분해된다 (Janesick, *Photon Transfer*, SPIE 2007; EMVA 1288; Nakamura, *Image Sensors and Signal Processing for Digital Still Cameras*, CRC 2005).

| 성분 | 통계 | 조도 의존성 | 비고 |
|---|---|---|---|
| Photon shot noise | Poisson, var = μ (electron 수) | 신호에 비례 | 물리적 하한. SNR = √N_e |
| Read noise | 근사 Gaussian, 신호 무관 | 없음 | ADC/amp 기원. 극저조도에서 지배 |
| Dark current shot noise | Poisson (dark electrons) | 노출시간·온도 비례 | 장노출/고온에서 부각 |
| DSNU (Dark Signal Non-Uniformity) | 고정 패턴 (offset) | 없음 | 픽셀별 offset 편차. BLC/보정 대상 |
| PRNU (Photo-Response Non-Uniformity) | 고정 패턴 (gain) | 신호에 비례 | 밝은 영역에서 부각, low-light에선 부차적 |
| Quantization noise | uniform, Δ²/12 | 없음 | 저신호 + 고gain 후 상대적으로 커짐 |

- EMVA 1288 (European Machine Vision Association, Standard 1288 Release 3.0/4.0)은 위 성분들을 photon transfer 방법론으로 측정·보고하는 표준이며, 총 분산을 σ²_total = σ²_read + σ²_quant + K·μ (K: system gain) 의 선형 모델로 기술한다. [emva.org/EMVA1288-3.0.pdf](https://www.emva.org/wp-content/uploads/EMVA1288-3.0.pdf)
- Photon Transfer Curve (PTC): log-log 상에서 노이즈-신호 곡선이 read-noise floor(기울기 0) → shot-noise 영역(기울기 1/2) → PRNU 영역(기울기 1) → full-well saturation으로 이어진다 (Janesick 2007). Low-light 영상은 곡선의 **왼쪽 끝(read-noise floor ~ shot-noise 전이 구간)** 에서 촬영된 영상이다.

### A.1.2 Heteroscedastic Poisson-Gaussian 모델 (Foi et al. 2008)

Foi, Trimeche, Katkovnik, Egiazarian, "Practical Poissonian-Gaussian Noise Modeling and Fitting for Single-Image Raw-Data," *IEEE TIP* 17(10), 2008. [PDF](https://webpages.tuni.fi/foi/papers/Foi-PoissonianGaussianClippedRaw-2007-IEEE_TIP.pdf)

raw 픽셀 z의 관측 모델:

```text
z = y + σ(y)·ξ,   σ²(y) = a·y + b
  a·y : Poisson (photon sensing) 성분 — 신호 의존
  b   : Gaussian (read noise 등 정상 성분) — 신호 무관
```

핵심 시사점:

1. 노이즈 표준편차가 신호의 함수인 **heteroscedastic** 모델이므로, 신호-무관(homoscedastic) Gaussian을 가정하는 처리(균일 강도의 denoise, 균일 threshold)는 low-light raw에 원리적으로 부정합하다.
2. 이 논문은 clipping(under/over-exposure)까지 모델에 포함한다 — low-light에서 black level 근처로 clip된 데이터의 통계 왜곡을 다룬 드문 정식화다.
3. 단일 영상에서 (a, b)를 추정할 수 있으므로, scene checker가 노이즈 파라미터 기반 mode decision을 하는 확장도 원리적으로 가능하다.

### A.1.3 SNR-신호 곡선

전자 수 N_e에서 SNR = N_e / √(N_e + σ²_read + N_dark). 결과:

- 밝은 영역: SNR ≈ √N_e (shot-limited, 10x 광량 → +10 dB SNR).
- 어두운 영역: SNR ≈ N_e / σ_read (read-limited, 10x 광량 → +20 dB SNR — 즉 low-light에서 광량/신호 손실은 SNR에 2배 기울기로 타격).
- 이 구간 전환이 EMVA 1288 SNR 곡선의 표준 형태다. Chan 계열의 exposure-referred SNR 논의도 참조 (Gnanasambandam & Chan, "Exposure-Referred SNR for Digital Image Sensors," 2022, [arXiv:2112.05817](https://arxiv.org/pdf/2112.05817)).

## A.2 영상 도메인에서의 결과

물리 모델이 ISP 입력 영상에 남기는 흔적:

1. **낮은 SNR / 텍스처 상실**: 신호가 read-noise floor에 근접 → 미세 텍스처·에지의 대비가 노이즈 표준편차 이하로 침몰. Local contrast 및 high-frequency detail 상실.
2. **Black level 근처로 압축된 histogram**: 코드 값 대부분이 하위 수십 LSB에 몰림. 유효 bit depth가 급감 — 12-bit raw라도 low-light frame의 실효 정보는 6–8 bit 수준.
3. **Gain 이후 quantization 지배**: digital gain g를 곱하면 quantization step도 g배로 벌어진다. 저조도 + 고gain 조합에서 posterization/banding이 발생하며, gamma로 dark region을 당길수록 step이 더 벌어진다. (EMVA 1288의 σ²_quant 항; Nakamura 2005의 ISP gain 배치 논의)
4. **WB/CCM에 의한 color noise 증폭**: AWB는 채널별 gain(통상 R, B gain > 1)을 곱하므로 해당 채널 노이즈가 그대로 증폭된다. CCM은 채도 복원을 위해 off-diagonal에 음수 계수를 갖는 것이 보통이며, 출력 분산은 σ²_out,i = Σ_j m²_ij σ²_in,j 로 **계수 절대값 제곱합만큼 증폭**된다 — 채도를 강하게 복원할수록(행렬 계수가 클수록) 노이즈 페널티가 커진다. 이것이 low-light에서 **chroma noise > luma noise** 가 되는 표준 기제다 (Nakamura 2005, ch. on color processing; Foi 2008의 pipeline 위치별 노이즈 논의).
5. **Motion blur ↔ exposure 트레이드오프**: 노출시간을 늘리면 shot noise SNR은 √t로 개선되지만 motion blur가 선형으로 악화. 짧은 노출 + 고gain은 노이즈를, 긴 노출은 blur를 택하는 것 — low-light 시스템의 근본 딜레마이며 Chen et al. (2018)의 SID가 "짧은 노출 raw를 학습으로 복원"이라는 형태로 우회한 지점이다.

## A.3 Detector 관점의 저하: 측정과 원인 분석

### A.3.1 저하 측정 (benchmarks)

- **ExDark** — Loh & Chan, "Getting to Know Low-light Images with the Exclusively Dark Dataset," *CVIU* 178, 2019. [GitHub](https://github.com/cs-chan/Exclusively-Dark-Image-Dataset), [ResearchGate](https://www.researchgate.net/publication/329150833_Getting_to_know_low-light_images_with_the_Exclusively_Dark_dataset). 7,363장, 10가지 저조도 조건, 12 클래스 (본 프로젝트의 dark-condition dataset). 기존 대형 dataset의 low-light 비중이 2% 미만임을 지적하고, hand-crafted feature와 CNN feature 모두 low-light에서 체계적으로 열화됨을 실증 — 특히 저조도에서 low-level feature 통계가 밝은 영상과 상이해 **밝은 데이터로 학습된 feature가 전이되지 않음**을 보였다.
- **DARK FACE / UG2+** — Yang et al., CVPR Workshop UG2+ Challenge. [dataset 페이지](https://flyywh.github.io/CVPRW2019LowLight/). 야간 실촬영 얼굴 6,100장(+challenge 10,000장). WIDER FACE hard에서 mAP 90%+를 내는 DSFD가 DARK FACE에서 **mAP 15.3%로 붕괴** — 저조도 단독으로 SOTA detector를 무력화함을 보이는 가장 극적인 수치.
- **LOD dataset** — Hong, Wei, Chen, Fu, "Crafting Object Detection in Very Low Light," *BMVC* 2021. [프로젝트](https://kxwei.net/publication/bmvc21_lod/), [GitHub](https://github.com/ying-fu/LODDataset). 저조도 raw-RGB 쌍의 detection dataset.

### A.3.2 왜 저하되는가 — noise vs brightness vs contrast ablation

- **Rodríguez-Rodríguez et al., "The Impact of Noise and Brightness on Object Detection Methods," *Sensors* 24(3):821, 2024.** [MDPI](https://www.mdpi.com/1424-8220/24/3/821), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10856852/). YOLOv5/v8 (n/m/x)과 Faster R-CNN에 대해 noise 종류(Poisson/Gaussian/salt-pepper/uniform) × 밝기 축소(0.1–1.0)를 직교로 ablation. 결론: (1) **noise의 영향이 밝기 축소의 영향을 능가**한다, (2) **작은 객체는 노이즈가 없고 조도가 적절해도 이미 검출이 취약**하며 열화 요인에 가장 민감하다. → 후자는 binning의 해상도 손실이 small object에 미칠 위험을 정량 근거로 뒷받침하는 결과 (B.2.2 참조).
- **Hong et al. (BMVC 2021)**: 초저조도 detection 실패의 원인을 **significantly low SNR**로 명시하고, "enhancement를 detection 앞단에 붙이는 통상적 관행은 연산량만 크게 늘리고 만족스러운 결과를 주지 못한다"고 보고. 대신 현실적 노이즈 모델 기반 합성(low-light synthetic pipeline) + 보조 recovery module이 유효함을 보임 — 즉 해결의 열쇠는 밝기가 아니라 **노이즈 통계의 정합**.
- **Dodge & Karam, "Understanding How Image Quality Affects Deep Neural Networks," *QoMEX* 2016.** [ResearchGate](https://www.researchgate.net/publication/301876936_Understanding_How_Image_Quality_Affects_Deep_Neural_Networks). CNN 분류기가 blur와 noise에 특히 취약하고 contrast/JPEG에는 상대적으로 강인함을 보인 고전적 ablation — "밝기·대비보다 noise가 CNN feature를 깨뜨린다"는 계열의 출발점.
- **Wu et al., "Low-Light Enhancement Effect on Classification and Detection: An Empirical Study," 2024.** [arXiv:2409.14461](https://arxiv.org/pdf/2409.14461). 다수 LLIE(low-light image enhancement) 기법을 detection/classification 앞단에 붙여 체계 평가: **LLIE는 인간 시각 해석은 개선하지만 vision task 효과는 비일관적이며 때로 유해** — "사람 보기 좋은 enhancement ≠ 머신에 좋은 전처리"의 직접 증거. 같은 취지로 LIME-Eval ([arXiv:2410.08810](https://arxiv.org/pdf/2410.08810))은 LLIE 평가 자체를 detection 기준으로 재정의할 것을 제안.

**종합**: detector 열화의 인과 사슬은 `광자 부족 → 낮은 SNR(read-noise floor) → gain/WB/CCM에 의한 노이즈·chroma noise 증폭 → CNN이 의존하는 high-frequency feature 파괴 + 저대비` 이며, 화면 밝기 자체는 부차적이다. 따라서 low-light ISP의 목표 함수는 "밝게"가 아니라 **"SNR을 올리고(binning/denoise), 남은 신호의 대비를 detector 입력 범위로 재배치(tone)"** 가 되어야 한다.

---

# Part B — 머신비전 지향 ISP 모듈

## B.1 ISP-for-viewing ≠ ISP-for-vision: 핵심 증거

| 논문 | 발견 | 본 프로젝트 함의 |
|---|---|---|
| Buckler, Jayasuriya, Sampson, "Reconfiguring the Imaging Pipeline for Computer Vision," *ICCV 2017* ([open access](https://openaccess.thecvf.com/content_iccv_2017/html/Buckler_Reconfiguring_the_Imaging_ICCV_2017_paper.html), [arXiv:1705.04352](https://arxiv.org/pdf/1705.04352)) | 8개 vision 알고리즘(CNN 포함) × ISP stage ablation. **demosaic와 gamma 압축 두 stage만 task 성능에 결정적**; denoise·tone·gamut/color mapping 등은 생략해도 대부분 알고리즘에서 손실 미미. "vision mode"(subsample 기반 demosaic 대체 + log gamma + 저bit ADC)로 ~75% 에너지 절감 | (1) 본 프로젝트가 tone(gamma)을 RM으로 분리한 것은 "결정적인 stage를 mode별로 특화한다"는 점에서 정확히 문헌과 정렬. (2) baseline core의 CCM/AWB는 detection에 2차적 → 단순 고정 구현으로 충분하다는 근거 |
| Hansen et al., "ISP4ML: The Role of Image Signal Processing in Efficient Deep Learning Vision Systems," 2019 ([arXiv:1911.07954](https://arxiv.org/abs/1911.07954)) | configurable ISP 시뮬레이터 + ImageNet: ISP 유무로 MobileNet 정확도 **+4.6–12.2%**. stage ablation에서 **HDR 입력 시 tone mapper가 단일 최대 기여(+5.8% 평균)** | tone stage가 vision용 ISP의 최중요 블록 → tone RM slot에 DFX 투자를 집중하는 본 설계의 직접 근거 |
| Wu et al., "VisionISP: Repurposing the Image Signal Processor for Computer Vision Applications," *ICIP 2019* ([arXiv:1911.05931](https://arxiv.org/abs/1911.05931)) | vision 소비용으로 bit-depth·해상도를 줄이는 trainable block(Vision Local Tone Mapping = global nonlinearity + local detail boost, Trainable Vision Scaler). 최적 perceptual IQ ≠ 최적 CV 성능 | "global tone + local detail boost" 조합과 "vision-aware downscaling"은 각각 CLAHE-계열 RM과 binning RM의 산업계 대응물 |
| Yahiaoui et al. (Valeo), "Optimization of ISP parameters for object detection algorithms," *Electronic Imaging AVM* 2019; "Overview and Empirical Analysis of ISP Parameter Tuning for Visual Perception in Autonomous Driving," *J. Imaging* 5(10):78, 2019 ([MDPI](https://www.mdpi.com/2313-433X/5/10/78)) | detection 성능을 cost로 ISP(sharpen/contrast) 파라미터 자동 튜닝 → **pedestrian detection +14%** | 파라미터 값 자체가 mode-dependent 최적점을 가짐 → 조도별 RM swap(또는 파라미터 swap)의 근거 |
| Mosleh et al., "Hardware-in-the-Loop End-to-End Optimization of Camera Image Processing Pipelines," *CVPR 2020* (oral) ([open access](https://openaccess.thecvf.com/content_CVPR_2020/html/Mosleh_Hardware-in-the-Loop_End-to-End_Optimization_of_Camera_Image_Processing_Pipelines_CVPR_2020_paper.html)) | 실제 HW ISP를 loop에 넣고 detection loss로 0th-order 최적화: 전문가 수동 튜닝 대비 **+30% mAP**, ISP 근사 기반 방법 대비 +18% | human-IQ 튜닝점과 detection 최적점의 거리가 매우 큼 — "viewing용 기본값을 그대로 쓰면 mAP를 크게 손해본다"는 정량 증거 |
| Diamond et al., "Dirty Pixels: Towards End-to-End Image Processing and Perception," *ACM TOG (SIGGRAPH) 2021* ([Princeton](https://light.princeton.edu/publication/dirty-pixels/), [arXiv:1701.06487](https://arxiv.org/abs/1701.06487)) | raw CFA→label 공동 학습. **Anscombe network** block으로 광량 일반화. 분류 최적 파이프라인은 fine detail을 살리는 대신 **PSNR/SSIM은 오히려 나빠짐** | "vision 최적 = IQ 최적 아님"의 극단적 증거 + VST(Anscombe)를 전단에 두는 설계의 선례 |
| Chen, Chen, Xu, Koltun, "Learning to See in the Dark," *CVPR 2018* ([open access](https://openaccess.thecvf.com/content_cvpr_2018/html/Chen_Learning_to_See_CVPR_2018_paper.html), [arXiv:1805.01934](https://arxiv.org/abs/1805.01934)) | 극저조도 raw를 end-to-end로 처리, 전통 파이프라인+BM3D 대비 압도적 복원. **amplification ratio(gain)를 외부 입력으로 명시** | 극저조도에서 전통 파이프라인의 한계 + "gain을 명시적 mode 파라미터로 취급"하는 본 설계와 동형 |
| Ljungbergh et al., "Raw or Cooked? Object Detection on RAW Images," *SCIA 2023* ([arXiv:2301.08965](https://arxiv.org/abs/2301.08965)) | raw 직입력은 성능 저하; **learnable gamma / learnable Yeo-Johnson 한 개 연산**만 넣으면 RGB baseline 초과, **특히 low-light에서 우위** | "1개의 잘 고른 nonlinearity(tone)"의 가치 — 학습된 1D LUT RM 후보의 직접 근거 |
| Yoshimura et al., "DynamicISP: Dynamically Controlled Image Signal Processor for Image Recognition," *ICCV 2023* ([arXiv:2211.01146](https://arxiv.org/abs/2211.01146)); "Rawgment: Noise-Accounted RAW Augmentation," *CVPR 2023* ([arXiv:2210.16046](https://arxiv.org/pdf/2210.16046)) | 고전 ISP 함수들의 파라미터를 프레임마다 인식 결과로 동적 제어 → 저연산으로 SOTA detection. Rawgment: 노이즈 물리 모델을 반영한 raw augmentation이 다양한 조도 인식을 가능케 함 | **"scene 조건에 따라 ISP를 바꾸면 detection이 오른다"** — 본 프로젝트 DFX per-scene RM swap 논지의 SW-side 최신 증거 |
| Xu et al., "Toward RAW Object Detection: A New Benchmark and a New Model (ROD)," *CVPR 2023* ([open access](https://openaccess.thecvf.com/content/CVPR2023/papers/Xu_Toward_RAW_Object_Detection_A_New_Benchmark_and_a_New_CVPR_2023_paper.pdf)) | 24-bit HDR raw 주야간 주행 dataset; raw detection에는 **image-adaptive한 dynamic range adjustment(tone)가 결정적**이며 detector와 공동 최적화해야 함 | tone 조정이 raw-vision의 1차 병목이라는 재확인 |

**수렴하는 결론**: (i) vision용 ISP에서 결정적 스테이지는 tone(gamma)·demosaic이고, (ii) 최적 파라미터/구조는 조도 조건에 강하게 의존하며, (iii) 조건 적응(per-scene control)이 실측 mAP 이득을 준다. 본 프로젝트는 (iii)을 SW 파라미터 제어가 아닌 **DFX RM swap으로 구현하고 그 area/power 이득을 정량화**하는 위치에 있다.

## B.2 모듈별 분석 — low-light + detection

### B.2.1 Denoising

- 원리: A.3의 인과 사슬에서 노이즈가 주범이므로 denoise는 원리적으로 1순위 개입점.
- 증거(양면):
  - Hong et al. (BMVC 2021): 저조도 detection 실패 원인 = low SNR. 다만 무거운 enhancement/denoise 전처리는 비용 대비 불만족.
  - Diamond et al. (2021): denoise를 인식과 공동 최적화하면 저조도 분류 SOTA — 단, **IQ 기준으론 덜 지운 상태**가 최적. 과도한 denoise는 CNN이 의존하는 high-frequency detail을 제거 → 성능 저하 (Li et al., WaveCNet 계열 분석 [arXiv:2107.13335](https://arxiv.org/pdf/2107.13335); DNN-denoise가 신호검출 task를 해칠 수 있음을 보인 [arXiv:2104.14037](https://arxiv.org/pdf/2104.14037)).
  - Buckler et al. (2017): 통상 조도에서는 denoise 생략 가능 → denoise는 **low-light 전용 모듈**로 두는 것이 자원 관점에서 정당 — 정확히 DFX RM에 맞는 프로파일.
- HW 관점: BM3D류(비지역 탐색·집계)는 FPGA streaming ISP에 부적합. 실용 후보는 3x3/5x5 Gaussian·bilateral 근사, VST-도메인 soft threshold — line buffer 2–4줄, DSP 소수.
- 판단: **binning과 결합한 경량 spatial denoise**(예: binning 후 3x3 edge-preserving smoothing)가 "SNR 개선 대비 detail 손실"의 균형점. 강한 단독 denoise RM보다 우선순위 높음.

### B.2.2 Pixel binning

- 원리: 2x2 합산 시 신호 4배. Read-noise-limited(극저조도)에서는 노이즈가 √4=2배(독립 read noise 합) 또는 1회 read로 감소 → **SNR +6 dB** (digital/voltage 합산, read-limited). Shot-noise-limited에서는 +3 dB(√4/2). 근거: Teledyne binning 해설 ([링크](https://www.teledynevisionsolutions.com/learn/learning-center/imaging-fundamentals/binning/)), Jin & Hirakawa, "Analysis and processing of pixel binning for color image sensor," *EURASIP JASP* 2012 ([링크](https://asp-eurasipjournals.springeropen.com/articles/10.1186/1687-6180-2012-125)) — binning은 "잉여 공간해상도를 SNR로 교환"하는 연산이며 low-light에서 가장 유효.
- 트레이드오프 정량: 해상도 1/2 (H/2 x W/2). YOLOv8n의 소형 객체(COCO 정의 <32² px)는 이미 최약 지점이고, Rodríguez-Rodríguez et al. (2024)은 **작은 객체가 열화 요인 이전에도 검출이 취약**함을 보였다 — binning은 객체의 픽셀 면적을 1/4로 줄이므로 32–64 px 객체를 small-object 구간으로 밀어 넣는다. 반면 ExDark류 저조도 장면에서 노이즈로 인한 mAP 손실이 해상도로 인한 손실을 능가하는 조도 구간이 존재하며(Sensors 2024의 "noise > brightness" + DSFD 15.3% 붕괴), binning은 그 구간에서 순이득.
- 판단: **binning의 손익분기점은 (조도, 객체 크기 분포)의 함수**다. 본 프로젝트에서 ExDark_5000_raw로 "binning on/off × 객체 크기별 AP" 분해를 측정하는 것 자체가 기여가 된다. Bayer-도메인 binning은 same-color 2x2 집계여야 CFA semantics가 보존됨(Jin & Hirakawa 2012) — `RESEARCH.md` §4.1의 channel grouping 명시 요구와 일치.

### B.2.3 Tone mapping / gamma

- 원리 1 (dynamic range 재배치): 압축된 저부 histogram을 detector가 학습한 입력 분포 범위로 확장.
- 원리 2 (variance stabilization): γ≈0.5(제곱근)형 곡선은 Poisson 노이즈의 근사적 VST — Anscombe 변환 2√(x+3/8)이 정확히 제곱근형이다. 즉 gamma는 "보기 좋게"가 아니라 **노이즈 분산을 코드 공간에서 균일화**하는 원리적 연산이다 (Anscombe 1948; Mäkitalo & Foi, *TIP* 2011/2013, [invansc](https://webpages.tuni.fi/foi/invansc/); Diamond et al. 2021의 Anscombe network).
- 증거: ISP4ML — tone mapper가 최대 기여 stage. ROD — raw detection의 병목은 dynamic range adjustment. Ljungbergh — learnable gamma/Yeo-Johnson 단일 연산으로 RGB 초과, low-light에서 특히. Buckler — gamma는 생략 불가능한 2개 stage 중 하나.
- Global vs local: global LUT는 HW 비용 ~0 (BRAM 1개). Local tone(CLAHE)은 저대비·불균일 조명에서 추가 이득 — YOLOX + CLAHE에서 **+1.13%p mAP** (Wang et al., *J. Comput. Des. Eng.* 10(3), 2023, [링크](https://academic.oup.com/jcde/article/10/3/1158/7177527)); VisionISP의 VLTM(global curve + local detail boost)도 같은 구조. 단 CLAHE는 tile histogram 축적이 필요해 1-frame latency 또는 이전 frame 통계 재사용이 필요.
- 판단: 본 프로젝트의 gamma LUT RM은 문헌상 최고 효율의 개입점이다. 값 선택 시 "γ=4.0 같은 강한 lift"보다 **제곱근형(VST-정합) 곡선 + 상부 soft-knee**가 노이즈 증폭 관점에서 원리적이다.

### B.2.4 Exposure/digital gain의 배치

- 원리: gain은 SNR을 바꾸지 못한다(신호·노이즈 동배율). 유일한 실익은 (1) 후단 양자화/클리핑 전에 코드 공간을 확보, (2) detector 입력 분포 정합. 따라서 **가능한 한 raw 상류(비트폭이 넓은 곳)에서, demosaic·양자화 이전에** 적용해야 quantization 손실을 최소화한다 — Chen et al. (2018)도 amplification을 raw 직후에 명시 배치. `RESEARCH.md` §4.2의 "RAW precision이 줄기 전에 RM이 동작해야 한다"는 지적과 정확히 일치하는 문헌 근거.
- WB gain과의 상호작용: gain→WB 순서든 WB→gain이든 곱셈이라 수학적으론 교환 가능하지만, 고정소수점에서는 곱셈 횟수·클리핑 지점이 달라진다. 채널별 노이즈 증폭(A.2.4)은 WB gain 몫.

### B.2.5 Demosaic (노이즈 하에서)

- 원리: demosaic 보간은 노이즈를 채널 간·공간적으로 상관시켜, 이후의 denoise를 어렵게 만들고(노이즈가 더 이상 백색이 아님) zipper/false color artifact를 노이즈가 증폭한다.
- 증거: Gharbi, Chaurasia, Paris, Durand, "Deep Joint Demosaicking and Denoising," *SIGGRAPH Asia 2016* ([demosaicnet](https://github.com/mgharbi/demosaicnet)) — demosaic와 denoise의 공동 처리가 순차 처리 대비 artifact(moiré, noise-induced)를 크게 줄임. Buckler (2017)는 vision 한정으로는 demosaic를 subsample로 대체 가능함을 보임 — **binning은 사실상 "저해상도 demosaic 대체물"** 로 기능한다는 해석이 가능(2x2 Bayer quad → 1 RGB 픽셀).
- 판단: baseline core의 demosaic는 고정 유지(§3.3 discipline)하되, low-light RM의 binning이 demosaic 부담을 구조적으로 줄여준다는 점을 논문 서술에 활용 가능.

### B.2.6 AWB / CCM — detector는 색 충실도에 민감한가

- 증거: Buckler (2017) — gamut mapping/color 변환 stage는 CNN vision 성능에 결정적이지 않음. ISP4ML도 tone 대비 color 스테이지 기여는 소폭. CNN은 학습 중 color jitter augmentation으로 색 변형에 강인화되는 것이 표준 관행이라 절대적 색 충실도 요구가 낮다.
- 단, 상한이 있다: WB가 완전히 붕괴되면(심한 색편향) domain shift로 작동. 또한 CCM 계수가 클수록 노이즈 증폭(A.2.4) — low-light에서는 오히려 **CCM을 약화(desaturate)하는 것이 chroma noise 억제 수단**이 된다. DynamicISP류가 저조도에서 채도 관련 파라미터를 낮추는 것과 일관.
- 판단: baseline core의 AWB/CCM은 고정·저비용 구현으로 충분. "low-light mode에서 CCM 강도 축소"는 저비용 고근거 개선이지만, 이는 RM이 아닌 baseline 파라미터라 본 프로젝트 아키텍처에서는 CCM strength를 RM metadata로 넘기는 형태가 자연스럽다.

### B.2.7 Contrast/histogram equalization 계열 (CLAHE, retinex, Zero-DCE)

- Zero-DCE — Guo et al., *CVPR 2020* ([open access](https://openaccess.thecvf.com/content_CVPR_2020/html/Guo_Zero-Reference_Deep_Curve_Estimation_for_Low-Light_Image_Enhancement_CVPR_2020_paper.html)): 픽셀별 고차 curve 추정으로 DARK FACE face detection 개선을 시연. 경량(DCE-Net)이라 **SW-side 비교 baseline**으로 적합 — 본 프로젝트에서 "HW tone RM vs SW Zero-DCE 전처리"의 mAP/latency 비교 축을 제공.
- MSRCR/retinex 계열: 조명-반사 분해 기반 enhancement의 고전. 단 A.3.2의 empirical study (arXiv:2409.14461)들이 보이듯 **LLIE 계열의 detection 이득은 비일관** — 노이즈를 함께 증폭하기 때문. 문헌은 "denoise 없는 밝기/대비 enhancement 단독"에 회의적.
- CLAHE: B.2.3 참조 — clip limit이 노이즈 증폭을 제한하는 내장 안전장치라는 점에서 retinex류보다 low-light 친화적이며, detection 개선의 실측 보고 다수.

### B.2.8 Variance-Stabilizing Transform (Anscombe)

- Anscombe (1948): f(x) = 2√(x + 3/8)이 Poisson을 근사 단위분산 Gaussian으로 변환. Poisson-Gaussian용 Generalized Anscombe Transform(GAT)과 최적 역변환은 Mäkitalo & Foi (*TIP* 2011; *TIP* 2013, [링크](https://webpages.tuni.fi/foi/invansc/)).
- 의의: "VST → Gaussian denoiser → exact unbiased inverse"가 저광량 처리의 원리적 표준 절차이며, **HW에서는 VST가 1D LUT 하나**라는 점이 핵심이다. gamma LUT slot에 GAT형 곡선을 넣으면 tone과 VST를 동시에 얻는다 — Diamond et al. (2021)이 Anscombe block을 인식 네트워크 전단에 두어 광량 일반화를 달성한 것이 직접 선례.

---

# Part C — 본 프로젝트 매핑

## C.1 기존 설계의 문헌 정합성

| 설계 요소 | 문헌 판정 |
|---|---|
| tone(gain+gamma)을 RM으로 분리, baseline은 BLC+WB+demosaic+CCM | 정합. 결정적 stage(tone)만 mode-specific으로 특화 (Buckler; ISP4ML; ROD) |
| RM_LOW_LIGHT_TONE = 2x2 binning + gain 2.0 + gamma 2.0 | 정합. binning +6dB(read-limited), gamma 2.0(=√)은 근사 Anscombe VST — 우연히도 원리적으로 좋은 값 |
| binning의 H/2 x W/2 출력 (Policy A) | 조건부 정합. small-object AP 손실 리스크(Sensors 2024) → 객체 크기별 AP 분해 측정 필수 |
| per-scene RM swap (checker + hysteresis) | 정합. DynamicISP가 per-frame ISP 제어로 detection SOTA — 본 프로젝트는 이를 area-efficient한 DFX로 구현하는 차별점 |
| 평가: COCO(normal)/ExDark(dark) pseudo-RAW + YOLOv8n mAP | 정합. 단 pseudo-RAW의 노이즈 통계가 실제 Poisson-Gaussian과 다르면 (Rawgment의 지적처럼) 결론이 약해짐 → Foi 모델 기반 노이즈 합성을 pseudo-RAW 생성에 반영할 것을 권고 |

## C.2 논문 서술에 쓸 수 있는 논증 골격

1. Low-light의 본질은 SNR (Part A) → 2. 사람용 enhancement는 detection에 비일관 (A.3.2) → 3. vision-ISP에서 tone이 최중요 stage (B.1) → 4. 최적 tone/전처리는 조도-의존 (Mosleh, DynamicISP) → 5. 조도별 tone 구현을 상시 병렬 탑재하면 area 낭비, 시분할(DFX)하면 mutually-exclusive라는 성질과 정확히 부합 → 6. 따라서 tone RM slot + DFX가 자연스러운 설계점이며, 남는 자원으로 3rd/4th RM(아래)까지 slot에 수용 가능.

## C.3 3rd/4th RM 후보 순위

점수: 기대 detection gain (low-light) × FPGA feasibility. 근거 문헌 병기. line buffer는 1080p 기준 1줄 ≈ 1920px × 12–24 bit ≈ BRAM18K 1–3개.

| 순위 | RM 후보 | 기대 gain (근거) | FPGA 비용 | 판정 |
|---|---|---|---|---|
| 1 | **RM_TONE_LUT_PARAM** — 학습/최적화된 parametric global tone (1D LUT, GAT/Yeo-Johnson형, detection loss로 offline 최적화) | 높음: learnable gamma 단일 연산으로 low-light detection 개선 (Ljungbergh 2023); tone이 최대 기여 stage (ISP4ML); HW-in-the-loop 튜닝 +30% mAP (Mosleh 2020) | 극소: BRAM LUT 1개, line buffer 0, DSP 0. partial bitstream 최소 → reconfig latency 최소 | **최우선.** 기존 gamma LUT 구조 재사용, "학습된 LUT vs 고정 γ" ablation이 저비용 고임팩트 |
| 2 | **RM_LL_BIN_DN** — 기존 low-light RM + 경량 edge-preserving spatial denoise (binning 후 3x3–5x5, 또는 VST-도메인 threshold) | 높음: 저조도 실패 원인 = low SNR (Hong 2021); noise > brightness (Sensors 2024); 과도 denoise 회피 조건부 (B.2.1) | 소–중: line buffer 2–4줄 (binning 후 W/2라 절반), DSP 수 개–십수 개 | **2순위.** binning과 시너지(반폭 line buffer). 4th RM으로 RM_LOW_LIGHT_TONE의 상위 변형 |
| 3 | **RM_TONE_CLAHE** — CLAHE-계열 local tone (tile histogram, 이전 frame 통계 재사용으로 streaming화) | 중–높: CLAHE로 YOLOX +1.13%p (Wang 2023); local tone = VisionISP VLTM 구조; 저대비 보상 | 중: tile histogram용 BRAM (예: 8x8 tile × 256 bin), 보간 DSP 소수, frame-lag 통계 시 line buffer 불필요 | 3순위. 이득 실측치가 1–4%p 수준으로 존재하나 통계 경로 검증 부담 |
| 4 | **RM_CHROMA_DN** — chroma-축 denoise/desaturation (CCM 후 또는 CCM 계수 축소 연동) | 중: WB/CCM 노이즈 증폭은 원리적으로 명확 (A.2.4)하나 detector의 색 민감도가 낮아 (Buckler) 이득 상한이 제한적 | 중: RGB→YCbCr 변환 + chroma LPF, line buffer 2줄 | 4순위. "CCM 강도 축소" 파라미터화가 더 싼 대체재 |
| 5 | **RM_TEMPORAL_DN** — temporal/recursive denoise (IIR frame blend) | 잠재적 최대: 정적 장면에서 N-frame 평균 = +10log₁₀N dB | 대: frame buffer(DDR 왕복) 대역폭, motion 대응 없으면 ghosting → blur가 detection 저해 | 후순위. Policy A(가변 shape)와의 결합 복잡도도 큼 |

권고: **3rd RM = RM_TONE_LUT_PARAM** (기존 slot 인터페이스 그대로, bitstream 최소, Ljungbergh/Mosleh 근거 직결), **4th RM = RM_LL_BIN_DN** (기존 low-light RM의 강화 변형으로 ablation 축 형성: binning-only vs binning+denoise). CLAHE는 5th 또는 SW(Zero-DCE)와의 비교 실험으로 대체.

---

# References

전체 서지(33편, 4개 그룹 — 물리/노이즈 모델, low-light detection 벤치마크, ISP-for-vision, 모듈별 —
링크 포함)는 `references-index-2026-07-07.md` § C 참고.
