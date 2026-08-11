# DFXISP 이론 배경 및 근거 자료

> 작성일: 2026-08-11
>
> 범위: 저조도 RAW 영상, 센서 노이즈·캘리브레이션, ISP, 장면 판정, FPGA DFX, AI/CV 검출
>
> 목적: DFXISP의 가설·수식·구현 선택·실험 지표를 논문과 공식 문서로 뒷받침하기 위한 출발점

## 0. 이 연구에 적용되는 핵심 논리

- 저조도의 본질은 단순히 픽셀 값이 작은 것이 아니라 photon shot noise와 read noise 때문에 **SNR이 낮아지는 것**이다. RAW 센서 노이즈는 보통 신호 의존 Poisson 성분과 신호 비의존 Gaussian 성분을 합친 `Var[z|y] = a y + b`로 근사한다.
- 2×2 binning은 공간 해상도를 신호 통계의 안정성과 교환한다. 네 픽셀의 독립 노이즈를 합치면 shot-noise-limited 영역의 SNR은 이상적으로 2배(+6 dB, 합산 출력 기준)가 되지만, 출력 크기 축소로 작은 객체 검출에는 손해가 날 수 있다. 실제 구현 방식(전하/아날로그/디지털 binning, 합/평균)에 따라 read-noise 이득과 출력 스케일은 달라진다.
- BLC, AWB, CCM, gain, gamma는 서로 독립적인 장식 단계가 아니다. BLC 오차는 후속 gain·WB에 의해 확대되고, gamma는 비선형이므로 BLC/WB/CCM 같은 선형 보정 뒤에 두는 것이 해석과 캘리브레이션에 유리하다.
- 사람에게 보기 좋은 영상과 검출기에 좋은 영상은 같지 않을 수 있다. 따라서 PSNR/SSIM만으로 ISP를 선택하지 않고, 동일 detector·동일 split에서 mAP/AP50/AP-small과 checker 오류, 전환 횟수, FPGA 자원·전력·지연을 함께 비교해야 한다.
- DFXISP에서 DFX는 정확도를 직접 만드는 영상 알고리즘이 아니라, 조도별로 다른 전체 ISP RM을 상호배타적으로 적재해 always-on 병렬 구현보다 자원을 줄이는 **구현 수단**이다.

## 1. 저조도 영상과 센서 노이즈

- [Foi et al., “Practical Poissonian-Gaussian Noise Modeling and Fitting for Single-Image Raw-Data,” IEEE TIP, 2008](https://doi.org/10.1109/TIP.2008.2001399) — RAW 관측 노이즈를 신호 의존 Poisson 성분과 정상 Gaussian 성분으로 모델링하고, clipping까지 포함한다. 본 연구의 `sigma²(y)=a·y+b`, 합성 노이즈, SNR 기반 저조도 해석의 가장 직접적인 근거다.
- [EMVA Standard 1288, Release 4.0 Linear](https://www.emva.org/wp-content/uploads/EMVA1288Linear_4.0Release.pdf) — 산업용 카메라의 sensitivity, temporal dark noise, saturation, dynamic range, SNR 및 photon-transfer 측정을 표준화한다. 센서 gain과 noise parameter를 임의 추정하지 않고 dark/flat 측정으로 캘리브레이션할 때 사용한다.
- [EMVA 1288 공식 다운로드 페이지](https://www.emva.org/standards-technology/emva-1288/emva-standard-1288-downloads-2/) — Linear/General 4.0 규격과 이전 버전을 제공한다. 비선형·내부 전처리 카메라는 General 모듈 적용 여부를 판단해야 한다.
- [Gnanasambandam & Chan, “Exposure-Referred SNR for Digital Image Sensors”](https://arxiv.org/abs/2112.05817) — 디지털 출력 값만이 아니라 exposure 기준으로 SNR과 dynamic range를 비교하는 관점을 설명한다. 서로 다른 gain/ISP 설정의 출력 밝기만 보고 SNR 향상을 오판하지 않게 해준다.
- [Chen et al., “Learning to See in the Dark,” CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/html/Chen_Learning_to_See_CVPR_2018_paper.html) — 극저조도 RAW를 직접 처리하고 amplification ratio를 명시적으로 사용한다. 저조도에서는 sRGB 후처리보다 RAW 단계의 노이즈·gain 처리가 중요하다는 실증 근거다.
- [Hong et al., “Crafting Object Detection in Very Low Light,” BMVC 2021](https://kxwei.net/publication/bmvc21_lod/) — 매우 낮은 SNR의 RAW/RGB 객체 검출을 다루며 LOD 데이터셋을 제공한다. 본 연구의 저조도 조건 데이터와 object-detection 목적을 직접 연결한다.
- [Loh & Chan, “Getting to Know Low-light Images with the Exclusively Dark Dataset,” CVIU 2019](https://github.com/cs-chan/Exclusively-Dark-Image-Dataset) — 다양한 저조도 유형의 ExDark 데이터셋과 저조도에서의 feature 열화를 제시한다. 밝은 영상에서 학습한 표현의 domain shift를 설명하는 배경 자료다.
- [Rodríguez-Rodríguez et al., “The Impact of Noise and Brightness on Object Detection Methods,” Sensors, 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10856852/) — brightness 감소와 여러 noise를 분리해 detector 성능을 평가한다. 단순 밝기보다 노이즈가 더 큰 손상을 줄 수 있고 작은 객체가 특히 취약하다는 근거로, binning의 SNR 이득과 해상도 비용을 함께 보게 한다.

## 2. SNR, sigma, gain과 photon-transfer calibration

- 기본 정의: `SNR = μ_signal / σ_noise`, `SNR_dB = 20 log10(SNR)`. 독립 noise source라면 표준편차가 아니라 **분산**이 더해져 `σ_total² = Σσ_i²`가 된다.
- Poisson shot noise만 있을 때 전자 수를 `N_e`라 하면 `σ_shot=√N_e`, `SNR=√N_e`. read noise와 dark noise를 포함하면 `SNR ≈ N_e / √(N_e + σ_read² + σ_dark²)`로 쓸 수 있다.
- 디지털 gain `g`만 곱하면 평균과 sigma가 모두 `g`배가 되어 이상적인 연속값 SNR은 바뀌지 않는다. 다만 ADC 전단의 analog gain은 read/quantization noise의 상대적 비중을 바꿀 수 있고, 후단 digital gain은 quantization·clipping과 입력 분포에 영향을 준다.
- `snr sigma`는 별도 표준 알고리즘명이라기보다 보통 평균 대비 noise 표준편차, 또는 threshold를 `μ ± kσ`로 두는 규칙을 뜻한다. 본 연구에서는 문맥을 명확히 해 `SNR=μ/σ`, noise sigma `σ(y)=√(ay+b)`, threshold margin `kσ` 중 무엇인지 표기해야 한다.
- [EMVA 1288 Release 4.0 Linear](https://www.emva.org/wp-content/uploads/EMVA1288Linear_4.0Release.pdf) — dark frame과 균일 flat-field series로 conversion gain, temporal dark noise, SNR curve를 구하는 공식 절차다.
- [Teledyne Vision Solutions, Camera Gain](https://www.teledynevisionsolutions.com/en-gb/learn/learning-center/imaging-fundamentals/camera-gain/) — gain의 의미와 bias/dark 및 두 장의 균일 flat을 이용한 실무 측정 절차를 설명한다. 논문 이론을 실제 센서 캘리브레이션으로 옮길 때 유용하다.
- [ESO VIRCAM Quality Control: Gain](https://www.eso.org/observing/dfo/quality/VIRCAM/qc/qc_VC_gain.html) — 두 flat의 차와 dark frame으로 photon noise, read noise, `e⁻/ADU` gain을 추정하는 실제 관측 장비 사례다.
- [Brown, Cai & DasGupta, “Interval Estimation for a Binomial Proportion,” Statistical Science, 2001](https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.full) — dark-pixel ratio처럼 `K/N`으로 계산한 비율의 불확실성에 Wald interval 대신 Wilson/Jeffreys interval을 쓰는 근거다.

## 3. Poisson–Gaussian noise model과 분산 안정화

- 모델: 전자 영역에서 `x ~ Poisson(λ)`, read noise `n ~ N(0,σ_r²)`, digital output을 `z = g·x + n + offset`으로 둘 수 있다. 정규화된 RAW에서는 흔히 `z = y + √(a y+b)·ξ`, `ξ~N(0,1)`로 쓴다.
- parameter `a`는 shot-noise/gain 성분, `b`는 read·quantization noise floor를 나타낸다. BLC 이후 음수 clamp와 sensor saturation은 분포를 잘라내므로 noise fitting에서 clipping을 무시하면 bias가 생긴다.
- [Foi et al. 2008 저자 공개 PDF](https://webpages.tuni.fi/foi/papers/Foi-PoissonianGaussianClippedRaw-2007-IEEE_TIP.pdf) — 위 모델의 식, parameter fitting, clipping 처리를 자세히 볼 수 있는 공개본이다.
- [Mäkitalo & Foi, Optimal Inversion of the Anscombe Transformation](https://webpages.tuni.fi/foi/invansc/) — Poisson 및 Poisson–Gaussian noise를 거의 일정 분산 Gaussian으로 바꾸는 Anscombe/GAT와 역변환 자료다. 제곱근형 gamma/tone을 단순 밝기 보정이 아니라 variance-stabilizing transform 후보로 해석하는 근거다.
- [Rawgment: Noise-Accounted RAW Augmentation, CVPR 2023](https://arxiv.org/abs/2210.16046) — 카메라 noise formation을 반영한 RAW augmentation이 다양한 조도에서의 인식 일반화에 유효함을 보인다. 합성 저조도 실험에는 단순 RGB darkening보다 이 접근이 적합하다.

## 4. Binning

- [Teledyne Vision Solutions, Binning](https://www.teledynevisionsolutions.com/learn/learning-center/imaging-fundamentals/binning/) — pixel binning이 sensitivity/SNR과 spatial resolution을 교환하는 원리, sensor/vertical/horizontal binning의 차이를 설명한다.
- [Jin & Hirakawa, “Analysis and Processing of Pixel Binning for Color Image Sensor,” EURASIP JASP, 2012](https://asp-eurasipjournals.springeropen.com/articles/10.1186/1687-6180-2012-125) — CFA color sensor의 binning 구조, aliasing과 색 재구성 문제를 분석한다. Bayer 배열에서 단순 인접 평균이 아니라 color/CFA semantics를 보존해야 하는 근거다.
- DFXISP 적용 규칙: 2×2 Bayer quad를 하나의 RGB 위치로 만드는 binning-demosaic는 출력 `H/2×W/2`와 small-object pixel 면적 1/4 감소를 명시해야 한다. 같은 크기로 upsample한 결과를 원본 해상도 처리와 동일하다고 간주하면 안 된다.
- 검증 규칙: bright/dark 조건 각각에서 전체 AP뿐 아니라 `AP_small`, `AP_medium`, `AP_large`, 출력 크기, 처리량, noise sigma를 함께 보고한다. binning의 이득을 gain/BLC 변화와 분리하는 ablation이 필요하다.

## 5. ISP pipeline 전체 구조

- [AMD Vitis Vision, Image Sensor Processing Pipeline](https://docs.amd.com/r/en-US/Vitis_Libraries/vision/overview.html_3_8) — Bayer 입력에서 BLC, bad-pixel correction, gain control, demosaicing, AWB, CCM, gamma 등 FPGA용 ISP stage와 dataflow를 공식적으로 정리한다. DFXISP HLS pipeline의 가장 가까운 vendor reference다.
- [MathWorks, End-to-End Digital Camera Processing Pipeline](https://www.mathworks.com/help/images/end-to-end-implementation-of-digital-camera-processing-pipeline.html) — RAW metadata를 사용해 linearization, BLC, white balance, demosaic, color conversion을 수행하는 재현 가능한 예제다. 각 stage의 입력 공간과 순서를 확인하기 좋다.
- [Buckler et al., “Reconfiguring the Imaging Pipeline for Computer Vision,” ICCV 2017](https://openaccess.thecvf.com/content_iccv_2017/html/Buckler_Reconfiguring_the_Imaging_ICCV_2017_paper.html) — ISP stage ablation을 통해 사람용 image quality와 vision workload의 필요 stage가 다름을 보인다. DFXISP가 vision 성능을 기준으로 pipeline을 재구성한다는 핵심 근거다.
- [Hansen et al., “ISP4ML: The Role of Image Signal Processing in Efficient Deep Learning Vision Systems”](https://arxiv.org/abs/1911.07954) — configurable ISP와 ImageNet 실험으로 ISP 및 tone mapping이 ML 정확도에 미치는 영향을 분석한다.
- [Wu et al., “VisionISP: Repurposing the Image Signal Processor for Computer Vision Applications”](https://arxiv.org/abs/1911.05931) — bit depth, scale, global/local tone을 machine vision 목적에 맞춰 학습한다. ISP를 사람용 rendering이 아니라 AI 입력 변환기로 보는 직접적인 선행연구다.
- [Mosleh et al., “Hardware-in-the-Loop End-to-End Optimization of Camera Image Processing Pipelines,” CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/html/Mosleh_Hardware-in-the-Loop_End-to-End_Optimization_of_Camera_Image_Processing_Pipelines_CVPR_2020_paper.html) — 실제 ISP hardware를 loop에 넣고 downstream vision loss로 parameter를 최적화한다. ISP 설정을 mAP로 조정해야 한다는 실증 근거다.

## 6. BLC (Black Level Correction)와 dark calibration

- BLC 기본식: CFA channel별 `x_blc = max(x_raw - b_c, 0)`. `b_c`는 무광 상태에서도 생기는 sensor/readout offset이며 R/Gr/Gb/B별로 다를 수 있다.
- [MathWorks ISP 예제의 Black-Level Correction 절](https://www.mathworks.com/help/images/end-to-end-implementation-of-digital-camera-processing-pipeline.html) — masked pixel 또는 RAW metadata의 channel별 black level을 빼고 음수를 clamp하는 구현을 설명한다.
- [darktable, Raw Black/White Point](https://docs.darktable.org/usermanual/development/en/module-reference/processing-modules/raw-black-white-point/) — Bayer 4채널별 camera-specific black level과 white point의 역할을 설명하는 실무 자료다.
- DFXISP 적용 규칙: black level은 가능하면 동일 sensor·gain/ISO·노출·온도에서 lens cap 또는 optical-black frame 여러 장의 robust mean/median으로 추정한다. `BLC → gain/WB` 순서이므로 BLC 오차 `Δb`도 후속 배율만큼 증폭된다.
- dark frame의 평균은 fixed offset/dark-current pattern 보정에 쓰고, frame 간 표준편차는 temporal read/dark noise 측정에 쓴다. 한 장의 dark image에 보이는 값의 분산을 전부 temporal noise로 간주하면 fixed-pattern noise와 혼동한다.

## 7. Demosaicing

- [Malvar, He & Cutler, “High-Quality Linear Interpolation for Demosaicing of Bayer-Patterned Color Images,” ICASSP 2004](https://www.ipol.im/pub/art/2011/g_mhcd/revisions/2011-08-14/g_mhcd.htm) — bilinear interpolation에 cross-channel correction을 더한 고전적 선형 demosaic와 공개 설명/구현을 제공한다. bilinear baseline보다 정확하지만 여전히 규칙 기반이고 HW 구현 가능하다.
- [Gharbi et al., “Deep Joint Demosaicking and Denoising,” SIGGRAPH Asia 2016](https://github.com/mgharbi/demosaicnet) — 저조도에서는 noise가 demosaic artifact와 결합하므로 두 문제를 독립 stage로만 다루기 어렵다는 근거다.
- [AMD Vitis Vision ISP](https://docs.amd.com/r/en-US/Vitis_Libraries/vision/overview.html_3_8) — RGGB/BGGR/GBRG/GRBG Bayer pattern을 RGB로 복원하는 FPGA-ready demosaic reference다.
- 구현 규칙: dataset RAW의 CFA pattern, visible crop의 시작 좌표, binning 뒤 pattern을 반드시 기록한다. 한 픽셀 offset만 생겨도 R/B가 뒤바뀌므로 색 성능과 detector 성능 모두 무효가 될 수 있다.

## 8. AWB (Auto White Balance)

- AWB는 illuminant 때문에 생긴 channel gain 차이를 보정하며 보통 linear RAW/RGB에서 diagonal gain `diag(g_R,g_G,g_B)`으로 적용한다. Gray-world는 장면 평균색이 무채색이라는 가정이므로 단색 장면에서는 실패할 수 있다.
- [Gijsenij, Gevers & van de Weijer, “Computational Color Constancy: Survey and Experiments,” IEEE TIP 2011](https://doi.org/10.1109/TIP.2011.2118224) — Gray-world, White-patch, Shades-of-Gray 등 illuminant estimation 방법과 평가를 체계적으로 비교한 color constancy survey다.
- [AMD Vitis Vision ISP](https://docs.amd.com/r/en-US/Vitis_Libraries/vision/overview.html_3_8) — histogram/gray-world 계열 AWB를 FPGA pipeline에서 사용하는 공식 reference다.
- 적용 규칙: AWB gain은 BLC가 끝난 linear 값에서 추정·적용하고, saturation 및 극저신호 픽셀은 통계에서 제외한다. 저조도에서는 channel별 noise floor가 달라 평균 기반 gain이 불안정해질 수 있으므로 gain cap과 temporal smoothing을 검토한다.

## 9. CCM (Color Correction Matrix)

- CCM은 sensor RGB를 목표 color space로 보내는 보통 `3×3` 선형 변환 `rgb_out=M·rgb_sensor`다. AWB가 illuminant의 channel scale을 다루는 반면 CCM은 sensor spectral sensitivity와 목표 primaries 간 색 혼합을 보정한다.
- [Finlayson & Drew, “Constrained Least-Squares Regression in Color Spaces,” Journal of Electronic Imaging, 1997](https://doi.org/10.1117/12.271585) — camera color correction matrix를 least-squares로 추정하는 고전적 수학 근거다.
- [Imatest, Color Correction Matrix](https://www.imatest.com/docs/colormatrix/) — ColorChecker patch, linear RAW, reference color를 이용한 CCM optimization과 ΔE 평가를 실무적으로 설명한다.
- 적용 규칙: gamma-compressed 값이 아니라 BLC/AWB 후의 **linear** 값에서 CCM을 fitting/apply한다. calibration illuminant, chart, objective(least squares 또는 ΔE), matrix normalization을 기록해야 재현 가능하다.

## 10. Gain과 gamma/tone mapping

- gain: `y=clip(gx)`는 신호를 밝히지만 이미 존재하는 shot/read noise도 함께 키운다. 따라서 “gain이 SNR을 개선했다”는 주장은 analog/quantization 조건 또는 clipping 변화 없이 출력 영상만으로 해서는 안 된다.
- gamma: power-law의 한 표현은 `y=x^(1/γ)`이다. 문헌·코드마다 `γ`를 지수 자체로 쓰기도 하므로 “gamma 2.2”만 적지 말고 실제 exponent나 LUT를 함께 기록한다.
- [ITU-R BT.709](https://www.itu.int/rec/R-REC-BT.709/en) — HDTV RGB primaries, luma와 opto-electronic transfer 특성의 공식 표준이다. `Y′=0.2126R′+0.7152G′+0.0722B′`는 비선형 R′G′B′의 luma이고, linear luminance와 혼용하지 않아야 한다.
- [IEC 61966-2-1 / sRGB background by ICC](https://www.color.org/chardata/rgb/srgb.xalter) — sRGB transfer function과 color space 정의의 참고 자료다. 단순 `x^(1/2.2)`는 sRGB의 저휘도 선형 구간을 정확히 재현하지 않는다.
- [Ljungbergh et al., “Raw or Cooked? Object Detection on RAW Images,” SCIA 2023](https://arxiv.org/abs/2301.08965) — RAW detector 앞에 learnable gamma/Yeo–Johnson 변환만 추가해 dynamic range mismatch를 크게 줄일 수 있음을 보인다.
- [Xu et al., “Toward RAW Object Detection: A New Benchmark and a New Model,” CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/papers/Xu_Toward_RAW_Object_Detection_A_New_Benchmark_and_a_New_CVPR_2023_paper.pdf) — 주야간 HDR RAW 검출에서 image-adaptive dynamic-range adjustment가 중요함을 보인다.

## 11. Dark pixel count, threshold와 장면 checker

- DFXISP checker의 핵심 통계는 `K = Σ 1[Y_i < T_dark]`, `dark_ratio=K/N`이다. 고정 threshold 아래인지 여부는 Bernoulli 변수이므로, 독립 표본이라는 근사 아래 `Var(dark_ratio)=p(1-p)/N`이다.
- [Otsu, “A Threshold Selection Method from Gray-Level Histograms,” IEEE TSMC, 1979](https://doi.org/10.1109/TSMC.1979.4310076) — 두 class의 between-class variance를 최대화하는 자동 intensity threshold의 고전적 근거다. 고정 `dark16`의 비교 baseline으로 쓸 수 있지만, 장면 histogram이 두 봉우리가 아닐 때는 실패할 수 있다.
- [ITU-R BT.709](https://www.itu.int/rec/R-REC-BT.709/en) — RGB 기반 밝기 통계를 만들 때 표준 luma coefficient의 출처다. 현재 checker의 저비용 `Y=(R+2G+B)/4`는 BT.709 정확식이 아니라 FPGA용 근사임을 명시해야 한다.
- [Brown, Cai & DasGupta 2001](https://doi.org/10.1214/ss/1009213286) — dark_ratio의 frame/sample 불확실성을 Wilson interval로 제시할 때의 통계 근거다.
- 적용 규칙: `T_dark`는 black level이 제거된 linear RAW/RGB 기준인지, raw12 code인지, gamma 후 값인지 반드시 명시한다. sensor gain/black level이 바뀌면 같은 숫자 threshold는 같은 광량을 뜻하지 않는다.
- 실험 규칙: checker는 accuracy 하나보다 confusion matrix, balanced accuracy, ROC/Youden's J, 조건별 false enter/false exit, mode-switch 횟수를 보고한다. 인접 픽셀은 상관되므로 픽셀 수가 매우 커도 이미지·장면 단위 재표본화가 더 정직한 신뢰구간을 준다.

## 12. Hysteresis (요청의 `hystereisis` 교정)와 temporal switching

- Schmitt hysteresis는 진입 threshold와 이탈 threshold를 다르게 두어 경계 근처 noise로 인한 mode thrashing을 막는다. DFXISP의 `enter=64%`, `exit=60%`는 state를 가진 dual-threshold 정책이다.
- [Schmitt, “A Thermionic Trigger,” Journal of Scientific Instruments, 1938](https://doi.org/10.1088/0950-7671/15/1/305) — 두 threshold와 positive feedback을 사용하는 Schmitt trigger의 원전이다. 영상 checker에서는 전압 대신 dark_ratio에 같은 상태기계 원리를 적용한다.
- [Page, “Continuous Inspection Schemes,” Biometrika, 1954](https://doi.org/10.1093/biomet/41.1-2.100) — 누적 변화 감지(CUSUM)의 고전적 근거다. 단순 N-frame dwell보다 지속적인 조도 변화에 민감한 후속 checker 후보가 될 수 있다.
- 구현 규칙: `(현재 mode, enter/exit 판정, minimum dwell, PR busy/ack)`를 하나의 명시적 FSM으로 검증한다. threshold 정확도뿐 아니라 transition latency, thrashing, pending request 유실, reconfiguration 중 입력 처리를 testbench로 확인한다.

## 13. Calibration: 무엇을 어떻게 보정할 것인가

- **Radiometric/sensor calibration:** lens cap dark/bias frames, 여러 exposure의 uniform flat frames, gain/ISO·온도별 측정으로 black offset, temporal noise, conversion gain, saturation, PRNU/DSNU를 구한다. 주 근거는 EMVA 1288이다.
- **Color calibration:** 표준 illuminant 아래 ColorChecker를 linear RAW로 촬영해 AWB와 CCM을 fitting하고 ΔE 또는 patch residual을 보고한다.
- **Geometric calibration:** 렌즈 왜곡이나 다중 카메라 좌표가 실험에 관여할 때만 intrinsic/extrinsic calibration을 별도로 수행한다.
- [Zhang, “A Flexible New Technique for Camera Calibration,” IEEE TPAMI, 2000](https://doi.org/10.1109/34.888718) — 평면 checkerboard 여러 자세로 intrinsic/extrinsic과 distortion을 구하는 표준적 geometric calibration 방법이다.
- [OpenCV Camera Calibration tutorial](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html) — Zhang 계열 방법의 실제 구현, reprojection error와 distortion correction 절차다.
- 실험 규칙: calibration frame과 평가 frame은 같은 preprocessing code path를 써야 하며, sensor/camera, lens, CFA, bit depth, exposure, analog/digital gain, temperature, black/white level, illuminant를 metadata로 보존한다.

## 14. DFX (Dynamic Function eXchange)

- [AMD Vivado Design Suite User Guide: Dynamic Function eXchange, UG909](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration) — static logic, reconfigurable partition(RP), reconfigurable module(RM), partition pin, floorplanning, implementation, partial bitstream, `pr_verify`의 공식 정의와 flow다.
- [AMD Dynamic Function eXchange Controller, PG374](https://docs.amd.com/v/u/en-US/pg374-dfx-controller) — self-reconfiguration을 관리하는 DFX Controller IP의 interface, state, trigger 및 bitstream 관리 reference다. DFXISP checker→controller 연결의 직접 근거다.
- [AMD DFX Tutorial, UG947](https://docs.amd.com/r/en-US/ug947-vivado-partial-reconfiguration-tutorial) — 여러 RM configuration 생성, implementation과 partial bitstream 검증을 재현할 수 있는 공식 실습이다.
- DFXISP 적용 규칙: RM_NORMAL과 RM_LOW_LIGHT가 같은 RP interface/partition pin contract를 만족하고 상호배타적으로 resident함을 보여야 한다. static shell·각 RM·always-on 양쪽 구현의 자원 비교는 같은 device, clock, constraint, Vivado version, post-route 기준으로 해야 한다.
- 효율 검증: 정확도는 SW/HW bit-exact output과 detector mAP로, DFX의 고유 기여는 post-route LUT/FF/BRAM/DSP, partial-bitstream size, reconfiguration latency, transition energy, steady-state board power로 분리해 보고한다.

## 15. AI detection, computer vision, visual AI, vision for AI

- 용어 정리: **computer vision**은 영상에서 의미를 추론하는 분야 전체, **AI detection/object detection**은 객체의 class와 위치를 예측하는 하위 task, **visual AI**는 학술적으로 엄밀한 단일 알고리즘명보다 vision 기반 AI 시스템을 넓게 부르는 표현이다. **vision for AI**는 이 연구에서는 사람이 보기 위한 ISP가 아니라 AI가 소비하기 좋은 입력을 만드는 machine-oriented vision/ISP라는 뜻으로 사용하는 편이 명확하다.
- [Krizhevsky, Sutskever & Hinton, “ImageNet Classification with Deep Convolutional Neural Networks,” NeurIPS 2012](https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html) — 현대 CNN visual recognition의 대표적 출발점으로, 입력 영상 통계와 learned feature의 관계를 이해하는 배경 자료다.
- [Ren et al., “Faster R-CNN,” NeurIPS 2015](https://arxiv.org/abs/1506.01497) — two-stage object detector의 대표 구조다. YOLO 계열과 다른 detector에서도 ISP 결론이 유지되는지 cross-model 검증할 때 쓸 baseline이다.
- [Redmon et al., “You Only Look Once,” CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Redmon_You_Only_Look_CVPR_2016_paper.html) — single-stage real-time detection 계열의 기초다. FPGA/edge vision의 latency 목적과 잘 맞는다.
- [Lin et al., “Microsoft COCO: Common Objects in Context,” ECCV 2014](https://arxiv.org/abs/1405.0312) — detection dataset와 다양한 객체 크기/문맥 평가의 기초다. binning에 따른 small-object 성능을 분리 평가하는 배경이다.
- [Everingham et al., “The PASCAL Visual Object Classes Challenge,” IJCV 2010](https://doi.org/10.1007/s11263-009-0275-4) — PASCAL VOC detection task, annotation, AP 평가의 원전이다. PASCALRAW의 annotation 계보를 설명할 때 사용한다.
- [Dodge & Karam, “Understanding How Image Quality Affects Deep Neural Networks,” QoMEX 2016](https://doi.org/10.1109/QoMEX.2016.7498955) — blur, noise, contrast, compression이 CNN 정확도에 서로 다르게 영향을 준다는 실험이다. 모든 image-quality 열화를 하나의 PSNR로 대신할 수 없다는 근거다.
- [Wu et al., “Low-Light Enhancement Effect on Classification and Detection: An Empirical Study,” 2024](https://arxiv.org/abs/2409.14461) — LLIE가 사람 눈에는 개선되어도 classification/detection에는 일관된 이득을 주지 않는다는 비교다. ISP 선택 기준을 downstream task metric으로 두는 근거다.
- [Diamond et al., “Dirty Pixels: Towards End-to-End Image Processing and Perception,” ACM TOG 2021](https://light.princeton.edu/publication/dirty-pixels/) — RAW-to-task joint optimization에서 perceptual quality와 recognition optimum이 다를 수 있음을 보인다.
- [Yoshimura et al., “DynamicISP: Dynamically Controlled Image Signal Processor for Image Recognition,” ICCV 2023](https://arxiv.org/abs/2211.01146) — 이미지 조건에 따라 ISP parameter를 동적으로 제어한다. 조도 조건에 따라 ISP mode를 바꾸는 DFXISP의 알고리즘 측 선행연구와 가장 가깝다.

## 16. 실험 설계를 뒷받침하는 규칙

- **가설을 분리한다:** (H1) low-light ISP가 dark condition에서 normal ISP보다 detection 성능이 높은가, (H2) checker 기반 adaptive 선택이 condition별 이득을 유지하는가, (H3) DFX가 always-on 구현보다 자원·전력 효율적인가를 별도로 검정한다.
- **한 번에 한 요소를 바꾼다:** binning, BLC, AWB/CCM, gain, gamma를 factorial 또는 단계별 ablation으로 분리한다. 여러 stage를 동시에 바꾼 두 RM만 비교하면 원인 귀속을 할 수 없다.
- **동일 입력·동일 split을 쓴다:** 각 arm은 같은 RAW와 annotation, resize/letterbox, detector weight, confidence/NMS, 평가 코드를 사용한다. 가능하면 image 단위 paired bootstrap으로 AP 차이의 신뢰구간을 구한다.
- **데이터 누수를 막는다:** calibration/tuning set과 final test set을 분리한다. checker threshold, BLC/gain/gamma, detector threshold를 test 결과를 보고 반복 선택하면 최종 수치가 낙관적으로 편향된다.
- **정확도와 화질을 분리한다:** 주요 endpoint는 mAP/AP50/AP-small과 checker 오류로 두고, PSNR/SSIM, mean luma, sigma, saturation, color error는 원인 분석용 보조 지표로 둔다.
- **RAW 정합성을 보장한다:** CFA pattern, black/white level, bit depth, crop origin, linearity를 확인한다. sRGB를 inverse-gamma한 pseudo-RAW는 실제 Poisson–Gaussian sensor RAW와 같지 않으므로 별도 표기한다.
- **HW 비교를 공정하게 한다:** 동일 device/clock/constraints/tool version 및 post-route 보고서를 사용하고, static과 RP 자원을 분리한다. DFX 전환 중 drain/decouple, partial-bitstream transfer, reconfiguration latency와 dropped/stalled frame 정책을 기록한다.
- **재현성을 남긴다:** dataset version/hash, sample 수, random seed, commit, model weight, library/tool version, calibration constants, 모든 LUT/threshold와 평가 명령을 결과 문서에 고정한다.

## 17. 이 저장소 안의 관련 정본·상세 자료

- [`README.md`](README.md) — 현재 DFXISP 목표, active architecture, normal/low-light RM 구성과 상태 요약.
- [`SPEC.md`](SPEC.md) — 입력부터 checker, RM, 출력, 평가까지 시스템 계약과 RP 경계.
- [`ROADMAP.md`](ROADMAP.md) — Stage 0~6 실험 및 HW 검증의 진행 상황과 근거 문서 index.
- [`isppipeline/hls/results/lowlight-mv-isp-survey-2026-07-03.md`](isppipeline/hls/results/lowlight-mv-isp-survey-2026-07-03.md) — 저조도 machine-vision ISP에 대한 기존 심층 문헌조사.
- [`isppipeline/hls/results/lowlight-feature-principles-2026-07-05.md`](isppipeline/hls/results/lowlight-feature-principles-2026-07-05.md) — SNR, high-frequency feature, VST, binning, denoise 선택 원리.
- [`isppipeline/hls/results/checker-principles-2026-07-05.md`](isppipeline/hls/results/checker-principles-2026-07-05.md) — dark-ratio checker의 광도·노이즈·표본·시간축 원리.
- [`isppipeline/hls/checker/checker_hysteresis.md`](isppipeline/hls/checker/checker_hysteresis.md) — 현재 60/64% hysteresis, dwell, request/ack와 testbench 결과.
- [`isppipeline/sw/sim/binning.md`](isppipeline/sw/sim/binning.md), [`blc.md`](isppipeline/sw/sim/blc.md), [`gain.md`](isppipeline/sw/sim/gain.md), [`gamma.md`](isppipeline/sw/sim/gamma.md) — 현재 SW pipeline의 stage별 동작과 실험 메모.

## 18. 인용 시 주의사항

- 제조사 tutorial은 구현 설명에는 좋지만 핵심 성능 주장에는 peer-reviewed 논문이나 표준을 함께 인용한다.
- arXiv 링크는 접근성이 좋지만 출판본이 있으면 DOI/CVF/학회본을 우선 인용한다.
- “2×2 binning = 무조건 +6 dB”, “gain = SNR 개선”, “gamma = denoise”처럼 조건을 생략한 문장을 피한다. 합산/평균, read 위치, noise regime, clipping, 해상도 조건을 같이 쓴다.
- 이 문서의 수식은 실험 설계용 요약이다. 논문 본문에는 실제 사용한 signal domain(raw code/electron/normalized linear RGB), 단위, estimator와 calibration 절차를 명시한다.
