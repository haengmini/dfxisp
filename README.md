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

## Current reset decision

최근 HLS C-sim scaffold는 low-light를 post-RGB8 gain/lift로 단순화했지만, 이것은 최종 연구 구조와 다르다. 지금부터 문서/구현 기준은 다음으로 재정렬한다.

```text
정본 방향: mode-specific tone RM slot + baseline ISP core
NORMAL RM: gain + gamma or identity
LOW_LIGHT RM: binning + gain + gamma
현재 단순 scaffold: normal demosaic 후 RGB8 gain/lift
```

따라서 후속 구현은 `RESEARCH.md`의 RM/baseline 구조를 기준으로 고친다.

## Active documents

- `README.md` — 프로젝트 한 페이지 요약
- `RESEARCH.md` — 연구 정본: 배경, 아키텍처, RM 명세, 실험/검증 계획

이전 문서들은 아래 archive로 보존했다.

```text
archive/docs-reorg-2026-07-01/
```

## Important local paths

```text
isppipeline/hls/                 Current HLS C-sim scaffold
isppipeline/baseline/            Historical/current baseline ISP references
isppipeline/proposal/            Historical proposal ISP references
archive/docs-reorg-2026-07-01/   Archived docs from the pre-reset structure
RESEARCH.md                      Current research and implementation source of truth
```

## Verification status

Current executable C-sim status before reset:

```text
cd isppipeline/hls
make verify
# DFXISP golden vector compare passed (832 pixels)
# DFXISP C-sim smoke tests passed
```

주의: 이 PASS는 현재 scaffold의 bit-exactness를 의미할 뿐, 새 RM 구조가 구현 완료되었다는 뜻은 아니다.

## Next implementation target

1. `RM_NORMAL_TONE`: normal gain + gamma, or identity bypass if not needed
2. `RM_LOW_LIGHT_TONE`: `2x2 binning + gain + gamma`
3. `baseline_isp_core`: shared ISP core without duplicated gain/gamma
4. `checker`: dark-scene trigger, hysteresis 포함
5. `mode controller`: mutually exclusive RM selection; dark trigger 시 low-light tone RM active
6. Python golden + HLS C-sim fixtures: bright → dark → bright sequence
