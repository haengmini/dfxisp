---
type: research
title: "DFXISP R1 — Theory & Source Inventory"
project: DFXISP
task_id: DFXISP-R1
board: dfxisp
owner_agent: researcher
status: review
created: 2026-06-23
tags: [dfx, dpr, isp, ai-isp, fpga, inventory]
---

# DFXISP-R1 — Theory & Source Inventory

> 핸드오프 스키마(`[[AGENT-OS]]`/agent-routing-contract)를 따른 loop 산출물. 외부 공개 문헌 기반 1차 인벤토리이며, 형민의 내부 자료(DFXISP 사양·실험 데이터)는 미반영 — Open Questions 참조.

## Summary
DFXISP = **DFX(Dynamic Function eXchange) 기반 적응형 ISP**. 두 축의 교차점이다: ① DFX/DPR로 런타임에 ISP 파이프라인 일부를 교체, ② 고전 ISP를 학습형/적응형(AI-ISP)으로. 외부 문헌상 둘 다 성숙한 분리 영역이나, "DFX로 ISP 모듈을 스왑하는 적응형 AI-ISP"라는 결합은 공개 사례가 희박 → 형민 연구의 차별점 가설.

## Inputs
- `[[MY]]` 연구 정체성·도구·검증 체인
- 외부 문헌 검색 (2026-06-23, 아래 출처)

## Output — 소스 인벤토리 (테마별)

### A. DFX / DPR 메커니즘 (정본·벤더)
- AMD DFX 개요 — static region + reconfigurable partition(RP)/module(RM), 부분 비트스트림을 ICAP로 로드. https://www.amd.com/en/products/adaptive-socs-and-fpgas/technologies/dynamic-function-exchange.html
- AMD DFX Controller IP — 트리거 시 메모리에서 부분 비트스트림을 ICAP로 전달. https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/dfx-controller.html
- ZynqMP PL Programming (AMD wiki) — ZU+에서 PL 부분 재구성 실무. https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841847/Solution+ZynqMP+PL+Programming
- *관련성*: DFXISP의 "런타임 모듈 스왑" 기반. RP/RM 분할이 ISP 단계(예: denoise/demosaic 변형)에 어떻게 매핑되는지가 A1 과제.

### B. DPR for 신호·영상 처리 (학술)
- ACM Computing Surveys, "FPGA Dynamic and Partial Reconfiguration: A Survey". https://dl.acm.org/doi/10.1145/3193827
- EURASIP J. Embedded Systems, "Evaluation of DPR for Signal and Image Processing". https://link.springer.com/article/10.1155/2008/367860
- "Internal DPR for real-time signal processing on FPGA" (ICAP+soft-core 구동). https://www.researchgate.net/publication/228888498
- *관련성*: ISP 파이프라인에 DPR 적용 시 reconfiguration latency·면적·throughput 트레이드오프의 선행 근거.

### C. AI-ISP / 적응형 ISP (최신)
- MDPI Mathematics, "Energy-Efficient Zero-Shot AI-ISP for Real-Time Low-Light Enhancement" — dual-network Retinex + FPGA 가속(bilinear interpolation). https://www.mdpi.com/2227-7390/14/8/1324
- "Integrating ISP and NPU" — 학습형 통합 파이프라인이 hand-tuned 순차 ISP를 대체(demosaic+denoise 통합). https://medium.com/@jasonyang.algo/next-generation-imaging-integrating-isp-and-npu-for-superior-image-quality-674a43f7831f
- *관련성*: "적응형" 축의 SOTA. DFX로 *어떤 RM을 스왑할지*(예: 저조도용 vs 일반용 ISP RM)의 후보.

### D. Edge AI 가속 / 머신비전 플랫폼 (맥락)
- arXiv survey, "AI and ML Accelerator Survey and Trends". https://arxiv.org/pdf/2210.04055
- "Energy-Efficient Quad-Camera Visual System on FPGA" (ZU+ XCZU9EG). https://arxiv.org/pdf/2104.00192
- Kria K26 (ZU+ MPSoC) 적응형 edge AI 모듈 — 파이프라인 커스터마이즈. (위 서베이/플랫폼 자료)
- *관련성*: ZCU104 타깃의 전력·면적 예산 기준선.

## Decisions
- DFXISP의 신규성 가설 = "DFX 모듈 스왑 × 적응형 AI-ISP". A/B는 풍부, C는 활발, **A×C 결합은 희박** → 여기에 집중.
- ZCU104(ZU+) 타깃 유지(형민 도구체인과 일치).

## Verification
- 출처 8건 모두 실제 URL·1차/학술/벤더. 미검증 수치 단정 없음(`[[MY]]` §6 준수).
- 한계: 공개 문헌만. DFX×AI-ISP 결합의 "희박" 판정은 본 검색 범위 내 결론이며 전수조사 아님.

## Open Questions (형민 입력 필요)
1. DFXISP 내부 사양/타깃 지표(해상도·fps·전력 예산)가 있나? → A1 제약 분석에 필수.
2. 스왑 대상 ISP 단계 후보(denoise/demosaic/tone)와 RM 경계는?
3. Zotero/Drive에 이미 모아둔 DFXISP 논문 corpus가 있나? 있으면 본 인벤토리에 머지.

## Next Agent
→ **analyst (DFXISP-A1)**: A×C 결합 가설 기준으로 아키텍처·FPGA 제약(RP 분할, reconfig latency, 면적/전력) 분석.

## Sources
위 본문 인라인 URL 참조 (AMD DFX, ACM CSUR survey, EURASIP, MDPI AI-ISP, arXiv 등).
