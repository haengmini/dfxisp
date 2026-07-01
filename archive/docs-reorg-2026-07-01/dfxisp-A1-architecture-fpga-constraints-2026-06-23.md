---
type: research
title: "DFXISP A1 — Architecture & FPGA Constraint Analysis"
project: DFXISP
task_id: DFXISP-A1
board: dfxisp
owner_agent: analyst
status: review
created: 2026-06-23
tags: [dfx, isp, fpga, architecture, low-light, zcu104]
---

# DFXISP-A1 — Architecture & FPGA Constraint Analysis

> R1 인벤토리 + 형민 입력 + 실제 repo(`Research/FPGA/ISP/DFXISP`) + Notion 논문 DB("문서 허브")에 근거. 핸드오프 스키마 준수.

## Summary
실제 repo를 보면 DFXISP는 이미 **baseline(고정 ISP) vs proposal(checker+binning_gain+pr_controller+isp_proposal)** C/C++ 레퍼런스가 구현돼 있고, normal/low-light 차이는 **대부분 파라미터(gain 256→320, γ2.2→4.0, 2x2 binning on/off)**다. 핵심 분석 결론: **이 차이의 대부분은 레지스터/LUT 스왑으로 충분하고, 진짜 DFX(부분 비트스트림 교체)가 정당화되는 지점은 "구조가 바뀌는 부분(binning 경로) 또는 normal에선 면적을 안 내고 싶은 무거운 low-light 블록"으로 한정된다.** DFX를 *어디에* 쓰는지가 A1의 핵심 결정.

## Inputs
- `Research/FPGA/ISP/DFXISP/`: PROJECT.md, README.md, AI_README.md, isppipeline/{baseline,proposal}
- 확정 파라미터(PROJECT.md handoff): BLC16, gainN256/LL320, AWB R286/G256/B307, CCM288, γ2.2(N)/4.0(LL), LOW_LIGHT 게인 = binning ×1.5(sum*3/8) + pre-gain ×1.25 이중적용
- 형민 입력: Checker→Normal=일반 pipeline / Low-light=프런트엔드(Binning+Gain+Gamma) 변형, 나머지 모듈 공유
- Notion 논문 DB(문서 허브): AdaptiveISP, DynamicISP, Dark-ISP, GenISP, HISP(FPGA), Hardware-Aware LLIE on Edge, Learning to See in the Dark 등

## Output — 분석

### 1. RP 분할 문제 (가장 중요한 HW 제약)
형민 설계의 mode-dependent 연산은 **파이프라인상 흩어져 있다**: Binning/Gain은 프런트, Gamma는 백엔드(CCM 뒤). DFX의 Reconfigurable Partition(RP)은 **물리적으로 연속된 영역**이어야 한다 → 흩어진 연산을 하나의 RP로 묶기 어렵다. 선택지:
- (a) **파라미터 스왑**: Gain/Gamma는 RM 비트스트림이 아니라 레지스터/LUT 값으로 전환(연속 영역 불필요). ← 권장 기본.
- (b) **단일 RP = ISP 데이터패스 전체**: 면적 크고 reconfig 비용 큼.
- (c) **2개 RP**(front: binning, back: gamma-LUT): 관리 복잡.
→ **결정 가설: Gain·Gamma = 레지스터 스왑, 구조가 바뀌는 Binning(+필요시 저조도 denoise)만 DFX RM 후보.**

### 2. DFX vs 레지스터 재구성 (novelty 정당화)
확정 델타를 보면 normal↔low-light는 거의 파라미터다. 그러면 "그냥 레지스터 쓰면 되는데 왜 DFX?"라는 리뷰어 질문에 답해야 한다(YAGNI 관점). DFX가 실제 가치를 주는 경우는:
- **면적**: low-light용 무거운 블록(예: binning+denoise, 또는 소형 CNN 보정)을 normal 모드에선 fabric에서 빼서 면적/전력 절감.
- **상호배타 경로**: normal·low-light 데이터패스가 동시 필요 없을 때 같은 영역을 시분할.
→ A1 권고: **DFX의 신규성 주장 = "상호배타 + 면적 큰 low-light 프런트엔드를 부분재구성으로 시분할"**. 단순 gain/gamma는 비교군(register baseline)으로 두고 *DFX가 면적/전력에서 이기는 지점*을 실험 변인으로 설계.

### 3. 재구성 지연 vs 프레임레이트 (운영 제약)
부분 비트스트림은 DFX Controller가 ICAP로 로드한다. 지연 ≈ (부분 비트스트림 크기 ÷ ICAP 대역폭). 30fps=33ms 예산에서 **프레임마다 모드 스왑은 비현실적** → 모드 전환은 **장면 단위(히스테리시스 적용 checker)**여야 한다. (정확한 지연은 RM 크기 확정 후 계산 — Open Q.)

### 4. Checker 강건성 (실측 리스크를 제약으로)
repo 실측: COCO checker 일치율 **0.216**, proposal high clipping ratio. → checker가 모드를 자주 오판하면 DFX 스왑이 무의미하거나 진동(thrashing). **제약: checker에 히스테리시스/시간적 안정화 + low-light 게인 경로 clipping 방지(소프트 니/헤드룸)**. 이건 §3의 "장면 단위 전환"과 직결.

### 5. 문헌 포지셔닝 (corpus 기준 차별점)
- 학습형 파라미터 적응: **AdaptiveISP**(객체검출용 ISP 파라미터를 RL로 적응), **DynamicISP**(인식용 동적 제어 ISP) → "적응은 파라미터로" 진영. 형민 설계의 register-swap 부분과 정렬.
- RAW 저조도 검출: **Dark-ISP**, **GenISP**, **Learning to See in the Dark** → low-light RM의 알고리즘 후보.
- FPGA 이종 ISP: **HISP**(전통+딥러닝 ISP를 FPGA에) , **Hardware-Aware LLIE on Edge** → HW 구현 선행근거.
→ **차별점: 위 문헌은 학습형 *파라미터* 적응 또는 고정 HW가 주류. "DFX 부분재구성으로 ISP 프런트엔드를 시분할 교체"는 빈자리** → 단, §2대로 면적/전력 이득으로 정당화해야 기여로 성립.

## Decisions
- 기본 적응은 레지스터/LUT 스왑(Gain·Gamma). **DFX는 구조가 바뀌고 면적 큰 low-light 프런트엔드(Binning±denoise)에만** 적용.
- 모드 전환은 장면 단위(히스테리시스 checker), 프레임 단위 아님.
- 평가 비교군에 **register-only adaptive** 를 반드시 포함(DFX의 추가 이득을 분리 측정).

## Verification
- 파라미터·실측 수치(0.216, gain/γ 값)는 repo PROJECT.md handoff에서 직접 인용. 미검증 수치 단정 없음.
- 재구성 지연은 원리만 제시, 정확값은 RM 크기 미확정이라 Open Q로 분리.

## Open Questions
1. low-light RM 후보를 binning만으로 둘지, denoise/소형 enhancement까지 포함할지? (면적·정당성 좌우)
2. ZCU104 타깃 해상도·fps? (재구성 지연 예산 계산에 필요)
3. 비교군에 register-only adaptive 포함 동의? (DFX 순이득 분리용)

## Next Agent
→ **coder (DFXISP-C1)**: ① RM 경계(binning±denoise) HLS 프로토타입, ② 부분 비트스트림 크기→ICAP 재구성 지연 측정, ③ register-only vs DFX 면적/전력 비교 실험 scaffold. 기존 `isppipeline/proposal/` C/C++ 위에 얹기.

## Sources
- repo: `Research/FPGA/ISP/DFXISP/{PROJECT.md, README.md, AI_README.md}`
- corpus: Notion "문서 허브" DB (AdaptiveISP, DynamicISP, Dark-ISP, GenISP, HISP, Hardware-Aware LLIE, Learning to See in the Dark)
- DFX 기반: [[dfxisp-R1-theory-source-inventory-2026-06-23]] (AMD DFX/DFX Controller/ICAP, ACM DPR survey)
