---
type: project
title: DFXISP
layer: production
status: active
priority: P0
board: dfxisp
created: 2026-06-23
owner: 이형민
tags: [fpga, dfx, isp, machine-vision, zynq-ultrascale]
---

# DFXISP

DFX(Dynamic Function eXchange) 기반 **적응형 AI-ISP**를 머신 비전용으로 설계하고 Zynq UltraScale+ ZCU104 FPGA에 구현하는 프로젝트.

## 컨텍스트 (정본 포인터)
- 연구 정체성·도구·검증 체인 → `[[MY]]` (FPGA / Adaptive ISP / DPR / Edge AI, Vivado·Vitis 2024.1, Verilator→cocotb→Vivado batch)
- 운영 규칙 → `[[AGENT-OS]]` · 우선순위 → `[[agent-os-canonical-roadmap-2026-06-23]]`

## 산출물
- [[dfxisp-R1-theory-source-inventory-2026-06-23]] — R1 이론·소스 인벤토리
- [[dfxisp-A1-architecture-fpga-constraints-2026-06-23]] — A1 아키텍처·FPGA 제약 분석
- **`paper/`** — 석사 학위논문 작업공간 (목표 2026.10)
  - `00-thesis-outline.md` — 정본: 제목·기여·장구성·일정·막힌 것
  - `01-thesis-draft.md` — 6장 본문 골격 (R1+A1 시드)
  - `02-references.md` — 참고문헌
  - `03-figures-tables.md` — 그림·표 계획

## 다음 (논문)
R1·A1 완료 → **paper/ 골격 O** → 즉시: 3장 설계 확정 + Fig2·Fig3·Tab1 작도(측정 불필요) → RM 범위 결정(Open Q1).
연구 루프(C1 실험 scaffold → V1 검증 → REP1 digest)는 4·5장 실험을 채운다.
