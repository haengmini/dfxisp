---
type: paper-references
title: "DFXISP 학위논문 — 참고문헌"
project: DFXISP
created: 2026-06-26
note: "R1·A1에서 수집. BibTeX key는 임시. 정식 인용정보(저자·연도·DOI)는 인용 확정 시 보강 — 현재 미검증 필드는 TODO."
---

# 참고문헌 (Working Bibliography)

> 그룹: A) DFX/DPR · B) 적응형·AI-ISP · C) FPGA ISP/Edge · D) 맥락(가속기·플랫폼).
> 본문 `01-thesis-draft.md`의 `(refs: …)` 가 여기를 가리킨다.

## A. DFX / DPR 메커니즘 (벤더·서베이)
- **[amd-dfx]** AMD, "Dynamic Function eXchange" 개요 — static region + RP/RM, 부분 비트스트림 ICAP 로드.
  https://www.amd.com/en/products/adaptive-socs-and-fpgas/technologies/dynamic-function-exchange.html
- **[amd-dfxctrl]** AMD, "DFX Controller IP" — 트리거 시 부분 비트스트림을 ICAP로 전달.
  https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/dfx-controller.html
- **[amd-zynqmp-pl]** AMD Wiki, "ZynqMP PL Programming" — ZU+ 부분 재구성 실무.
  https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841847/
- **[csur-dpr]** ACM Computing Surveys, "FPGA Dynamic and Partial Reconfiguration: A Survey." https://dl.acm.org/doi/10.1145/3193827
- **[eurasip-dpr]** EURASIP J. Embedded Systems, "Evaluation of DPR for Signal and Image Processing." https://link.springer.com/article/10.1155/2008/367860
- **[dpr-rt]** "Internal DPR for real-time signal processing on FPGA" (ICAP+soft-core). https://www.researchgate.net/publication/228888498

## B. 적응형 / AI-ISP
- **[adaptiveisp]** AdaptiveISP — 객체검출용 ISP pipeline/parameter RL 적응. NeurIPS 2024. https://arxiv.org/abs/2410.22939
- **[dynamicisp]** DynamicISP — 인식용 동적 제어 ISP. ICCV 2023. https://arxiv.org/abs/2211.01146
- **[ta-isp]** Task-Aware Image Signal Processor for Advanced Visual Perception — compact RAW-to-RGB task-aware representation. 2025. https://arxiv.org/abs/2509.13762
- **[pos-isp]** POS-ISP — sequence-level task-aware ISP pipeline optimization. 2026. https://arxiv.org/abs/2604.06938
- **[raw-or-cooked]** Raw or Cooked? Object Detection on RAW Images. 2023. https://arxiv.org/abs/2301.08965
- **[beyond-rgb-ram]** Beyond RGB: Adaptive Parallel Processing for RAW Object Detection. ICCV 2025. https://arxiv.org/abs/2503.13163
- **[simrod]** SimROD: A Simple Baseline for RAW Object Detection with Global and Local Enhancements. AAAI 2026. https://arxiv.org/abs/2503.07101
- **[darkisp]** Dark-ISP — RAW 저조도 object detection용 lightweight self-adaptive ISP. ICCV 2025. https://arxiv.org/abs/2509.09183
- **[genisp]** GenISP — Neural ISP for Low-Light Machine Cognition. CVPRW 2022. https://arxiv.org/abs/2205.03688
- **[aodraw]** Towards RAW Object Detection in Diverse Conditions / AODRaw. CVPR 2025. https://arxiv.org/abs/2411.15678
- **[seeindark]** Learning to See in the Dark (Chen et al., CVPR 2018). https://arxiv.org/abs/1805.01934
- **[trash-to-treasure]** Trash to Treasure: Low-Light Object Detection via Decomposition-and-Aggregation. AAAI 2024. https://arxiv.org/abs/2309.03548
- **[yola]** You Only Look Around: Learning Illumination-Invariant Feature for Low-light Object Detection. NeurIPS 2024. https://arxiv.org/abs/2410.18398
- **[mdpi-aiisp]** MDPI Mathematics, "Energy-Efficient Zero-Shot AI-ISP for Real-Time Low-Light Enhancement." https://www.mdpi.com/2227-7390/14/8/1324
- **[isp-npu]** "Integrating ISP and NPU" — 학습형 통합 파이프라인. https://medium.com/@jasonyang.algo/next-generation-imaging-integrating-isp-and-npu-...

## C. FPGA ISP / Edge 구현
- **[hisp]** HISP — 전통+딥러닝 ISP를 FPGA에. (corpus) TODO(정식 인용)
- **[hwllie]** "Hardware-Aware LLIE on Edge" — 저조도 향상 edge 구현. (corpus) TODO(정식 인용)
- **[vitis-vision-isp]** Xilinx Vitis Vision Library ISP Pipeline — FPGA/HLS ISP blocks. https://xilinx.github.io/Vitis_Libraries/vision/2022.1/overview.html#isp
- **[kv260]** AMD/Xilinx Kria KV260 Vision AI Starter Kit — Zynq UltraScale+ edge vision platform. https://www.amd.com/en/products/system-on-modules/kria/k26/kv260-vision-starter-kit.html
- **[fold-fpga]** FOLD: Low-Level Image Enhancement for Low-Light Object Detection Based on FPGA MPSoC. 2024. https://doi.org/10.3390/electronics13010230
- **[fpga-retinex]** FPGA-based/low-cost Retinex low-light enhancement implementations. 2024. https://doi.org/10.1109/TCSII.2024.3361561

## D. 맥락 — 가속기·플랫폼
- **[accel-survey]** arXiv, "AI and ML Accelerator Survey and Trends." https://arxiv.org/pdf/2210.04055
- **[quadcam-fpga]** "Energy-Efficient Quad-Camera Visual System on FPGA" (ZU+ XCZU9EG). https://arxiv.org/pdf/2104.00192
- **[kria-k26]** AMD Kria K26 (ZU+ MPSoC) 적응형 edge AI 모듈. TODO(정식 자료 링크)

## 내부 자료 (비공개 — 인용 형태 결정 필요)
- repo: `Research/FPGA/ISP/DFXISP/{PROJECT.md, README.md, AI_README.md, isppipeline/}`
- corpus: Notion "문서 허브" 논문 DB

> TODO: 학위논문 인용양식(IEEE 또는 학교 규정) 확정 후 BibTeX 변환. 현재는 URL·식별자 보존이 목적.
