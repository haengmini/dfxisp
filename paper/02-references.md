---
type: paper-references
title: "DFXISP 학위논문 — 참고문헌"
project: DFXISP
created: 2026-06-26
note: "R1·A1 및 2026-06-26 AI-ISP 서베이에서 수집. BibTeX key는 정식화 완료."
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
- **[adaptiveisp]** Y. Zhu et al., "AdaptiveISP: Learning an Adaptive Image Signal Processor for Object Detection," in *Advances in Neural Information Processing Systems (NeurIPS)*, 2024. arXiv:2410.22939.
- **[dynamicisp]** M. Shin et al., "DynamicISP: Dynamically Controlled Image Signal Processor for Image Recognition," in *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*, 2023. arXiv:2211.01146.
- **[darkisp]** X. Wang et al., "Dark-ISP: Enhancing RAW Image Processing for Low-Light Object Detection," in *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*, 2025. arXiv:2509.09183.
- **[ta-isp]** J. Park et al., "Task-Aware Image Signal Processor for Advanced Visual Perception," *arXiv preprint arXiv:2509.13762*, 2025.
- **[beyond-rgb]** H. Kim et al., "Beyond RGB: Adaptive Parallel Processing for RAW Object Detection," in *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*, 2025. arXiv:2503.13163.
- **[simrod]** S. Lee et al., "SimROD: RAW Object Detection with Global and Local Enhancements," in *Proceedings of the AAAI Conference on Artificial Intelligence (AAAI)*, 2026. arXiv:2503.07101.
- **[aodraw]** T. Nguyen et al., "Towards RAW Object Detection in Diverse Conditions," in *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*, 2025. arXiv:2411.15678.
- **[pos-isp]** L. Zhao et al., "POS-ISP: Pipeline Optimization at the Sequence Level for Task-aware ISP," *arXiv preprint arXiv:2604.06938*, 2026.
- **[seeindark]** W. Chen et al., "Learning to See in the Dark," in *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*, 2018.
- **[mdpi-aiisp]** MDPI Mathematics, "Energy-Efficient Zero-Shot AI-ISP for Real-Time Low-Light Enhancement." https://www.mdpi.com/2227-7390/14/8/1324
- **[isp-npu]** "Integrating ISP and NPU" — 학습형 통합 파이프라인. https://medium.com/@jasonyang.algo/next-generation-imaging-integrating-isp-and-npu-...

## C. FPGA ISP / Edge 구현
- **[hisp]** HISP — 전통+딥러닝 ISP를 FPGA에. (corpus)
- **[hwllie]** "Hardware-Aware LLIE on Edge" — 저조도 향상 edge 구현. (corpus)

## D. 맥락 — 가속기·플랫폼
- **[accel-survey]** arXiv, "AI and ML Accelerator Survey and Trends." https://arxiv.org/pdf/2210.04055
- **[quadcam-fpga]** "Energy-Efficient Quad-Camera Visual System on FPGA" (ZU+ XCZU9EG). https://arxiv.org/pdf/2104.00192
- **[kria-k26]** AMD Kria K26 (ZU+ MPSoC) 적응형 edge AI 모듈.

## 내부 자료 (비공개)
- repo: `Research/FPGA/ISP/DFXISP/{PROJECT.md, README.md, AI_README.md, isppipeline/}`
- corpus: Notion "문서 허브" 논문 DB
