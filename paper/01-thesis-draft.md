---
type: paper-draft
title: "DFXISP 학위논문 — 본문 골격"
project: DFXISP
status: drafting
created: 2026-06-26
note: "각 장은 R1·A1 및 2026-06-26 논문 서베이에서 시드. [TODO]는 형민 입력/측정/작성 필요. 미검증 수치 단정 금지."
---

# DFXISP 학위논문 — 본문 (Working Draft)

> 표기: **[작성]** 글쓰기만 남음 · **[TODO:측정]** 실측 필요 · **[TODO:결정]** Open Q · `(refs: …)` → `02-references.md`

---

## 1. 서론

### 1.1 배경
- 머신비전에서 ISP(Image Signal Processing)는 센서 RAW → 인식 가능한 영상으로 변환하는 핵심 단계. (refs: [isp-npu], [hisp])
- 환경(특히 **저조도**)에 따라 최적 ISP 동작이 달라짐 → 고정 파이프라인의 한계. (refs: [seeindark], [darkisp])
- FPGA는 ISP를 실시간·저전력으로 구현 가능하나, 보통 **정적(고정) 회로**. (refs: [hisp], [hwllie])

### 1.2 문제 정의
- normal과 low-light는 서로 다른 ISP 동작을 요구하지만, 둘을 동시에 fabric에 올리면 면적·전력 낭비.
- 실제 repo 분석상 두 모드 차이의 **대부분은 파라미터**(gain, gamma)지만, **구조가 바뀌는 부분(binning 경로, 저조도 보정/Denoise)** 은 별도 하드웨어가 필요. (A1 §1)

### 1.3 동기 — 왜 DFX인가
- DFX(Dynamic Function eXchange) = 런타임에 부분 비트스트림으로 회로 일부 교체. (refs: [amd-dfx], [amd-dfxctrl])
- 가설: normal·low-light **데이터패스는 상호배타**(동시 불필요) → 같은 fabric 영역을 **시분할**하면 면적/전력 절감. (A1 §2)
- **단, 단순 gain/γ는 레지스터로 충분** → DFX는 "구조가 바뀌고 면적 큰 저조도 프런트엔드"에만 정당화. (핵심 논지)

### 1.4 기여
- (1) **하이브리드 적응 아키텍처:** gain/gamma는 레지스터로, 구조적 저조도 프런트엔드는 DFX RM으로 전환하는 아키텍처 제안.
- (2) **인식 특화 저조도 RM 설계:** 2x2 Binning 및 Denoise 기반의 저조도 RM(`DFX-Bin`) 및 피처 보존 RM(`DFX-FP`)을 제안하고 mAP 최적화 설계.
- (3) **리소스 인지형 스케줄러:** PR latency, frame drain, power, bandwidth cost 등을 고려하는 스케줄러 목적함수 모델링.
- (4) **ZCU104 검증 패키지:** ZCU104 위에서 4종의 실험 variant에 대해 리소스, 전력, 지연시간, mAP 등을 실측하여 DFX의 정량적 순이득 증명.

### 1.5 논문 구성 — [작성]

---

## 2. 관련 연구

### 2.1 DFX / DPR 메커니즘
- AMD DFX: static region + Reconfigurable Partition(RP)/Module(RM), 부분 비트스트림을 ICAP로 로드. (refs: [amd-dfx], [amd-dfxctrl], [amd-zynqmp-pl])
- DPR 일반: 재구성 지연·면적·throughput 트레이드오프. (refs: [csur-dpr], [eurasip-dpr], [dpr-rt])

### 2.2 적응형 / AI-ISP
- 파라미터 적응 및 최적화: **AdaptiveISP**([adaptiveisp])는 RL로 객체검출용 ISP 최적화를, **DynamicISP**([dynamicisp])는 이미지별 실시간 파라미터 튜닝을 제안. → 본 연구의 register-swap 부분의 선행 연구.
- 저조도 및 태스크 특화 ISP: **Dark-ISP**([darkisp])는 Bayer RAW 직접 처리 및 linear/nonlinear 분할 구조를, **TA-ISP**([ta-isp])는 Perception 최적화 representation 생성을 제안. **Beyond RGB**([beyond-rgb])는 병렬 브랜치 구성을 제안하나 하드웨어 면적 이슈가 있음. **SimROD**([simrod])는 G-channel 가이드 로컬 인핸스먼트를 제시함.
- 다양한 환경 벤치마크: **AODRaw**([aodraw])는 다양한 날씨/조명 조건 하의 RAW object detection 벤치마크로 condition-aware RM 라우팅의 필요성을 지지함.

### 2.3 FPGA ISP 및 Edge 구현
- **HISP**([hisp])는 전통+딥러닝 이종 ISP FPGA 가속, **Hardware-Aware LLIE on Edge**([hwllie])는 저조도 edge 구현.
- **POS-ISP**([pos-isp])는 Sequence 레벨의 ISP 파이프라인 최적화를 제안했으나 하드웨어/DPR cost(PR latency, frame stall 등)를 고려하지 않음.

### 2.4 차별점 (positioning) — [작성 + 비교표 Tab2]
- 기존 AI-ISP 연구는 selection/tuning을 software나 heavy한 neural network로만 처리하거나, FPGA 구현은 static 고정 회로에 국한됨.
- 제안 연구는 ZCU104 FPGA 상에서 register-fast adaptation과 DFX-RM 시분할 재구성으로 데이터패스를 분리하여, HW resource 및 전력 이득을 정량화하고 DFX 스케줄러 상에 하드웨어 오버헤드(stall, latency)를 반영한 최초의 연구임.

---

## 3. 제안 설계

### 3.1 전체 파이프라인 — [그림 Fig2]
- baseline(고정 ISP): BLC→demosaic→AWB→CCM→gamma 등. normal/low-light 공유 모듈 + 모드 의존 모듈. (A1 Inputs)
- 확정 파라미터: BLC16, gain N256/LL320, AWB R286/G256/B307, CCM288, γ 2.2(N)/4.0(LL), LL게인=binning×1.5 + pre-gain×1.25. (A1 Inputs — repo PROJECT.md 인용)

### 3.2 적응 메커니즘 분리 (하이브리드 아키텍처) — [Tab1]
- **레지스터/LUT 스왑**: gain, gamma → 연속 영역 불필요, 1-사이클 전환. (A1 §1(a))
- **DFX-RM**: 구조가 바뀌는 **2x2 Binning + Denoise** 혹은 **Feature-Preserving enhancement**만 부분재구성 대상. (A1 Decisions)

### 3.3 RP 분할 결정 — [그림 Fig3]
- 모드 의존 연산이 파이프라인상 흩어짐(binning 프런트, gamma 백엔드) → RP는 물리적 연속 영역이어야 함. (A1 §1)
- 결정: gain·gamma는 register, **binning±denoise만 단일 RP=RM**. (A1 §1 결정가설)

### 3.4 모드 전환 FSM — [그림 Fig6 FSM]
- 재구성 지연 ≈ 부분비트스트림 크기 ÷ ICAP 대역폭 → 프레임 단위(33ms@30fps) 스왑 비현실적 → **장면 단위 전환**. (A1 §3)
- checker 강건성: 히스테리시스를 포함하는 4-상태 FSM (`STATE_NORMAL`, `STATE_CONFIRM_LOW_LIGHT`, `STATE_LOW_LIGHT`, `STATE_CONFIRM_NORMAL`)을 도입하여 thrashing 방지 및 시간적 안정화 필터링 적용.

### 3.5 리소스 인지형 스케줄러 모델
- DFX 전환 여부를 판단하는 스케줄러는 단순히 mAP 이득만을 따지는 것이 아니라, 하드웨어 오버헤드(stall, latency)를 통합 평가하여 모드 전환을 스케줄링함.
- 목적함수 공식:
  \[ \text{Maximize } \text{Task mAP Gain} - \lambda_1 \cdot \text{PR Latency} - \lambda_2 \cdot \text{Frame Stall} - \lambda_3 \cdot \text{Power} - \lambda_4 \cdot \text{Bandwidth} \]
  여기서 \(\lambda_1, \lambda_2, \lambda_3, \lambda_4\)는 각각 재구성 지연, 프레임 드랍/스톨, dynamic power 및 AXI 버스 대역폭 패널티 계수임.

---

## 4. 구현

### 4.1 타깃·툴체인
- ZCU104 (Zynq UltraScale+ MPSoC). Vivado/Vitis 2024.1, Vitis AI. (`[[MY]]`)
- 검증 체인: Verilator(lint) → Icarus+cocotb(Python 골든모델 bit-exact) → Vivado batch(synth/timing). (`[[MY]]`)

### 4.2 기존 자산 위에 구축
- repo `Research/FPGA/ISP/DFXISP/isppipeline/{baseline, proposal}` C/C++ 레퍼런스 활용.

### 4.3 DFX-RM 구현
- binning RM HLS 프로토타입 (`DFX-Bin`) 및 피처 보존 RM (`DFX-FP`) 구현 -> 부분 비트스트림 생성 -> DFX Controller/ICAP 로드.

### 4.4 비교군 (Variants)
- (1) **`Static`**: 고정 기본 ISP (baseline)
- (2) **`Reg-only`**: DFX 없이 레지스터/Mux 스위칭 제어로 전체 파이프라인 탑재
- (3) **`DFX-Bin`**: DFX 기반 2x2 Binning + Denoise RM 스왑 적용
- (4) **`DFX-FP`**: DFX 기반 Feature-Preserving enhancement RM 스왑 적용

---

## 5. 실험 및 평가

### 5.1 실험 설계
- 변인: 4종 variant (`Static` vs `Reg-only` vs `DFX-Bin` vs `DFX-FP`).
- 지표: 면적(LUT/FF/BRAM/DSP), Dynamic Power, 재구성 지연, Object Detection mAP, fps.

### 5.2 재구성 지연 — [TODO:측정]
- ZCU104 ICAP (100MHz 32-bit = 400MB/s) 대역폭 및 부분 비트스트림 크기 대비 지연 계산/실측 (이론값 1.95 ms).

### 5.3 면적·전력 — [TODO:측정] [Tab3, Tab4]
- 4종 variant 간의 리소스 사용량 및 dynamic power 비교. Register-only 대비 DFX의 면적/전력 감소량 정량 측정.

### 5.4 화질·정확도 — [TODO:측정] [Tab5]
- golden model 대비 bit-exact 검증 및 ExDark/COCO 데이터셋 기반 RAW object detection mAP 비교.

### 5.5 checker 안정성 — [TODO:측정]
- 히스테리시스 FSM 적용 전/후의 모드 오판/thrashing 감소량 비교.

---

## 6. 결론

### 6.1 요약 — [작성]
### 6.2 한계 — [작성]
- DFX×AI-ISP "빈자리" 판정은 검색 범위 내 결론(전수조사 아님). (R1 Verification)
### 6.3 향후 연구 — [작성]
- 다중 RM 및 Vitis AI 연계 가속기 확장.

---

## 부록/메모
- 모든 [TODO:측정]은 실측 전까지 수치 단정 금지(`[[MY]]` §6).
