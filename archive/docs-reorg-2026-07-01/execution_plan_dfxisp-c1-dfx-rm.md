---
type: execution_plan
title: "DFXISP-C1 — Codex 실행계획 (DFX RM 프로토타입)"
task_id: DFXISP-C1
board: dfxisp
owner_agent: codex
status: ready
created: 2026-06-23
note: Claude(분석)→Codex(구현) 핸드오프. 실제 repo Research/FPGA/ISP/DFXISP에서 구현. 산출은 그 repo의 output/ + PROJECT.md Handoff Log 규약 따름.
---

# DFXISP-C1 — Codex 실행계획

A1([[dfxisp-A1-architecture-fpga-constraints-2026-06-23]]) 결론을 구현으로 옮긴다. Codex가 `isppipeline/proposal/` 위에 구현.

## A1 Open Q 결정 (형민 확정 2026-06-23)
- Q1: 저조도 RM에 **denoise 포함** (binning + gain + 경량 denoise).
- Q2: 타깃 **1920×1080 @ 30fps**, ZCU104 (작업 가정, 추후 조정 가능).
- Q3: 비교군에 **register-only adaptive 포함** (DFX 순이득 분리).

## Goal
3-arm 비교로 "DFX가 register-only 대비 면적·전력에서 이득"을 증명하는 scaffold + RM HLS 프로토타입 + 재구성 지연 측정.

## 3개 비교 arm
1. **baseline** — 고정 ISP (기존 `isppipeline/baseline/`).
2. **register-only adaptive** — 단일 비트스트림, gain/γ를 레지스터로 normal↔low-light 전환 (PR 없음).
3. **DFX adaptive** — 저조도 프런트엔드(binning+denoise)를 Reconfigurable Module로 부분재구성 교체.

## 구현 항목 (Codex)
1. **low-light RM 블록** (HLS-ready C++): 2x2 binning + gain + 경량 denoise. RP는 연속영역 1개로 한정(gain/γ는 RM 아님 → 레지스터).
2. **register-only variant**: 동일 기능을 파라미터화로(비트스트림 교체 없이) — arm 2.
3. **pr_controller 확장**: 히스테리시스 checker(장면 단위 전환, 프레임마다 금지) + DFX RM swap 트리거 FSM. clipping 방지(헤드룸/소프트니).
4. **reconfig 지연 측정**: 부분 비트스트림 크기 → ICAP 대역폭 기준 지연 계산/측정, 30fps(33ms) 예산과 대조.
5. **면적/전력 비교 harness**: Vivado synth/util/power 리포트 파싱 → baseline vs register-only vs DFX 표.

## Verification (완료 조건)
- `csim PASS` (기존 proposal 컨벤션), 가능 시 golden byte-exact mismatch=0.
- reconfig 지연 < 장면전환 예산(히스테리시스 주기) 확인.
- 3-arm 면적/전력/지연 표 산출 → register-only 대비 DFX 순이득 수치화.
- mAP 연결은 detector checkpoint 확정 후(현재 not_run).

## 제약 (A1)
- 모드 전환 = 장면 단위(히스테리시스), 프레임 단위 아님.
- RP = 연속 물리영역(binning+denoise만), gain/γ는 레지스터 스왑.
- checker 강건성: repo 실측 COCO 일치율 0.216 + high clipping → 시간적 안정화 필수.

## Handoff (Codex → Claude 리뷰)
- 실제 repo `PROJECT.md` Work Board 락 후 구현, 완료 시 `output/handoff_dfxisp-c1.md` + Handoff Log 1줄.
- 이후 Claude(analyst/reviewer)가 reconfig 지연·면적표 해석 + 리스크 리뷰.

## 입력 자료
- A1: [[dfxisp-A1-architecture-fpga-constraints-2026-06-23]] · R1: [[dfxisp-R1-theory-source-inventory-2026-06-23]]
- 실제 코드: `Research/FPGA/ISP/DFXISP/isppipeline/{baseline,proposal}`
- 논문: Notion "문서 허브" (Dark-ISP, GenISP=저조도 RM 알고리즘 후보; Hardware-Aware LLIE=HW)
