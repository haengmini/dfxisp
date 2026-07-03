# results/ INDEX — 실험·시뮬레이션 산출물 카탈로그

**갱신:** 2026-07-03 · 이 폴더의 모든 파일을 주제별로 분류한 탐색용 인덱스.
정본 요약은 `ROADMAP.md`(진행 상태) / `SPEC.md`(사양) 참조. 파일은 인용 링크 보존을 위해 이동하지 않고 여기서 색인만 한다.

## 읽는 순서 (처음 오면 이 4개부터)

| 파일 | 내용 |
|---|---|
| `experiment-stages-2026-07-02.md` | Stage 0~6 정본 실험 계획 |
| `experiment-report-2026-07-02.md` | 조건→결과 종합 실험 보고서 |
| `design-limitations-2026-07-03.md` | 설계 한계 종합 (정직한 기록) |
| `improvement-strategy-2026-07-03.md` | 개선 전략 (한계 + DFX 고려사항 종합) |

## 1. 계획/전략 문서

| 파일 | 날짜 | 상태 |
|---|---|---|
| `experiment-plan-2026-07-01.md` | 07-01 | superseded → `experiment-stages-2026-07-02.md` |
| `experiment-stages-2026-07-02.md` | 07-02 | **정본** Stage 0~6 계획 |
| `improvement-strategy-2026-07-03.md` | 07-03 | **정본** 개선 전략 |

## 2. SW 트랙 결과 (Stage 0~3)

| 파일 | 날짜 | 내용 |
|---|---|---|
| `stage1-3-results-2026-07-02.md` | 07-02 | Stage 1~3 SW 실측 (checker/RM/mAP) |
| `experiment_ver1_2026-07-02.md` | 07-02 | ver1 파이프라인 (RAW-domain-first) |
| `experiment_ver2_2026-07-02.md` | 07-02 | ver2 checker dark-level 재보정 |
| `lowlight-rm-map-rootcause-2026-07-02.md` | 07-02 | low-light RM mAP 미개선 원인 ablation |
| `phase0-2-execution-2026-07-03.md` | 07-03 | 개선전략 Phase 0~2 실행 결과 |
| `isp_analysis.md` / `isp_analysis.csv` | 06-29 | ISP variant proxy 분석 (detector 없음) |
| `11-ssd-crosscheck-2026-06-29.md` | 06-29 | SSD 2차 detector 교차검증 |

## 3. HW 트랙 결과 (Stage 4~5)

| 파일 | 날짜 | 내용 |
|---|---|---|
| `10-hw-csynth-resource-2026-06-29.md` | 06-29 | 초기 C-합성 자원 (구 스캐폴드 기준) |
| `stage4-hw-synthesis-2026-07-02.md` | 07-02 | **정본** Stage 4 HLS 합성 실측 |
| `stage5-dfx-implementation-2026-07-02.md` | 07-02 | **정본** Stage 5 Vivado DFX 구현 |
| `pr-latency-breakdown-2026-07-02.md` | 07-02 | PR latency 단계별 분해 |
| `pr-latency-vivado-sim-2026-07-02.md` | 07-02 | XSIM 기반 ICAP PR latency 실측 시도 |
| `blc-fix-resynthesis-2026-07-03.md` | 07-03 | BLC 완화 반영 전체 재합성 |
| `cosim-waveform-analysis-2026-07-03.md` | 07-03 | C/RTL Co-sim 파형 분석 |
| `design-limitations-2026-07-03.md` | 07-03 | 설계 한계 종합 보고서 |
| `dfx-vivado-considerations-2026-07-03.md` | 07-03 | FPGA DFX 적용 고려사항 (Vivado 실측 기반) |
| `dfxisp-accel-connectivity-2026-07-03.md` | 07-03 | top-level 연결 테이블 (434 signal wires) |

## 4. 다이어그램 / RTL 부속물

| 파일 | 내용 |
|---|---|
| `dfxisp-microarchitecture-2026-07-02.svg` / `.drawio` | 마이크로아키텍처 다이어그램 (Arm2 vs Arm3) |
| `pr_controller/pr_controller.v` + `_tb.v` | PR 컨트롤러 1차 RTL + testbench |
| `icap_sim/icap_pr_latency_tb.v` | ICAP PR latency 측정용 testbench |

## 5. mAP CSV 계보 (시간순 — 어느 숫자가 최신인지)

측정 세대가 4번 바뀌었다. **최신 정본 수치는 G4 (`*_blcfix`)**, 그 이전은 계보 추적용.

```text
G1 (06-29, 구 스캐폴드):  map_dark, map_dark_full, map_real, map_real_full,
                          map_exdark, map_exdark_bilbin, map_coco_bilbin,
                          map_exdark_yolov8s, map_coco_ssd, map_exdark_ssd
G2 (07-01~02, reset 아키텍처 "newrm"):
                          map_newrm_{coco,exdark}_{yolov8n,yolov8s,ssd}
G3 (07-02, ver1/ver2 개정): map_ver1_{coco,exdark}_{yolov8n,yolov8s,ssd}
                          map_ver2_{coco,exdark}_yolov8n_adaptive
                          map_ablation_*, map_ablation2_* (원인분석 ablation)
G4 (07-03, BLC 완화 최종): map_ver1_coco_yolov8n_blcfix.csv ★
                          map_ver1_exdark_yolov8n_blcfix.csv ★
```

- `map_ablation{,2}_*` — `lowlight-rm-map-rootcause-2026-07-02.md` 의 근거 데이터
- `image_metrics_{coco,exdark}.csv` — Y 통계/포화율 등 이미지 지표 (Stage 2)

## 6. 자원/스케줄러 CSV

| 파일 | 내용 |
|---|---|
| `resource_csynth.csv` | variant별 C-합성 자원 (BRAM/DSP/FF/LUT/Fmax) |
| `resource_csynth_ver1_2026-07-02.csv` | ver1 모듈별 자원 분해 |
| `resource_csynth_rm_standalone_2026-07-02.csv` | RM 단독 합성 자원 |
| `resource_dfx_savings.csv` | DFX 시분할 대비 자원 절감 시나리오 |
| `scheduler.csv` | checker/히스테리시스 단계별 효과 |
| `scheduler_sweep.csv` | band×temporal×dwell 27조합 sweep |

## 7. 파일 명명 규칙 (앞으로도 이 규칙 유지)

```text
<주제>-<YYYY-MM-DD>.md          보고서 (예: blc-fix-resynthesis-2026-07-03.md)
map_<세대>_<dataset>_<model>.csv  mAP 측정 (최신 세대가 정본)
resource_*.csv / scheduler*.csv   자원·스케줄러 측정
새 실험 추가 시: 파일 생성 → 이 INDEX의 해당 섹션에 한 줄 추가
```
