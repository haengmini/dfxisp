---
type: paper-outline
title: "DFXISP 석사 학위논문 — Outline"
project: DFXISP
target: 석사 학위논문 (제주대 전자공학과, 목표 2026.10)
language: 한글 본문 + 영문 Abstract + 영어 기술용어
status: drafting
created: 2026-06-26
sources: "[[dfxisp-R1-theory-source-inventory-2026-06-23]] · [[dfxisp-A1-architecture-fpga-constraints-2026-06-23]]"
---

# DFXISP 학위논문 — 설계도 (Outline)

> 이 파일이 논문의 **단일 정본(무엇이 done인가)**. 본문은 `01-thesis-draft.md`, 참고문헌 `02-references.md`, 그림·표 `03-figures-tables.md`.
> 원칙: 미검증 수치는 단정하지 않고 `TODO(측정)`로 표시(`[[MY]]` §6).

## 제목 (draft)
- 국문: **DFX 부분 재구성 기반 적응형 AI-ISP 설계 및 ZCU104 FPGA 구현**
- 영문: *Design and FPGA Implementation of an Adaptive AI-ISP Using DFX Partial Reconfiguration on Zynq UltraScale+*

## 한 줄 기여 (thesis statement)
머신비전용 ISP에서 normal↔low-light 적응의 대부분은 레지스터 스왑으로 충분하지만,
**구조가 바뀌고 면적이 큰 저조도 프런트엔드(binning±denoise)를 DFX 부분재구성으로 시분할 교체**하면
상호배타 경로에서 면적·전력 이득을 얻는다 — 이를 ZCU104에서 register-only 대비 실측한다.

## 핵심 기여 4가지 (survey 근거 갱신)
1. **하이브리드 적응 아키텍처 (Hybrid register/DFX adaptation):**
   gain/gamma/threshold와 같이 빠른 전환이 요구되는 연산은 register/LUT 스왑으로 처리하고, 구조가 근본적으로 변하여 면적 부담이 크고 상호배타적인 저조도 ISP 프런트엔드는 DFX RM 교체 방식으로 설계를 분리함으로써 dynamic reconfiguration의 정당성을 확보함.
2. **인식 특화 저조도 RM 설계 (Task-aware low-light RM):**
   인간의 시각적 선호가 아닌 object detection 성능(mAP) 최적화를 타깃으로 2x2 Binning 및 Denoise를 수행하는 Low-light RM을 구성하며, Feature-Preserving (FP) low-light RM의 추가적인 포트폴리오를 제안함.
3. **리소스 인지형 스케줄러 (DFX-aware scheduler):**
   단순 mAP 이득만을 고려하는 기존 task-aware ISP 스케줄러와 달리, DPR 재구성 지연(latency), AXI stall/frame drain, switching count 및 전력/대역폭 비용을 종합적으로 고려하여 스케줄러 목적함수를 모델링함.
4. **ZCU104 검증 패키지 (ZCU104 evidence package):**
   ZCU104 FPGA 위에서 4종의 실험 variant (Static, Register-only, DFX-Bin, DFX-FP)에 대해 mAP, 리소스 사용량(LUT/FF/BRAM/DSP), Dynamic Power, PR latency 등을 종합 실측하여 DFX의 정량적 순이득을 입증함.

## Abstract (draft — 채워질 자리)
- 국문 초록: TODO(본문 확정 후). 배경→문제→제안(DFX 분리 적응)→방법(ZCU104)→결과(면적/전력/지연)→의의.
- English Abstract: TODO.

## 장(章) 구성
```
1. 서론              배경·문제정의·동기·기여·논문구성
2. 관련 연구          DFX/DPR · 적응형/AI-ISP · FPGA ISP 구현 · 차별점
3. 제안 설계          파이프라인 · 적응 분리(register vs DFX) · RP 분할 · 모드 전환 · 스케줄러 모델
4. 구현              ZCU104 · 툴체인 · HLS RM · 부분비트스트림 · 비교군
5. 실험 및 평가        재구성지연 · 면적/전력 · 화질 · checker 안정성 · fps · mAP 정확도
6. 결론              요약 · 한계 · 향후연구
```

## 진행 보드 (장별 상태)
```
[ ] 1 서론        — 기여 4개로 업데이트 완료 / 본문 TODO
[ ] 2 관련연구     — 8대 논문 비교표 및 차별점 추가 완료 / 서술 보강 TODO
[ ] 3 제안설계     — 스케줄러 목적함수 및 4종 variant 설계 완료 / 그림 TODO
[ ] 4 구현        — HLS C-sim scaffold 및 3-arm 구현 완료 / HLS 합성 TODO
[ ] 5 실험·평가    — 비교 설계 O / 측정값 전부 TODO
[ ] 6 결론        — TODO
```

## 해결된 질문 & 마감 스펙 (2026-06-26)
1. **low-light RM 범위:** 2x2 Binning + Denoise(Mean filter)를 기본으로 하며, Edge guided local enhancement/Soft-knee를 지원하는 Feature-Preserving RM(`DFX-FP`)을 추가 variant로 설계함.
2. **ZCU104 타깃 해상도 & fps:** 1920x1080 @ 30fps (프레임 예산 33.3 ms).
3. **비교군 설계:** `Static`(고정), `Reg-only`(전체 회로 동시 탑재), `DFX-Bin`(기본 DFX), `DFX-FP`(피처 보존 DFX)의 4종 variant로 비교 실험 구조 확정.

## 일정 (역산, 목표 2026.10 제출)
```
~7월:  3장 제안설계 확정 + 그림 1·2·3, RM 범위 결정(Open Q1)
~8월:  4장 구현 — binning RM HLS 프로토타입 + 부분비트스트림 생성
~9월:  5장 실험 — register-only vs DFX 면적/전력/지연 측정, checker 안정화
~10월: 1·2·6장 + Abstract 마감, 교정·제출
```
