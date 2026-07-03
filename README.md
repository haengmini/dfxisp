---
type: project
title: DFXISP
layer: production
status: active
priority: P0
board: dfxisp
created: 2026-06-23
owner: 이형민
tags: [fpga, dfx, isp, machine-vision, zynq-ultrascale, low-light]
updated: 2026-07-03
---

# DFXISP

DFXISP는 Zynq UltraScale+ ZCU104에서 **shared baseline ISP core**를 공통 경로로 유지하고, 조도 조건에 따라 **mode-specific tone Reconfigurable Module(RM)** 을 선택하는 Dynamic Function eXchange 기반 AI-ISP 연구 프로젝트다. 평상시에는 `RM_NORMAL_TONE` 또는 identity bypass를 사용하고, 어두운 환경에서는 `RM_LOW_LIGHT_TONE`을 트리거한다.

## Active architecture

```text
Input Bayer / pseudo-RAW / RGB fixture
  -> Scene checker
       - 평상시: normal tone RM 또는 identity bypass
       - 어두운 환경: low-light tone RM trigger
  -> Mutually exclusive tone RM slot
       NORMAL: gain -> gamma, or identity
       LOW_LIGHT: 2x2 binning -> gain -> gamma
  -> Baseline ISP core
       BLC -> AWB/color calibration -> demosaic or bypass -> CCM -> RGB32 pack
  -> RGB32 / DPU-facing output
```

핵심 원칙:

1. **Shared baseline ISP core는 공통 후단 경로다.**
2. **Gain/gamma는 baseline core에 중복 배치하지 않고 mode-specific tone RM으로 분리한다.**
3. **Normal tone RM과 low-light tone RM은 mutually exclusive다.**
4. **Checker가 어두운 장면을 감지했을 때만 low-light tone RM을 트리거한다.**
5. **Low-light tone RM의 1차 명세는 `binning + gain + gamma`다.**
6. DFX 실증 전에는 C-Sim/Python golden으로 산술 정합을 먼저 고정한다.

## Current status (2026-07-03)

- **Stage 0~3 (SW 트랙): 완료** — golden/baseline core 확정, checker+히스테리시스, tone RM 산술, mAP 평가(ver1/ver2/BLC 완화 3라운드).
- **Stage 4~5 (HW 트랙): 완료(한계 기록됨)** — Vitis HLS 합성 + C/RTL Co-sim, Vivado DFX 구현 + pr_verify + PR latency 분석.
- **Stage 6 (보드 실장 + DPU end-to-end): 미착수** — 실물 ZCU104 필요, 유일하게 남은 단계.
- 상세 진행 상태와 근거 문서는 `ROADMAP.md` 참조.

## Next direction

다음 리팩토링 방향은 **Vitis Vision Library 기준 baseline + DFXISP 확장 모듈** 구조다 (자체 ISP 전체를 새로 만드는 대신 Vitis Base를 고정하고 Check / Dark / DFX Ctrl을 확장). 계획 전문은 `STRATEGY.md` 참조.

## Active documents

- `README.md` — 프로젝트 한 페이지 요약 (이 문서)
- `RESEARCH.md` — 연구 정본: 배경, 아키텍처, RM 명세, 실험/검증 계획
- `SPEC.md` — 시스템 사양서: 입력 데이터셋 → checker → tone RM → baseline core → RGB32 출력 → 평가
- `ROADMAP.md` — Stage 0~6 진행 상태 추적 (근거 문서 링크 포함)
- `STRATEGY.md` — Vitis-first 리팩토링 전략 (2026-07-03, 다음 구현 방향)

실험/시뮬레이션 산출물 전체 목록은 `isppipeline/hls/results/INDEX.md` 에서 찾을 수 있다.

이전 문서들은 `archive/docs-reorg-2026-07-01/` 에 보존되어 있다 (`archive/README.md` 참조).

## Repository layout

```text
README.md / RESEARCH.md / SPEC.md / ROADMAP.md / STRATEGY.md   정본 문서 5종
isppipeline/hls/            HLS 구현 (src, include, tests, tools, scripts)
isppipeline/hls/results/    실험·시뮬레이션 산출물 (INDEX.md 로 탐색)
isppipeline/hls/reports/    최신 검증 리포트 (latest.md) + csynth 리포트
isppipeline/baseline/       Baseline ISP 참고 자료
isppipeline/proposal/       Proposal ISP 참고 자료 (historical)
model/                      Detector 모델 메타데이터 (weights는 Drive 백업)
include/aie-ml/             AIE-ML 참고 자료
archive/                    이전 구조의 문서 보존 (archive/README.md 참조)
```

## Verification status

```text
cd isppipeline/hls
make verify        # Python golden ↔ C-sim bit-exact + binning cross-check
make report        # reports/latest.md 갱신
```

`reports/latest.md` 기준: golden PASS, C-sim PASS, 아키텍처 gate 6종 PASS (shared baseline core / RM 2종 / 상호배타 / gain·gamma 중복없음 / 형상정책).

## Related locations

- GitHub (code source of truth): https://github.com/haengmini/dfxisp
- Google Drive 백업: `내 드라이브/Agent OS/06-production/DFXISP/` (dataset zip, 모델 weights, 다이어그램, lit-reviews 포함)
