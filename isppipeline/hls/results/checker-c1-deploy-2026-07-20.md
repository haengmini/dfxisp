<!--
=============================================================================
File   : isppipeline/hls/results/checker-c1-deploy-2026-07-20.md
Date   : 2026-07-20 KST
Function: checker-status-2026-07-10.md §4 관문 4 실행 기록 -- C1 운영점
          (dark16 ratio > 0.62) 정식 배포. adaptive-τ가 아니라 C1을 택한
          이유, 코드 변경, bit-exact 검증, 실데이터 321+321장 대조 결과.
Sources: checker-status-2026-07-10.md §1/§4 (C1 정의·배포 조건),
         pascalraw-adapter-2026-07-13.md §7 (false-trigger 실측),
         checker-adaptive-tau-realdata-2026-07-13.md (recall 실측),
         lod-pascal-isp-simulation-2026-07-15.md (mAP 실측, adaptive 근소우위),
         src/dfxisp_accel.cpp, tools/checker.py, tools/gen_golden_vectors.py,
         tests/test_dfxisp_csim.cpp
=============================================================================
-->
# Checker C1 정식 배포 — dark50>0.80 → dark16>0.62 (2026-07-20, 관문 4)

## 0. 결론부터

`checker-status-2026-07-10.md` §4 관문 4를 실행했다. 배포 checker 규칙을
**C0(dark50 ratio > 0.80)에서 C1(dark16 ratio > 0.62)로 전환**:

- HW: `DARK_RATIO_PCT` 80 → 62 (컴파일 상수 1개). RTL 구조 변경 0.
- 드라이버: `dark_pixel_threshold` AXI-lite 레지스터에 **256**(= 16<<4,
  raw12 도메인) 기록 — 이 레포에 드라이버 코드는 없으므로 소스 주석과 이
  문서에 규약으로 명시.
- SW 미러(`checker.py`)를 C1으로 갱신하면서 **HW 정합성도 개선**(§3).
- golden 재생성 + `make verify`/`py-verify`/`rm-verify` 전부 통과, 실
  센서 RAW 642장(SonyNOD 321 + PASCALRAW 321)에서 manifest 사전계산
  dark16/C1 verdict와 **최대 오차 0.0, 판정 불일치 0건**.

## 1. 왜 adaptive-τ가 아니라 C1인가

관문 4의 선택지는 "C1 또는 재보정 τ"였다. C1을 택한 근거:

1. **adaptive-τ의 ISO[800,1600) 역전 미해명** — PASCALRAW n=28 구간에서
   adaptive FT 96.4% > C1 32.1%(`pascalraw-adapter-2026-07-13.md` §7).
   checker-status §4도 "역전 원인 규명 후 배포 권장"이라 명시했다.
2. **실전 이득이 근소** — 07-15 mAP 캠페인에서 adaptive-τ는 lowlight 강제
   arm 대비 "동등~근소 우위"(BLC=2에서만 +0.0002)에 그쳤다. 판정 지표
   개선(FT 41.8→38.4%)이 mAP 이득으로 이어진다는 증거가 아직 없다.
3. **배포 복잡도 차이** — C1은 상수 1개 + 레지스터값 1개. adaptive-τ는
   프레임별 EXIF(ISO/노출) 기반 τ 계산을 드라이버가 수행해야 하며(Path A),
   이 레포에는 그 드라이버 실행 경로 자체가 없다.

adaptive-τ는 SW 실험 코드(`checker_adaptive_tau.py`)로 유지하고, 역전
규명 후 재검토한다. C1 배포는 τ 배포의 전제를 깨지 않는다 — τ Path A도
같은 레지스터에 값만 다르게 쓰는 구조라, 이후 전환 시에도 RTL 변경은 없다.

## 2. C1이 C0를 지배한다는 근거 (기존 실측 요약)

| | C0(구 배포) | C1(신 배포) |
|---|---|---|
| 규칙 | dark50 ratio > 0.80 | dark16 ratio > 0.62 |
| recall (pseudo-RAW 보정) | 0.918 | **0.936** |
| false-trigger (동) | 0.125 | **0.089** |
| Youden J | 0.793 | **0.847** (사후확률 중립점, 강화안 #6 독립 확인) |
| PASCALRAW 실측 FT (4,259장 전수) | 92.91% | **41.82%** |
| HW 비용 | 1 비교기 + 1 카운터 | **동일 RTL** |

관문 1(실 RAW 확보)·관문 3(ISO 층화 recall/FT 실측) 완료로 "실센서
재확인 후 배포" 조건이 충족된 상태였다.

## 3. 변경 내용

| 파일 | 변경 |
|---|---|
| `src/dfxisp_accel.cpp` | `DARK_RATIO_PCT` 80 → 62 + 주석(레지스터값 256 규약 포함) |
| `tools/gen_golden_vectors.py` | 미러 상수 80 → 62, 경계 케이스 75%/86% → 60.9%/62.5%(39/64, 40/64) |
| `tests/test_dfxisp_csim.cpp` | 경계 스모크 assert 동일 갱신 |
| `tools/checker.py` | C1로 전환 + **정합성 개선(아래)** |
| `tools/eval_map_isp.py` | 주석/`--help`의 "deployed C0" 표기 갱신(동작 무변경) |

**checker.py 정합성 개선**: 구 구현은 demosaic 후 luminance<50 근사로 HW를
흉내냈다 — HLS `checker_select_mode`는 **raw Bayer 픽셀을 레지스터와 직접
비교**하고, C1 임계(0.62)의 보정 자체도 raw 도메인 dark16 통계
(`checker_stat_sweep`) 위에서 이뤄졌다. 이번에 `selected_mode`를 raw 도메인
비교(`bayer16 < 16<<8`, strict)로 바꿔 HW·보정 도메인과 정확히 일치시켰다.
demosaic 헬퍼는 cross-check 스크립트용으로 유지(무변경).

Schmitt δ=2%p 히스테리시스는 C1 스펙의 시간축 성분으로 **드라이버측 정책**
(mode FF 1개, `tools/scheduler_sim.py`의 plus_hysteresis 정책과 동형)이다.
단일 프레임 HLS 규칙은 순수 임계 비교 그대로다.

## 4. 검증 (전부 통과, 2026-07-20 데스크톱)

1. `make verify` — golden 재생성(13 cases) → csim **bit-exact 726픽셀 통과**
   (신규 경계 케이스 39/64→NORMAL, 40/64→LOW_LIGHT 포함) + cross-check 2종.
2. `make py-verify` — tools/*.py 전체 컴파일 + edge/boundary 스모크 통과.
3. `make rm-verify` — mismatch=0 (톤 RM은 checker와 무관, 예상대로).
4. **실데이터 대조 (이번 배포의 핵심 검증)**: 새 `checker.py`의
   dark_ratio/verdict를 07-15 manifest의 사전계산 `dark16`/
   `c1_verdict_lowlight`와 프레임별 대조 —
   - LOD_split(SonyNOD 321장, 실 `.ARW` 유래): max|diff| = 0.0, 불일치 0
   - PASCAL_split(PASCALRAW 321장, 실 `.NEF` 유래): max|diff| = 0.0, 불일치 0,
     C1 FT 142/321(44.2%) — ISO 층화 샘플에서 전수 실측 41.8%와 정합.

## 5. 남은 것

- **csynth/cosim 재실행** — BLC 재보정 건과 묶어서 비트스트림 배포 전 1회
  (상수만 변경이라 자원 영향 없음 예상, `build/vitis_hls`는 아직 구 상수).
- **드라이버 레지스터값** — 실 보드 배포 시 `dark_pixel_threshold=256` 기록
  + Schmitt δ=2%p 정책 구현(레포 밖 사안, 규약만 여기 고정).
- **관문 2(오라클 라벨)** — 유일하게 남은 관문. 07-15 캠페인의 27개 조합
  dual-arm 렌더 결과가 재료를 상당 부분 이미 제공.
- **adaptive-τ 재검토 게이트** — ISO[800,1600) 역전(n=28) 원인 규명이 선행
  조건. 규명 전까지 τ는 실험 코드 유지.
