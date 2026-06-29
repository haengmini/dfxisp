---
type: paper-outline
title: "DFXISP 석사 학위논문 — Outline (방향 A 재편)"
project: DFXISP
target: 석사 학위논문 (제주대 전자공학과, 목표 2026.10)
language: 한글 본문 + 영문 Abstract + 영어 기술용어
status: drafting (방향 A: resource/power 중심 재편 2026-06-29)
created: 2026-06-26
updated: 2026-06-29
sources: "[[dfxisp-R1-theory-source-inventory-2026-06-23]] · [[dfxisp-A1-architecture-fpga-constraints-2026-06-23]] · [[08-e2-map-results-2026-06-29]]"
---

# DFXISP 학위논문 — 설계도 (Outline, 방향 A)

> 정본(무엇이 done인가). 본문 `01-thesis-draft.md`, 참고문헌 `02-references.md`, 그림·표 `03-figures-tables.md`, RM 사양 `04-implementation-rm-spec.md`, 실험 `05-experiment-protocol.md`, 실측 `06~08`.
> 원칙: 미검증 수치는 `TODO(측정)`. 예비 실측은 출처를 밝히고 단정하지 않음.

## 재편 한 줄 요지 (방향 A)
**task-adaptive mAP는 register-fast path가 확보한다(실측: real-low-light에서 register-only가 최고). DFX의 가치는 mAP 향상이 아니라, 구조적으로 크고 상호배타적인 블록을 "필요할 때만" 적재하여 얻는 자원/전력 절감이다.** 본 논문의 기여는 "무엇을 register로, 무엇을 DFX-RM으로 둘지를 mAP-guardrail 하에 자원/전력 기준으로 결정하는 방법론과 그 ZCU104 evidence"다.

## 제목 (draft, 재편)
- 국문: **ZCU104를 위한 Resource-Aware Register/DFX 분할 적응형 ISP: mAP는 레지스터로, 면적·전력은 부분재구성으로**
- 영문: *Resource-Aware Register/DFX Partitioning for Adaptive ISP on Zynq UltraScale+: Register-Driven Accuracy, Reconfiguration-Driven Area/Power*

## 한 줄 기여 (thesis statement)
머신비전 ISP의 장면 적응을 register-fast path와 DFX-RM slow path로 계층화하되, **적응의 정확도(mAP) 기여는 register/LUT가 담당**하고 **DFX는 면적/전력이 큰 상호배타 구조 블록의 시분할 적재로 자원 효율을 담당**하도록 역할을 분리한다. 어떤 연산을 어느 계층에 둘지는 **mAP를 떨어뜨리지 않는다는 guardrail 하에 자원/전력/PR-latency 기준으로 결정**하며, ZCU104 evidence package로 검증한다.

## 핵심 기여 4가지 (재편)
1. **Resource-aware register/DFX partitioning policy:** 적응 연산을 (a) register/LUT(빠름·mAP 담당)와 (b) DFX-RM(면적·전력 큰 구조 블록·자원 담당)으로 나누는 **결정 기준**을 제시. 단순 파라미터는 register, 구조가 바뀌고 상호배타이며 상시 상주 비용이 큰 블록만 DFX 후보.
2. **mAP-guardrail RM screening (evidence-driven):** DFX-RM 후보(DFX-Bin binning, DFX-FP feature-preserving)를 **자원/전력 이득과 mAP guardrail로 선별**하는 절차. 예비 실측에서 detail-boost형 DFX-FP는 저조도 mAP를 떨어뜨려 **guardrail에서 탈락**함을 보이고(부정 결과를 방법론의 작동 증거로 활용), 자원이 정당화되는 후보(binning/denoise 계열, resident-bypass 등)를 제시.
3. **DFX-aware scene scheduler:** PR latency·drain·switch·thrashing을 고려한 장면 단위 전환. register 전환(무중단)과 DFX 전환(장면 단위)을 비용에 맞게 분리.
4. **ZCU104 resource/power evidence package:** static / register-only / DFX-Bin(/DFX-FP ablation)을 동일 파이프라인에서 비교, **1차 지표 = LUT/FF/BRAM/DSP·power·partial bitstream size·PR latency**, **mAP는 guardrail(≥ register-only)**. DFX가 normal 모드 fabric/전력을 register-only 대비 줄이는지를 정량화.

## 핵심 실측 근거 (방향 A의 출발점, [[08-e2-map-results]])
- real-low-light(ExDark, n=260, yolov8n/s 동일 순서): **reg_only 최고, DFX-FP 최저**. → mAP는 register가 담당, detail-boost RM은 부적합.
- COCO 전체(n=347): 저조도 처리는 정상조도에서 이득 없음 → **장면 적응 스위칭 필요**(기여 1/3).
- ⇒ "DFX=mAP 향상"이 아니라 "DFX=자원/전력 절감 + register=mAP"로 역할 분리하는 것이 데이터와 정합.

## 장(章) 구성 (재편)
```
1. 서론          배경·문제(상시 상주 비용)·동기(register는 mAP, DFX는 자원)·기여·구성
2. 관련 연구      적응형/AI-ISP(parameter vs module) · RAW low-light · FPGA ISP · DFX/DPR · 자원-인식 적응의 빈자리
3. 제안 설계      register/DFX 분할 정책 · mAP-guardrail RM screening · RP 분할 · DFX-aware scheduler
4. 구현          ZCU104 · register fast path · DFX-RM 후보 · 부분비트스트림 · 비교군
5. 실험 및 평가    [1차] 자원/전력/PR latency/bitstream  · [guardrail] mAP(register-only 대비) · scheduler 안정성
6. 결론          요약 · 한계(부정결과 포함) · 향후(denoise형 RM, real-RAW, 자원 모델)
```

## 진행 보드 (장별 상태)
```
[~] 1 서론        — 재편 반영(register=mAP, DFX=자원) / 본문 다듬기
[~] 2 관련연구     — 비교표 Tab2 / "자원-인식 적응" 축으로 재정렬
[x] 3 제안설계     — 분할정책+RM screening+scheduler, Fig1~6 작도
[~] 4 구현        — RM 사양(04) 재편(자원 관점) / csynth·DFX flow는 보드
[~] 5 실험·평가    — 1차지표=자원/전력으로 전환; mAP guardrail 예비실측 반영 / 보드 측정 TODO
[~] 6 결론        — 부정결과를 방법론 증거로 재서술
범례: [x] 완료 · [~] 서술완결·실측대기 · [ ] 미착수
```

## 확정된 설계 결정 (2026-06-28~29)
1. 해상도·fps: 개발 640×480 → 평가 1280×720@30fps (frame budget 33.3ms).
2. 비교군: static / register-only / DFX-Bin / (DFX-FP는 ablation/부정사례).
3. **1차 평가지표 = 자원/전력/PR-latency**, mAP는 guardrail. (방향 A 핵심 전환)
4. **DFX 1순위 RM = DFX-Bin(2×2 binning + integer bilinear upsample).** detail-boost(DFX-FP)는 ablation. (결정 1) — bilinear 개선으로 ExDark mAP guardrail 통과(reg 대비 0.09pt, [[08-e2-map-results]]).
5. **mAP guardrail Δ = register-only 대비 절대 1.0 mAP point(@[.5:.95], ≈ 상대 5%) 이내.** "무시 가능 저하"의 보편 기준. (결정 2)
6. **자원 비교 main baseline = static all-resident** (normal+low-light 블록 상시 상주, DFX 없음). DFX-Bin이 이 대비 normal 모드 fabric/전력을 얼마나 줄이는지가 핵심 결과. (결정 3)
7. metric 데이터: COCO/ExDark pseudo-RAW(확보), real-RAW(LOD/NOD)는 향후.

> **용어 주의:** mAP 변종의 `static`(= demosaic-only 파이프라인)과, 자원 baseline `static all-resident`(= 모든 블록 상주 HW 구성)는 다른 개념. 전자는 정확도 참조, 후자는 면적/전력 참조다.

## 즉시 막힌 것 / 결정 필요
(핵심 3개 결정 완료 — 2026-06-29. 남은 항목 없음. 다음은 구현/측정 단계.)

## 일정 (역산, 목표 2026.10)
```
~7월:  3장 분할정책/RM screening 확정 + Fig2/Fig3/자원 trade-off 그림틀
~8월:  4장 구현 — register fast path + DFX-Bin/denoise RM HLS, csynth 자원수치
~9월:  5장 실험 — ZCU104 자원/전력/PR latency 측정 + mAP guardrail 확인
~10월: 1·2·6장 + Abstract 마감, 부정결과 서술 포함, 교정·제출
```
