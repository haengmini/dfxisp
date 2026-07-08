# 참고문헌 링크 통합 인덱스 (2026-07-07)

principled-v3 캠페인(체커 + 저조도 RM 이론)을 뒷받침하는 논문/표준/자료 링크가 3개 문서에
흩어져 있던 것을 이 문서 하나로 모았다. 원 문서(아래 A/B/C)는 이제 서지 목록/각주 본문
대신 이 인덱스로의 포인터만 남긴다 — 참고문헌 링크는 이 파일에만 존재한다. 개별 원리·
발견과의 연결(어떤 근거가 어떤 결론을 뒷받침하는지)은 각 원 문서 본문을 참고.

- 출처 A: `checker-improvement-theory-2026-07-03.md` (체커 5원칙의 학술 인용, 원래 References 1–25)
- 출처 B: `checker-principles-2026-07-05.md` (Youden/Bayesian-opt/Weber-Fechner/subsampling/hysteresis — 대중적 설명 각주, 출처 A와 별개로 최근 추가됨)
- 출처 C: `lowlight-mv-isp-survey-2026-07-03.md` (저조도 RM 원칙의 근거, 원래 References 1–33 + 2026-07-07 최신 후속연구 4편 추가)

중복(같은 문헌이 두 출처에 인용된 경우)은 각 항목에 표시했다.

---

## A. 체커 이론 (출처 A: checker-improvement-theory-2026-07-03.md, References 1–25)

1. Neyman & Pearson (1933), "On the Problem of the Most Efficient Tests of Statistical Hypotheses," *Phil. Trans. Royal Society A* 231:289–337.
   https://royalsocietypublishing.org/doi/10.1098/rsta.1933.0009
2. Duda, Hart & Stork (2001), *Pattern Classification*, 2nd ed., Wiley.
   https://www.wiley.com/en-us/Pattern+Classification,+2nd+Edition-p-9780471056690
3. Youden (1950), "Index for Rating Diagnostic Tests," *Cancer* 3(1):32–35.
   https://acsjournals.onlinelibrary.wiley.com/doi/10.1002/1097-0142(1950)3:1%3C32::AID-CNCR2820030106%3E3.0.CO;2-3
4. Lehmann & Romano (2005), *Testing Statistical Hypotheses*, 3rd ed., Springer.
   https://link.springer.com/book/10.1007/0-387-27605-X
5. Cover & Thomas (2006), *Elements of Information Theory*, 2nd ed., Wiley.
   https://onlinelibrary.wiley.com/doi/book/10.1002/047174882X
6. Reinhard, Stark, Shirley & Ferwerda (2002), "Photographic Tone Reproduction for Digital Images," *ACM TOG* 21(3) (SIGGRAPH).
   https://www.cs.utah.edu/docs/techreports/2002/pdf/UUCS-02-001.pdf
7. ISO 12232:2019, *Photography — Digital still cameras — exposure index/ISO speed/SOS/REI*.
   https://www.iso.org/standard/73758.html
8. EMVA (2010), *EMVA Standard 1288*, Release 3.0.
   https://www.emva.org/wp-content/uploads/EMVA1288-3.0.pdf
   (해설: https://www.baslerweb.com/en/learning/emva-1288-standard/)
9. Janesick (2007), *Photon Transfer: DN → λ*, SPIE Press.
   https://spie.org/publications/book/725073  *(→ 출처 C #2와 동일 문헌)*
10. Rose (1948), "The Sensitivity Performance of the Human Eye on an Absolute Scale," *JOSA* 38(2):196–208.
    https://opg.optica.org/josa/abstract.cfm?uri=josa-38-2-196
11. Page (1954), "Continuous Inspection Schemes," *Biometrika* 41(1/2):100–115. (CUSUM)
    https://en.wikipedia.org/wiki/CUSUM
12. Moustakides (1986), "Optimal Stopping Times for Detecting Changes in Distributions," *Annals of Statistics* 14(4):1379–1387.
    https://projecteuclid.org/journals/annals-of-statistics/volume-14/issue-4/Optimal-Stopping-Times-for-Detecting-Changes-in-Distributions/10.1214/aos/1176350164.full
13. Wald (1945), "Sequential Tests of Statistical Hypotheses," *Annals of Mathematical Statistics* 16(2):117–186. (SPRT)
    https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-16/issue-2/Sequential-Tests-of-Statistical-Hypotheses/10.1214/aoms/1177731118.full
14. Dixit (1989), "Entry and Exit Decisions under Uncertainty," *Journal of Political Economy* 97(3):620–638.
    https://www.journals.uchicago.edu/doi/abs/10.1086/261619 ([PDF](https://digilander.libero.it/vergalli/pdf/69.pdf))
15. Rabiner (1989), "A Tutorial on Hidden Markov Models and Selected Applications in Speech Recognition," *Proc. IEEE* 77(2):257–286.
    doi:10.1109/5.18626 (https://doi.org/10.1109/5.18626)
16. Schmitt (1938), "A Thermionic Trigger," *Journal of Scientific Instruments* 15(1):24–26.
    https://iopscience.iop.org/article/10.1088/0950-7671/15/1/305
17. Brown, Cai & DasGupta (2001), "Interval Estimation for a Binomial Proportion," *Statistical Science* 16(2):101–133.
    https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.full
18. Hoeffding (1963), "Probability Inequalities for Sums of Bounded Random Variables," *JASA* 58(301):13–30.
    https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830
19. Cochran (1977), *Sampling Techniques*, 3rd ed., Wiley.
    https://www.wiley.com/en-us/Sampling+Techniques,+3rd+Edition-p-9780471162407
20. Otsu (1979), "A Threshold Selection Method from Gray-Level Histograms," *IEEE Trans. SMC* 9(1):62–66.
    https://doi.org/10.1109/TSMC.1979.4310076
21. Kapur, Sahoo & Wong (1985), "A New Method for Gray-Level Picture Thresholding Using the Entropy of the Histogram," *CVGIP* 29(3):273–285.
    https://www.sciencedirect.com/science/article/abs/pii/0734189X85901252
22. Kittler & Illingworth (1986), "Minimum Error Thresholding," *Pattern Recognition* 19(1):41–47.
    https://doi.org/10.1016/0031-3203(86)90030-0
23. Gonzalez & Woods (2018), *Digital Image Processing*, 4th ed., Pearson.
    https://www.pearson.com/en-us/subject-catalog/p/digital-image-processing/P200000003224  *(→ 출처 C #5와 동일 문헌)*
24. Bernacki (2020), "Automatic Exposure Algorithms for Digital Photography," *Multimedia Tools and Applications* 79:12751–12776.
    https://link.springer.com/article/10.1007/s11042-019-08318-1
25. Loh & Chan (2019), "Getting to Know Low-light Images with the Exclusively Dark Dataset," *CVIU* 178:30–42.
    http://cs-chan.com/doc/cviu.pdf  *(→ 출처 C #9와 동일 문헌, GitHub 링크는 다름)*

---

## B. 체커 이론 — 대중적 설명 각주 (출처 B: checker-principles-2026-07-05.md, 최근 추가된 각주)

**Youden's J statistic**
- [Wikipedia](https://en.wikipedia.org/wiki/Youden's_J_statistic)
- [Youden Index — mass-at-zero 보정 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2749250/)
- [Youden's J와 비대칭 비용 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2959030/)

**Bayesian optimization**
- [Exploring Bayesian Optimization — Distill.pub](https://distill.pub/2020/bayesian-optimization/)
- [Bayesian Optimization for Hyperparameters Tuning, arXiv:2410.21886](https://arxiv.org/abs/2410.21886)
- [Hyperparameter Tuning With Bayesian Optimization — Comet](https://www.comet.com/site/blog/hyperparameter-tuning-with-bayesian-optimization/)

**log-average luminance / Weber–Fechner**
- Reinhard et al. 2002 (→ 출처 A #6과 동일 문헌)
- [Weber–Fechner law (Kiddle)](https://kids.kiddle.co/Weber%E2%80%93Fechner_law)
- [Weber's Law — Proc. Royal Society A (2023)](https://royalsocietypublishing.org/rspa/article/479/2271/20220626/54513/Weber-s-Law-of-perception-is-a-consequence-of)

**1/16 systematic subsampling**
- [Subsamplings — ScienceDirect Topics](https://www.sciencedirect.com/topics/engineering/subsamplings)
- [Ch.3 Upsampling/Downsampling — Forsyth, UIUC lecture notes (PDF)](http://luthuli.cs.uiuc.edu/~daf/Courses/CV2026/Notes/Jan27/Ch3updownsmooth.pdf)
- [21. Downsampling and Upsampling — MIT Foundations of Computer Vision](https://visionbook.mit.edu/upsamplig_downsampling_2.html)

**Schmitt trigger hysteresis / Dixit optimal-inaction**
- Schmitt 1938 (→ 출처 A #16과 동일 문헌)
- [Schmitt Trigger Hysteresis — Cadence](https://resources.pcb.cadence.com/blog/2021-schmitt-trigger-hysteresis-provides-noise-free-switching-and-output)
- [All About Circuits, Ch.7 Hysteresis](https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/hysteresis/)
- Dixit 1989 (→ 출처 A #14와 동일 문헌)

---

## C. 저조도 RM 이론 (출처 C: lowlight-mv-isp-survey-2026-07-03.md, References 1–33)

**물리/노이즈 모델**
1. Foi, Trimeche, Katkovnik, Egiazarian (2008), "Practical Poissonian-Gaussian Noise Modeling...," *IEEE TIP* 17(10).
   https://webpages.tuni.fi/foi/papers/Foi-PoissonianGaussianClippedRaw-2007-IEEE_TIP.pdf
2. Janesick (2007), *Photon Transfer: DN → λ* — https://spie.org/publications/book/725073 *(→ 출처 A #9)*
3. EMVA (2010), *EMVA Standard 1288* — https://www.emva.org/wp-content/uploads/EMVA1288-3.0.pdf *(→ 출처 A #8)*
4. Nakamura (ed., 2005), *Image Sensors and Signal Processing for Digital Still Cameras*, CRC Press.
   https://dl.acm.org/doi/10.5555/1211284
5. Gonzalez & Woods (2018), *Digital Image Processing*, 4th ed. — https://www.pearson.com/en-us/subject-catalog/p/digital-image-processing/P200000003224 *(→ 출처 A #23)*
6. Gnanasambandam & Chan (2022), "Exposure-Referred SNR for Digital Image Sensors."
   https://arxiv.org/pdf/2112.05817
7. Anscombe (1948), "The transformation of Poisson, binomial and negative-binomial data," *Biometrika* 35.
   https://academic.oup.com/biomet/article-abstract/35/3-4/246/280278
8. Mäkitalo & Foi (2011/2013), Anscombe/GAT 역변환, *IEEE TIP*.
   https://webpages.tuni.fi/foi/invansc/

**저조도 detection 벤치마크/분석**
9. Loh & Chan (2019), ExDark — https://github.com/cs-chan/Exclusively-Dark-Image-Dataset *(→ 출처 A #25)*
10. Yang et al., DARK FACE / UG2+ Challenge.
    https://flyywh.github.io/CVPRW2019LowLight/
11. Hong, Wei, Chen, Fu (2021), "Crafting Object Detection in Very Low Light," *BMVC*.
    https://kxwei.net/publication/bmvc21_lod/
12. Rodríguez-Rodríguez et al. (2024), "The Impact of Noise and Brightness on Object Detection Methods," *Sensors* 24(3):821.
    https://www.mdpi.com/1424-8220/24/3/821
13. Dodge & Karam (2016), "Understanding How Image Quality Affects Deep Neural Networks," *QoMEX*.
    https://www.researchgate.net/publication/301876936
14. Wu et al. (2024), "Low-Light Enhancement Effect on Classification and Detection."
    https://arxiv.org/pdf/2409.14461
15. "LIME-Eval: Rethinking Low-light Image Enhancement Evaluation via Object Detection" (2024).
    https://arxiv.org/pdf/2410.08810

**ISP-for-vision**
16. Buckler, Jayasuriya, Sampson (2017), "Reconfiguring the Imaging Pipeline for Computer Vision," *ICCV*.
    https://openaccess.thecvf.com/content_iccv_2017/html/Buckler_Reconfiguring_the_Imaging_ICCV_2017_paper.html
17. Hansen et al. (2019), "ISP4ML."
    https://arxiv.org/abs/1911.07954
18. Wu et al. (2019), "VisionISP," *ICIP*.
    https://arxiv.org/abs/1911.05931
19. Yahiaoui, Horgan, Deegan et al. (2019), ISP 파라미터 자동튜닝, *J. Imaging* 5(10):78.
    https://www.mdpi.com/2313-433X/5/10/78
20. Mosleh et al. (2020), "Hardware-in-the-Loop End-to-End Optimization...," *CVPR*.
    https://openaccess.thecvf.com/content_CVPR_2020/html/Mosleh_Hardware-in-the-Loop_End-to-End_Optimization_of_Camera_Image_Processing_Pipelines_CVPR_2020_paper.html
21. Diamond et al. (2021), "Dirty Pixels," *ACM TOG (SIGGRAPH)*.
    https://light.princeton.edu/publication/dirty-pixels/
22. Chen, Chen, Xu, Koltun (2018), "Learning to See in the Dark," *CVPR*.
    https://arxiv.org/abs/1805.01934
23. Ljungbergh, Johnander, Petersson, Felsberg (2023), "Raw or Cooked?," *SCIA*.
    https://arxiv.org/abs/2301.08965
24. Yoshimura et al. (2023), "DynamicISP," *ICCV*.
    https://arxiv.org/abs/2211.01146
25. Yoshimura et al. (2023), "Rawgment," *CVPR*.
    https://arxiv.org/pdf/2210.16046
26. Xu et al. (2023), "Toward RAW Object Detection (ROD)," *CVPR*.
    https://openaccess.thecvf.com/content/CVPR2023/papers/Xu_Toward_RAW_Object_Detection_A_New_Benchmark_and_a_New_CVPR_2023_paper.pdf

**모듈별**
27. Gharbi, Chaurasia, Paris, Durand (2016), "Deep Joint Demosaicking and Denoising," *SIGGRAPH Asia*.
    https://github.com/mgharbi/demosaicnet
28. Jin & Hirakawa (2012), "Analysis and processing of pixel binning...," *EURASIP JASP*.
    https://asp-eurasipjournals.springeropen.com/articles/10.1186/1687-6180-2012-125
29. Teledyne Vision Solutions, "Binning" (imaging fundamentals).
    https://www.teledynevisionsolutions.com/learn/learning-center/imaging-fundamentals/binning/
30. Guo, Li et al. (2020), "Zero-Reference Deep Curve Estimation (Zero-DCE)," *CVPR*.
    https://openaccess.thecvf.com/content_CVPR_2020/html/Guo_Zero-Reference_Deep_Curve_Estimation_for_Low-Light_Image_Enhancement_CVPR_2020_paper.html
31. Wang et al. (2023), "Improved YOLOX ... low-light and small object detection," *J. Comput. Des. Eng.* 10(3).
    https://academic.oup.com/jcde/article/10/3/1158/7177527
32. Li et al. (2021), "WaveCNet," *IEEE TIP*.
    https://arxiv.org/pdf/2107.13335
33. Li et al. (2021), "Assessing the Impact of DNN-based Image Denoising on Binary Signal Detection Tasks."
    https://arxiv.org/pdf/2104.14037

**2020년대 최신 추가 (2026-07-07 갱신)** — 아래 4편은 원 문서(`lowlight-mv-isp-survey-2026-07-03.md`)
작성 시점(2018–2021 수준)보다 해당 서브필드가 빠르게 갱신되어, 대체가 아니라 후속 SOTA로 보강.

34. Cai, Bian, Lin, Wang, Timofte, Zhang (2023), "Retinexformer: One-stage Retinex-based Transformer for Low-light Image Enhancement," *ICCV* 2023.
    https://arxiv.org/abs/2303.06705  *(→ #30 Zero-DCE(2020)의 후속. ICCV 2023 Top-10 Cited, NTIRE 2024–2026 챌린지 기준 baseline)*
35. da Silva et al. (2023), "ISP meets Deep Learning: A Survey on Deep Learning Methods for Image Signal Processing," *ACM Computing Surveys*.
    https://arxiv.org/abs/2305.11994  *(→ #16–21 ISP-for-vision 개별 논문들을 2019–2024 범위로 포괄하는 서베이)*
36. Li, Jin, Sun, Guo, Cheng (2025), "AODRaw: Towards RAW Object Detection in Diverse Conditions," *CVPR* 2025 (Highlight).
    https://arxiv.org/abs/2411.15678  *(→ #26 Xu et al. ROD(2023)보다 넓은 9종 조도·날씨 조건의 RAW 벤치마크·모델)*
37. Li, Lahiri, Dai, Mayer (2023), "Joint Demosaicing and Denoising with Double Deep Image Priors" (JDD-DoubleDIP), *BMVC* 2023 (Oral).
    https://arxiv.org/abs/2309.09426  *(→ #27 Gharbi et al.(2016)의 후속. 학습 데이터 없이 단일 RAW 이미지에서 동작)*

---

## 요약: 중복 문헌 (여러 출처에서 인용됨)

| 문헌 | 출처 A | 출처 B | 출처 C |
|---|---|---|---|
| Janesick, *Photon Transfer* (2007) | #9 | — | #2 |
| Gonzalez & Woods, *DIP* 4th ed. (2018) | #23 | — | #5 |
| Loh & Chan, ExDark (2019) | #25 | — | #9 |
| Reinhard et al. (2002) | #6 | logmean 각주 | — |
| Schmitt (1938) | #16 | hysteresis 각주 | — |
| Dixit (1989) | #14 | hysteresis 각주 | — |

25(A) + 5그룹(B) + 37(C, 2026-07-07 최신 추가 4편 포함) = 문헌 실질 개수는 중복 제외 약 59개.
