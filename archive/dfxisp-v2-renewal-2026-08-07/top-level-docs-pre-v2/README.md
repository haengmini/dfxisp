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
updated: 2026-08-04
---

# DFXISP

DFXISP는 Zynq UltraScale+ ZCU104에서 **static shell(ISP 연산이 없는 AXI/체커/DFX 컨트롤러)** 위에 조도 조건에 따라 상호배타로 스왑되는 **mode-specific 전체 ISP pipeline RM**(`RM_NORMAL`/`RM_LOW_LIGHT`, 각각 demosaic→BLC→WB/AWB→CCM→gain→gamma를 통째로 소유)을 얹는 Dynamic Function eXchange 기반 AI-ISP 연구 프로젝트다. baseline core는 두 RM 사이에 하드웨어로 공유되지 않는다(소스 함수 `apply_blc_wb12()`만 공유 — 실리콘에는 RM마다 중복 구현, `SPEC.md` §7 "RP 경계"). 평상시에는 `RM_NORMAL`, 어두운 환경에서는 `RM_LOW_LIGHT`를 (체커가 판단해) 트리거한다.

## 연구 목표 (정본: RESEARCH.md §1)

컴퓨터 비전(CV) 검출기는 조도에 따라 다른 전처리를 요구한다. 하나의 static ISP로 밝은·어두운 장면을 모두 처리하면 저조도에서 CV 성능·효율이 떨어진다. 따라서:

- **목표 1 — 필요성:** 저조도에 특화된 ISP 모듈이 CV에 더 적합하다. 단일 모듈은 각각 **자기 조건의 데이터셋에서 상대 모듈보다 높은 성능**을 낸다(normal→밝은 조도, low-light→저조도). 한 모듈로 두 조건을 다 이기지 못하므로 전환이 필요하다.
- **목표 2 — 전환:** 상황에 맞춰 모듈을 전환(adaptive)하고, 이를 **DFX 부분재구성**으로 구현해 always-on 대비 **자원·전력 효율**까지 얻는다.

**증명 순서: SW(golden/mAP)로 필요성·전환을 먼저 확립 → HW(HLS→DFX→보드)로 이식**, HW/보드의 고유 기여는 효율이다. CV 성능 비교 arm은 **`normal`/`lowlight`/`adaptive`** 세 가지이며, 색보정을 거치지 않는 `none`(무처리)은 배포 가능한 ISP 출력이 아니므로 **비교에서 제외**한다.

## Active architecture

```text
Input real-RAW Bayer (PASCAL RAW 밝음 / LOD RAW 저조도; 초기엔 pseudo-RAW proxy)
  -> Scene checker (static shell, ISP 연산 없음)
       - 평상시: RM_NORMAL 트리거
       - 어두운 환경: RM_LOW_LIGHT 트리거
  -> Mutually exclusive 전체 ISP pipeline RM (RP가 통째로 스왑)
       RM_NORMAL:     demosaic -> BLC -> AWB/CCM -> gain 1.25x -> gamma
       RM_LOW_LIGHT:  2x2 binning-demosaic -> BLC(완화) -> AWB/CCM -> gain 2.0x -> gamma
  -> RGB32 pack / DPU-facing output
```

핵심 원칙:

1. **Static shell에는 ISP 데이터패스가 없다.** static은 AXI/제어, checker/mode-FSM, DFX/PR 컨트롤러, output/metadata packer뿐이다. baseline core(BLC/AWB/demosaic/CCM)를 static·공유 하드웨어로 두지 않기로 결정했다(2026-07-10 reset v2, 이유는 `RESEARCH.md` §0) — 두 RM이 그 값보다 훨씬 작으면 always-on(Arm2)과 자원 차이가 거의 없어 DFX 채택 근거 자체가 약해지기 때문.
2. **각 RM(`RM_NORMAL`/`RM_LOW_LIGHT`)이 자기 파이프라인 전체(demosaic→BLC→AWB/CCM→gain→gamma)를 통째로 소유한다.** 두 RM이 호출하는 `apply_blc_wb12()`는 **소스 레벨에서만** 같은 함수 정의고(BLC/WB 산술의 bit-exact 일치 보장 목적), 합성 시 RM마다 독립적으로 중복 구현된다 — 실리콘에 공유 인스턴스는 없다(`SPEC.md` §7 "RP 경계", §11.12).
3. **RM_NORMAL과 RM_LOW_LIGHT는 mutually exclusive다** — 프레임/세그먼트당 정확히 하나만 상주·활성.
4. **Checker가 어두운 장면을 감지했을 때만 RM_LOW_LIGHT를 트리거한다.**
5. **RM_LOW_LIGHT의 저조도 특화 요소는 `2x2 binning-demosaic + 완화 BLC + gain 2.0x`다.** 이득 귀속(기대 vs 실측)은 `results/lowlight-module-techniques-2026-07-10.md` — 주효인은 완화 BLC, binning은 real-RAW에서 조건부, 별도 톤 LUT는 기각.
6. DFX 실증 전에는 C-Sim/Python golden으로 산술 정합을 먼저 고정한다.

## Current status (2026-08-04)

- **SW 트랙 (Stage 0~3): 절차 완료, real-RAW 기준으로 동결** — golden/baseline core, checker(+principled-v3 SOTA 후속), tone RM 산술+이득귀속, mAP 평가. **Stage 3 "정확도 재검증 허브"**가 2026-07-20에 한 바퀴 완주했다 — 정본 데이터셋(LOD=SonyNOD/PASCAL=PASCALRAW real-RAW, Shuffle_split 642장) 교차검증 완료, 그 실측 근거로 **BLC 재보정(16/8→2/2) 배포**. 정성적 결론(저조도 모듈이 dark 조건에서 normal 상회)은 견고하게 재확인됨.
- **Checker: SOTA 강화 4개 관문 전부 완료(2026-07-20)** — C0(dark50>0.80)→**C1(dark16>0.62) 정식 배포**, 오라클 라벨 재정의로 잔존오차의 89.6%가 라벨 아티팩트임을 확인해 **C1 재조정 불필요**로 결론. 상세: `isppipeline/hls/results/checker-status-2026-07-10.md` §4.
- **HW 트랙 (Stage 4~5): 완료(한계 기록됨)** — Vitis HLS 합성 + C/RTL Co-sim, Vivado DFX 구현 + pr_verify + PR latency 분석. BLC/checker 상수 반영 **csynth/cosim 재실행 완료**(07-20, 자원·타이밍 완전 동일)와 **Vivado DFX fabric-only 재구현 완료**(08-01, pr_verify PASS·partition pin 3·bitstream 크기 일치).
- **3-arm 자원 비교 완성(2026-08-04)** — 비어 있던 Arm1 칸을 메우고 세 arm을 **post-route 축으로 통일**했다. 적응성의 비용은 Arm1 3,363 → Arm2 4,768 LUT(+41.8%)이고, **DFX는 Arm2 대비 normal 모드 −29.5%, low-light 모드 −50.8% LUT를 절감**한다(모두 동일 래퍼·플로우로 배치·배선한 실측). 상세: `SPEC.md` §10.1~§10.3.
- **색보정 상수의 모드별 분리: 두 건 모두 기각(2026-08-04 확정)** — BLC는 모드별 배포 후 real-RAW 재보정에서 양쪽 2로 수렴(07-20), WB는 real-RAW 분리 재튜닝에서 mAP 무반응으로 기각(08-03). 두 모드의 실질적 차이는 **색보정 상수가 아니라 구조**(binning, 노출 게인)에 있다. 상세: `isppipeline/hls/results/lowlight-wb-mode-split-2026-08-03.md`.
- **Stage 6 (보드 실장 + DPU end-to-end): 미착수** — 실물 ZCU104 필요, **보드 없이 할 수 있는 절차 중 유일하게 남은 것**. 목표 2의 효율(전력) 실증이 여기 걸림.
- 실제 진행은 선형이 아니라 **나선형**(Stage 5까지 올라갔다 SW Stage 3으로 되돌아오는 되먹임 반복) — 상세는 `ROADMAP.md`.

## Next direction

**즉시:** (1) YOLOv8s 교차 모델 검증 결과 회수·정리(노트북 RTX 5060에 인수인계, 진행 중), (2) SSDLite 교차검증(글루 코드 필요). 둘 다 이미 배포된 결정을 막지 않으며 논문 일반화 주장 보강용이다. 그 다음은 **Stage 6(보드) 착수** — 선결 과제는 PR 컨트롤러 통합(`drain_ready`를 실제 RM `ap_idle`에 연결, ICAPE3/STARTUPE3 인스턴스화)이며, 이것이 유일한 진짜 blocking item이다.

**보류 중인 리팩토링 방향:** `STRATEGY.md`가 제안한 **Vitis Vision Library 기준 baseline + DFXISP 확장 모듈** 구조(Vitis Base를 고정하고 Check/Dark/DFX Ctrl을 확장)는 2026-07-03에 제안됐으나 **아직 착수되지 않았다** — checker/BLC real-RAW 재보정 트랙이 우선됐다. 착수 여부·시점은 미결정.

## Active documents

- `README.md` — 프로젝트 한 페이지 요약 (이 문서)
- `RESEARCH.md` — 연구 정본: 배경, 아키텍처, RM 명세, 실험/검증 계획
- `SPEC.md` — 시스템 사양서: 입력 데이터셋 → checker → mode-specific 전체 ISP pipeline RM → RGB32 출력 → 평가
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

`reports/latest.md` 기준: golden PASS, C-sim PASS, 아키텍처 gate 6종 PASS — 그중 "shared baseline core"는 **하드웨어 공유가 아니라 두 RM의 BLC/WB 소스 함수가 bit-exact로 일치하는지 보는 산술 회귀 게이트**다(실제 RP 경계는 `SPEC.md` §7 참고). 나머지: RM 2종 존재 / 상호배타 선택 / gain·gamma 중복없음 / 형상정책.

## Related locations

- GitHub (code source of truth): https://github.com/haengmini/dfxisp
- Google Drive 백업: `내 드라이브/Agent OS/06-production/DFXISP/` (dataset zip, 모델 weights, 다이어그램, lit-reviews 포함)
