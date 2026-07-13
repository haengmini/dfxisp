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
updated: 2026-07-10
---

# DFXISP

DFXISP는 Zynq UltraScale+ ZCU104에서 **static shell(checker + DFX 컨트롤러 + AXI + packer, ISP 연산 없음)**을 얇게 유지하고, 조도 조건에 따라 **전체 ISP pipeline 단위의 Reconfigurable Module(RM)** 을 통째로 교체하는 Dynamic Function eXchange 기반 AI-ISP 연구 프로젝트다. 평상시에는 stock Vitis Vision 기준 `RM_NORMAL`, 어두운 환경에서는 저조도 특화 `RM_LOW_LIGHT`를 (체커가 판단해) 트리거한다.

> **아키텍처 reset (2026-07-10, v2):** 이전 버전(v1)은 "공유 baseline ISP core + 작은 tone RM(gain/gamma만 swap)" 구조였다. v2는 RM 경계를 ISP 데이터패스 전체(BLC/AWB/demosaic/CCM/gain/gamma)로 넓혀 static 공유 스테이지를 없앤다 — 스왑 단위가 커야 DFX의 자원/전력 이득(목표 2)이 register-only 대비 실질적으로 방어된다. 상세: `RESEARCH.md` §0. 현재 코드(`isppipeline/hls/`)는 아직 v1이며, 마이그레이션은 다음 단계다.

## 연구 목표 (정본: RESEARCH.md §1)

컴퓨터 비전(CV) 검출기는 조도에 따라 다른 전처리를 요구한다. 하나의 static ISP로 밝은·어두운 장면을 모두 처리하면 저조도에서 CV 성능·효율이 떨어진다. 따라서:

- **목표 1 — 필요성:** 저조도에 특화된 ISP 모듈이 CV에 더 적합하다. 단일 모듈은 각각 **자기 조건의 데이터셋에서 상대 모듈보다 높은 성능**을 낸다(normal→밝은 조도, low-light→저조도). 한 모듈로 두 조건을 다 이기지 못하므로 전환이 필요하다.
- **목표 2 — 전환:** 상황에 맞춰 모듈을 전환(adaptive)하고, 이를 **DFX 부분재구성**으로 구현해 always-on 대비 **자원·전력 효율**까지 얻는다.

**증명 순서: SW(golden/mAP)로 필요성·전환을 먼저 확립 → HW(HLS→DFX→보드)로 이식**, HW/보드의 고유 기여는 효율이다. CV 성능 비교 arm은 **`normal`/`lowlight`/`adaptive`** 세 가지이며, 색보정을 거치지 않는 `none`(무처리)은 배포 가능한 ISP 출력이 아니므로 **비교에서 제외**한다.

## Active architecture (v2, 2026-07-10 reset)

```text
Input real-RAW Bayer (PASCAL RAW 밝음 / LOD RAW 저조도; 초기엔 pseudo-RAW proxy)
  -> Scene checker                (static)
  -> DFX / PR controller          (static, selects RM)
  -> Mutually exclusive 전체 ISP pipeline RM
       RM_NORMAL:     stock Vitis Vision 기준 ISP pipeline
                       (BLC -> demosaic -> AWB/CCM -> gain -> gamma)
       RM_LOW_LIGHT:  저조도 특화 ISP pipeline
                       (2x2 binning-demosaic -> 완화 BLC -> AWB/CCM -> gain -> gamma)
  -> output / metadata packer     (static)
  -> RGB32 / DPU-facing output
```

핵심 원칙:

1. **Static shell은 ISP 연산을 전혀 포함하지 않는다.** Checker, DFX 컨트롤러, AXI wrapper, output/metadata packer만 static이다.
2. **BLC/AWB/demosaic/CCM/gain/gamma 전부를 각 RM이 통째로 소유한다.** v1의 "baseline core 공유 + tone RM만 분리" 구조와 de-dup 규칙은 폐기됐다(RESEARCH.md §0/§3).
3. **`RM_NORMAL`과 `RM_LOW_LIGHT`는 mutually exclusive한 전체 ISP pipeline이다.**
4. **Checker가 어두운 장면을 감지했을 때만 `RM_LOW_LIGHT`를 트리거한다.**
5. **`RM_LOW_LIGHT`는 `binning-demosaic + 완화 BLC + 저조도 AWB/CCM + gain + gamma`다.** 이득 귀속(기대 vs 실측)은 `results/lowlight-module-techniques-2026-07-10.md` — 주효인은 완화 BLC, binning은 real-RAW에서 조건부, 별도 톤 LUT는 기각. (이 실측은 v1 tone-RM 기준이며, v2 전체 파이프라인 RM으로 재확인 필요.)
6. DFX 실증 전에는 C-Sim/Python golden으로 산술 정합을 먼저 고정한다.
7. **v1 코드는 삭제하지 않고 `Ref`/ablation으로 보존한다** — v1 vs v2 자원·전력·mAP 비교 기준.

## Current status (2026-07-10)

- **SW 트랙 (Stage 0~3): 절차 완료, Stage 3 재검증 진행중** — golden/baseline core, checker(+principled-v3 SOTA 후속), tone RM 산술+이득귀속, mAP 평가. **Stage 3은 "정확도 재검증 허브"**로 되먹임마다 재진입한다 — 현재 demosaic 수정 반영(R5, GPU 대기)과 **정본 데이터셋(PASCAL RAW/LOD RAW) 재평가**가 미완. 정성적 결론(저조도 모듈이 dark 조건에서 normal 상회)은 견고.
- **HW 트랙 (Stage 4~5): 완료(한계 기록됨)** — Vitis HLS 합성 + C/RTL Co-sim, Vivado DFX 구현 + pr_verify + PR latency 분석.
- **Stage 6 (보드 실장 + DPU end-to-end): 미착수** — 실물 ZCU104 필요. 목표 2의 효율(전력) 실증이 여기 걸림.
- 실제 진행은 선형이 아니라 **나선형**(Stage 5까지 올라갔다 SW Stage 3으로 되돌아오는 되먹임 반복) — 상세는 `ROADMAP.md`.
- **아키텍처 reset v2(2026-07-10):** RM 경계가 tone에서 전체 ISP pipeline으로 넓어졌다(위 "Active architecture" 참고). Stage 0~5의 실측 수치는 전부 v1(공유 baseline core + tone RM) 기준이며, v2 마이그레이션 후 재검증이 필요하다 — 아직 코드 변경은 시작하지 않았다.

## Next direction

다음 리팩토링 방향은 **Vitis Vision Library 기준 ISP를 `RM_NORMAL`로 그대로 사용하고, 저조도 특화 ISP를 `RM_LOW_LIGHT`로 나란히 구현 + DFX가 그 둘을 통째로 swap** 하는 구조다. Check(checker)와 DFX Ctrl만 static으로 남고, Vitis Vision 기반 ISP(구 "Base")도 저조도 ISP(구 "Tone")도 둘 다 재구성 영역(RP) 안에 들어간다 — 어느 한쪽만 static으로 고정하지 않는다. 계획 전문은 `STRATEGY.md` 참조(2026-07-10 갱신: RP = Tone+Base 전체로 결정).

## Active documents

- `README.md` — 프로젝트 한 페이지 요약 (이 문서)
- `RESEARCH.md` — 연구 정본: 배경, 아키텍처(v2), RM 명세, 실험/검증 계획
- `SPEC.md` — 시스템 사양서: 현재(v1) 구현의 입력 데이터셋 → checker → tone RM → baseline core → RGB32 출력 → 평가 (v2 마이그레이션 전)
- `ROADMAP.md` — Stage 0~6 진행 상태 추적 (근거 문서 링크 포함)
- `STRATEGY.md` — Vitis-first 리팩토링 전략 (2026-07-10 갱신, 다음 구현 방향)

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

`reports/latest.md` 기준: golden PASS, C-sim PASS, 아키텍처 gate 6종 PASS (shared baseline core / RM 2종 / 상호배타 / gain·gamma 중복없음 / 형상정책). **이 gate는 v1(현재 코드) 기준** — v2로 마이그레이션하면 gate 정의도 RESEARCH.md §8.2에 맞춰 갱신한다.

## Related locations

- GitHub (code source of truth): https://github.com/haengmini/dfxisp
- Google Drive 백업: `내 드라이브/Agent OS/06-production/DFXISP/` (dataset zip, 모델 weights, 다이어그램, lit-reviews 포함)
