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
updated: 2026-07-20
---

# DFXISP

DFXISP는 Zynq UltraScale+ ZCU104에서 **shared baseline ISP core**를 공통 경로로 유지하고, 조도 조건에 따라 **mode-specific tone Reconfigurable Module(RM)** 을 선택하는 Dynamic Function eXchange 기반 AI-ISP 연구 프로젝트다. 평상시에는 `RM_NORMAL_TONE`, 어두운 환경에서는 `RM_LOW_LIGHT_TONE`을 (체커가 판단해) 트리거한다.

## 연구 목표 (정본: RESEARCH.md §1)

컴퓨터 비전(CV) 검출기는 조도에 따라 다른 전처리를 요구한다. 하나의 static ISP로 밝은·어두운 장면을 모두 처리하면 저조도에서 CV 성능·효율이 떨어진다. 따라서:

- **목표 1 — 필요성:** 저조도에 특화된 ISP 모듈이 CV에 더 적합하다. 단일 모듈은 각각 **자기 조건의 데이터셋에서 상대 모듈보다 높은 성능**을 낸다(normal→밝은 조도, low-light→저조도). 한 모듈로 두 조건을 다 이기지 못하므로 전환이 필요하다.
- **목표 2 — 전환:** 상황에 맞춰 모듈을 전환(adaptive)하고, 이를 **DFX 부분재구성**으로 구현해 always-on 대비 **자원·전력 효율**까지 얻는다.

**증명 순서: SW(golden/mAP)로 필요성·전환을 먼저 확립 → HW(HLS→DFX→보드)로 이식**, HW/보드의 고유 기여는 효율이다. CV 성능 비교 arm은 **`normal`/`lowlight`/`adaptive`** 세 가지이며, 색보정을 거치지 않는 `none`(무처리)은 배포 가능한 ISP 출력이 아니므로 **비교에서 제외**한다.

## Active architecture

```text
Input real-RAW Bayer (PASCAL RAW 밝음 / LOD RAW 저조도; 초기엔 pseudo-RAW proxy)
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

1. **Shared baseline ISP core는 공통 후단 경로다** — 단, 이 "공유"는 **소스 레벨**이다. 한 개의 `apply_blc_wb12()` 정의를 두 경로가 호출해 BLC/WB 산술의 bit-exact 일치를 보장한다는 뜻이며, **하드웨어 자원 공유가 아니다**. 합성된 RP는 모드별 전체 파이프라인을 감싸므로 실리콘에는 BLC/WB가 RM마다 중복 구현된다(`SPEC.md` §7 "RP 경계", §11.12).
2. **Gain/gamma는 baseline core에 중복 배치하지 않고 mode-specific tone RM으로 분리한다.** (C-sim 아키텍처 게이트가 이 소스 레벨 계약을 검증한다.)
3. **Normal tone RM과 low-light tone RM은 mutually exclusive다.**
4. **Checker가 어두운 장면을 감지했을 때만 low-light tone RM을 트리거한다.**
5. **Low-light tone RM은 `binning + gain + gamma + 완화 BLC`다.** 이득 귀속(기대 vs 실측)은 `results/lowlight-module-techniques-2026-07-10.md` — 주효인은 완화 BLC, binning은 real-RAW에서 조건부, 별도 톤 LUT는 기각.
6. DFX 실증 전에는 C-Sim/Python golden으로 산술 정합을 먼저 고정한다.

## Current status (2026-08-04)

- **SW 트랙 (Stage 0~3): 절차 완료, real-RAW 기준으로 동결** — golden/baseline core, checker(+principled-v3 SOTA 후속), tone RM 산술+이득귀속, mAP 평가. **Stage 3 "정확도 재검증 허브"**가 2026-07-20에 한 바퀴 완주했다 — 정본 데이터셋(LOD=SonyNOD/PASCAL=PASCALRAW real-RAW, Shuffle_split 642장) 교차검증 완료, 그 실측 근거로 **BLC 재보정(16/8→2/2) 배포**. 정성적 결론(저조도 모듈이 dark 조건에서 normal 상회)은 견고하게 재확인됨.
- **Checker: SOTA 강화 4개 관문 전부 완료(2026-07-20)** — C0(dark50>0.80)→**C1(dark16>0.62) 정식 배포**, 오라클 라벨 재정의로 잔존오차의 89.6%가 라벨 아티팩트임을 확인해 **C1 재조정 불필요**로 결론. 상세: `isppipeline/hls/results/checker-status-2026-07-10.md` §4.
- **HW 트랙 (Stage 4~5): 완료(한계 기록됨)** — Vitis HLS 합성 + C/RTL Co-sim, Vivado DFX 구현 + pr_verify + PR latency 분석. BLC/checker 상수 반영 **csynth/cosim 재실행 완료**(07-20, 자원·타이밍 완전 동일)와 **Vivado DFX fabric-only 재구현 완료**(08-01, pr_verify PASS·partition pin 3·bitstream 크기 일치).
- **색보정 상수의 모드별 분리: 두 건 모두 기각(2026-08-04 확정)** — BLC는 모드별 배포 후 real-RAW 재보정에서 양쪽 2로 수렴(07-20), WB는 real-RAW 분리 재튜닝에서 mAP 무반응으로 기각(08-03). 두 모드의 실질적 차이는 **색보정 상수가 아니라 구조**(binning, 노출 게인)에 있다. 상세: `isppipeline/hls/results/lowlight-wb-mode-split-2026-08-03.md`.
- **Stage 6 (보드 실장 + DPU end-to-end): 미착수** — 실물 ZCU104 필요, **보드 없이 할 수 있는 절차 중 유일하게 남은 것**. 목표 2의 효율(전력) 실증이 여기 걸림.
- 실제 진행은 선형이 아니라 **나선형**(Stage 5까지 올라갔다 SW Stage 3으로 되돌아오는 되먹임 반복) — 상세는 `ROADMAP.md`.

## Next direction

**즉시:** (1) YOLOv8s 교차 모델 검증 결과 회수·정리(노트북 RTX 5060에 인수인계, 진행 중), (2) SSDLite 교차검증(글루 코드 필요). 둘 다 이미 배포된 결정을 막지 않으며 논문 일반화 주장 보강용이다. 그 다음은 **Stage 6(보드) 착수** — 선결 과제는 PR 컨트롤러 통합(`drain_ready`를 실제 RM `ap_idle`에 연결, ICAPE3/STARTUPE3 인스턴스화)이며, 이것이 유일한 진짜 blocking item이다.

**보류 중인 리팩토링 방향:** `STRATEGY.md`가 제안한 **Vitis Vision Library 기준 baseline + DFXISP 확장 모듈** 구조(Vitis Base를 고정하고 Check/Dark/DFX Ctrl을 확장)는 2026-07-03에 제안됐으나 **아직 착수되지 않았다** — checker/BLC real-RAW 재보정 트랙이 우선됐다. 착수 여부·시점은 미결정.

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
