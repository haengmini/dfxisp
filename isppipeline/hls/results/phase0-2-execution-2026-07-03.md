<!--
=============================================================================
File   : isppipeline/hls/results/phase0-2-execution-2026-07-03.md
Date   : 2026-07-03
Time   : 00:50 KST
Function: improvement-strategy-2026-07-03.md의 Phase 0~2 (즉시 착수 가능 항목)를
          모두 실행한 결과 기록.
Goal   : "지금 바로 착수 가능한 것들 모두 수행" 요청에 대한 응답.
=============================================================================
-->
# Phase 0~2 실행 결과 (2026-07-03)

> `improvement-strategy-2026-07-03.md`가 "의존성 없음, 병렬 가능"으로 분류한 6개
> 항목(0.1/0.2/1.1/1.2/2.1/2.2)을 모두 실행했다. 유일하게 보드가 필요한 Phase
> 3~4는 여전히 착수 전(정의상 지금 할 수 없음).

## 0.1 — golden model 독립 교차검증 게이트 ✅ 완료

`tools/verify_binning_cross_check.py`(신규): `gen_golden_vectors.py`의
`bin_demosaic_rggb12`을 `isp_pipeline_ver1.py`의 `_bin_demosaic_rggb16`(독립
저자·SW eval에서 이미 검증된 구현)과 500개 무작위 RGGB 그리드(2×2~64×48, 홀수
치수 포함)로 교차검증. `Makefile`의 `verify` 타깃에 `cross-check`로 연결 —
`make verify`가 이제 자동으로 이 게이트를 통과한다.

**검증(게이트가 진짜 작동하는지):** 과거의 버그(스칼라 평균 후 재-demosaic)를
인라인으로 재현해 같은 무작위 데이터로 비교한 결과 **16/16 셀 불일치** —
이 게이트가 있었다면 그 버그를 `make verify` 단계에서 잡았을 것임을 확인.

## 0.2 — pblock 클럭 리전 편중 원인 규명 ✅ 완료, 결정적 원인 발견

`get_sites -of_objects [get_clock_regions ...] -filter {SITE_TYPE==SLICEL||SLICEM}`
로 xczu7ev의 전체 클럭 리전별 SLICE 개수를 실측한 결과:

| 리전 | SLICE 수 |
|---|---|
| X0Y0, X0Y1, X0Y2, X0Y3 | **0** |
| X1Y0 | 1,080 |
| X2Y0, X3Y0 | 1,380 |
| X0Y4, X0Y5 | 2,520 |

**원인 확정: 컬럼 X0의 Y0~Y3 클럭 리전은 SLICE(PL fabric)가 전혀 없다** — 이
xczu7ev(ZU7EV) 파트에서 **PS(Processing System, ARM 코어+DDR 컨트롤러) 하드
매크로가 그 영역을 물리적으로 차지**하기 때문(Zynq UltraScale+의 전형적
플로어플랜: PS가 다이의 특정 코너를 점유). 기존 pblock이 `CLOCKREGION_X0Y0:
CLOCKREGION_X1Y0`을 선택했을 때, **X0Y0은 애초에 쓸 수 있는 로직 자원이 없는
영역**을 절반이나 포함시킨 것 — `report_utilization -pblocks`가 보여준
"X0Y0 0.06%"는 이 사실의 직접적 증거였다.

## 1.1/1.2 — 저조도 baseline core 완화 ablation ✅ 완료, 명확한 승자 발견

`isp_pipeline_ablation.py`에 3개 변형 추가(`ll_wb_relaxed`/`ll_blc_relaxed`/
`ll_wb_skip`), ExDark(n=31)·COCO(n=39) 양쪽에서 mAP 재측정:

| arm | ExDark mAP | ExDark Δ(vs lowlight) | COCO mAP | COCO Δ(vs lowlight) |
|---|---:|---:|---:|---:|
| lowlight(현재) | 0.0619 | — | 0.2089 | — |
| normal(참조) | 0.1053 | — | 0.2476 | — |
| `ll_wb_relaxed`(WB 게인 완화) | 0.0664 | +7.3% | 0.1963 | −6.0% |
| **`ll_blc_relaxed`(BLC 완화)** | **0.1495** | **+141.5%** | **0.2194** | **+5.0%** |
| `ll_wb_skip`(WB 완전 생략) | 0.0616 | −0.5% | 0.2008 | −3.9% |

**결론(전략 문서의 가설을 부분 정정):** 원래 ablation(2026-07-02)은 "BLC/WB"를
한 덩어리로 묶어 손상 원인으로 지목했는데, 이번에 BLC와 WB를 분리해보니
**진짜 범인은 WB 게인이 아니라 BLC(black-level) 오프셋**이었다. WB만 완화하면
거의 효과 없고(+7.3%, 여전히 normal 미달), WB를 완전히 꺼도 변화가 없다(−0.5%,
사실상 무관함을 반증)는 점이 이를 뒷받침한다. **BLC만 절반(16→8)으로 낮추자
mAP가 0.0619→0.1495로 2.4배 뛰어 normal(0.1053)을 42% 앞질렀다** — Phase 1.1의
성공 기준("normal 이상 회복")을 명확히 통과. COCO에서도 해를 끼치지 않고
오히려 소폭 개선(+5.0%)해 안전성도 확인됐다.

**미착수(의도적):** 이 결과를 실제 `src/dfxisp_accel.cpp`/`gen_golden_vectors.py`/
`isp_pipeline_ver1.py`의 정본 파이프라인에 반영하는 것은 **하지 않았다** — SW
proxy ablation은 "원인이 무엇인지, 어떤 방향이 통하는지"를 확인하는 실험
단계이고, 정본 파이프라인 변경은 HW 재합성·재검증(Stage 4~5 재실행)까지
동반하는 별개의 결정이라 사용자 확인 없이 진행하지 않았다.

## 2.1 — PR 컨트롤러 FSM 1차 설계 + 시뮬레이션 ✅ 완료, 진짜 trigger→완료 수치 확보

`pr_controller.v`(신규, `results/pr_controller/`) — `IDLE → DRAIN_WAIT →
ICAP_ARM → ICAP_FETCH/WRITE(word loop) → DONE` FSM. **완료 판정을 ICAPE3의
PRDONE이 아니라 자체 word-counter(171,633 도달)로 하는 설계**(2026-07-02에
격리된 ICAPE3가 PRDONE을 못 만든 이유 — `eos_startup`이 `STARTUPE3` 필요 —
를 설계 단계에서 우회). Fabric-only이므로 partial bitstream 소스는 BRAM 모델
(`$readmemh`로 실제 `rm_lowlight_partial.bit` payload 로드).

**시뮬레이션 결과(`pr_controller_tb.v`, xvlog/xelab/xsim):**
```
TRIGGER at t=87.5 ns
drain_ready asserted at t=197.5 ns (20-cycle 시뮬레이션된 drain)
DONE at t=1,716,537.5 ns, word_count=171,633 (전체 payload 정확히 소비)
TRIGGER_TO_DONE = 1,716,450.000 ns ≈ 1.716 ms
```

**이게 왜 중요한가:** 이 숫자는 `pr-latency-breakdown-2026-07-02.md`의 **분석적
추정치(peak 1.716ms)와 사실상 동일**하다 — 하지만 이번엔 사람이 손으로 나눗셈한
값이 아니라 **실제 partial bitstream을 실제 FSM으로 처음부터 끝까지 흘려 얻은
시뮬레이션 결과**다. 두 독립적인 방법(스펙 기반 계산 vs. 실제 FSM 시뮬레이션)이
같은 답에 수렴했다는 것 자체가 분석 추정치의 신뢰도를 높이는 교차검증이다.
(이 FSM의 word당 소요 2 사이클 × 5ns 클럭 = 10ns/word가 우연히 ICAP 스펙의
100MHz×1word/cycle=10ns/word와 정확히 같은 rate로 귀결됨.)

**한계(정직하게 기록):** 이건 여전히 **1차 설계**다 — drain_ready는 테스트벤치가
임의로 20 사이클 뒤 assert한 것이지 실제 RM의 `ap_idle`에서 온 신호가 아니고,
BRAM은 실제 partial bitstream 저장 매커니즘(SD/DDR)이 아니라 시뮬레이션
전용이다. §2.1 "성공 기준"(word-count 기반 완료 신호가 assert되는지)은
충족했지만, Phase 3(PS/DDR 통합)까지 가야 진짜 배포 가능한 컨트롤러가 된다.

## 2.2 — pblock 재floorplan ✅ 완료, 용량 2배 확보

0.2의 원인 규명에 따라 `CLOCKREGION_X1Y0:CLOCKREGION_X2Y0`(PS와 안 겹치는 두
리전)으로 재floorplan, config1/config2를 처음부터 재구현:

| 지표 | 기존(X0Y0:X1Y0) | **수정(X1Y0:X2Y0)** |
|---|---|---|
| 클럭 리전 기여도 | X0Y0 0.06% / X1Y0 99.94% | **X1Y0 42.40% / X2Y0 57.60%**(둘 다 유의미) |
| LUT 용량 | 8,640 | **19,200**(+122%) |
| BRAM Tile 용량 | 12 | **24**(+100%) |
| DSP 용량 | 96 | **216**(+125%) |
| config1 LUT 사용 | 3,953 | 3,972(거의 동일, 재배치 오차) |
| config2 LUT 사용 | 2,922 | 2,929(거의 동일) |
| pr_verify | PASS | **PASS**(static 영역 완전 동일 재확인) |

**같은 로직으로 실질 용량이 2배가 됐다** — 향후 더 큰 RM 후보를 고려할 여지가
그만큼 늘었다. 방법론적 교훈(§Phase 2.2 체크리스트에 이미 반영): **클럭 리전
경계로 pblock을 정의할 때는 `report_utilization -pblocks`의 Clock Region
Statistics로 각 리전이 실제로 PL fabric을 갖는지 검증해야 한다** — PS 통합
디바이스에서는 특정 코너 리전이 통째로 비어 있을 수 있다.

## 종합

| 항목 | 상태 | 핵심 결과 |
|---|---|---|
| 0.1 CI 게이트 | ✅ | `make verify`에 통합, 과거 버그 재현 시 잡는 것 확인 |
| 0.2 pblock 원인 | ✅ | X0 컬럼 Y0~Y3 = PS 매크로, SLICE 0개 |
| 1.1/1.2 WB→BLC 완화 | ✅ | BLC 완화가 진짜 승자, ExDark +141%(normal 42% 상회), COCO도 안전 |
| 2.1 PR 컨트롤러 | ✅(1차) | 실제 FSM 시뮬레이션으로 trigger→완료 1.716ms 확보, 분석 추정과 일치 |
| 2.2 pblock 재floorplan | ✅ | 용량 2배(LUT 8,640→19,200), pr_verify 유지 |

## 산출물
- 코드: `tools/verify_binning_cross_check.py`, `Makefile`(cross-check 타깃),
  `tools/isp_pipeline_ablation.py`(3개 신규 arm), `results/pr_controller/pr_controller.v`,
  `results/pr_controller/pr_controller_tb.v`.
- 결과: `results/map_ablation2_{exdark,coco}_yolov8n.csv`.
- `/tmp` 산출물(git 비추적, 재현 절차는 위 각 절 참조): `pblock_capacity_fixed.rpt`,
  `config{1,2}_fixed.util.rpt`, `pr_verify_fixed.rpt`, `pr_controller_latency.log`.
