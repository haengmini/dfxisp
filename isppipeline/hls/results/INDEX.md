# results/ INDEX — 실험·시뮬레이션 산출물 카탈로그

**갱신:** 2026-07-07 · 이 폴더의 모든 파일을 주제별로 분류한 탐색용 인덱스.
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
| `checker-improvement-theory-2026-07-03.md` | 07-03 | checker 개선 이론 (결정이론/노이즈물리/hysteresis) |
| `checker-improvement-simulation-2026-07-03.md` | 07-03 | checker 통계량 1150프레임 전수 스윕 (dark16 권고) |
| `lowlight-mv-isp-survey-2026-07-03.md` | 07-03 | 저조도 특성 + MV-ISP 모듈 서베이 (RM 후보) |
| `checker-improvement-analysis-2026-07-04.md` | 07-04 | dark16 우월성 원인 규명 + 기존 결과 비교 |
| `isp_analysis.md` / `isp_analysis.csv` | 06-29 | ISP variant proxy 분석 (detector 없음) |
| `11-ssd-crosscheck-2026-06-29.md` | 06-29 | SSD 2차 detector 교차검증 |
| `realraw-sonynod-benchmark-2026-07-06.md` | 07-06 (BLC ablation 07-07 추가) | **real-RAW** 벤치마크 (RAW-NOD Sony, .ARW 원본+실측 GT) + AWB(§6bis)/BLC(§6ter) domain-gap ablation |
| `isp-pipeline-recalibration-2026-07-08.md` | 07-08 | §6ter BLC 재보정 스윕 재측정 -- 구 SW-proxy 파이프라인의 gamma 버그(2.2/2.5/4.0 vs 배포 gamma-2.0) 수정 후 canonical-matched 파이프라인(`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/`checker.py`)으로 재실행, arm 순서 역전은 유지(단 margin 축소)·normal 단조감소 결론은 정정(BLC=1 근방 정점) |
| `demosaic-bilinear-fix-2026-07-09.md` | 07-09 | canonical `_demosaic_rggb16`의 R/B 채널 단일탭 보간을 golden/HW와 tap 단위로 동일한 bilinear로 수정, 신규 3자 교차검증 게이트로 bit-exact 확인. mAP 재검증은 GPU 필요 -- 별도 R5 라운드로 예정 |
| `lowlight-module-techniques-2026-07-10.md` | 07-10 | **정본** 저조도 모듈(RM_LOW_LIGHT_TONE) 제안 기술 4종(binning/gain/gamma/완화BLC) × 기대 vs 실측 이득. 주효인=완화BLC(+78%), binning=조건부(real-RAW 대기), 별도 톤=기각. RESEARCH.md §1.3 주장1 상세근거 |
| `checker-status-2026-07-10.md` | 07-10 | **정본(빠른 결정)** checker 현행 상태 — 배포(C0) vs 권장(C1) 운영점, 강화안 7항목 채택/기각 표, 다음=LOD real-RAW |
| `checker-strengthening-2026-07-10.md` | 07-10 | **정본(전체 근거)** checker SOTA 강화 종합 — 리뷰(왜 이 레버들) + 7항목 전략 + 캠페인 실측(#2 LRT·#5 타일·#3+#6 시간층·#1 적응τ 판정·수치·재현). 구 review/strategy/lrt/tile/temporal/adaptive-tau 6문서를 대체(원문 git 이력). 도구는 `tools/checker_{lrt,tile_probe,temporal,adaptive_tau}.py` |
| `checker-adaptive-tau-realdata-2026-07-13.md` | 07-13 | checker-status §4 "다음 관문" #1 첫 실데이터 답 — SonyNOD 321장 ISO 층화 fixed-vs-adaptive τ recall. ISO[3200,6400)에서 개선(0.750→1.000, 8프레임) 확인, ISO≤1600(n=7)은 개선 없음(고정 판정 컷오프 재사용 탓, 표본 소). false-trigger는 여전히 미검증(PASCALRAW 필요). 도구는 `tools/analyze_adaptive_tau_sonynod.py` |
| `checker-adaptive-tau-scenario-b-plan-2026-07-13.md` | 07-13 | **계획(미실행)** — 위 문서에서 C0/C1/adaptive 분류가 갈린 13프레임을 normal/lowlight 강제 arm으로 mAP 재확인하는 실행 계획. GPU 필요, 결과는 별도 문서로 추가 예정 |

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

## 6.5 principled-v3 캠페인 (2026-07-05, 원리기반 checker+RM 재설계)

정본 종합: `principled-comparison-2026-07-05.md` (여기부터 읽기). 브랜치 `exp/principled-checker-rm-2026-07-05`.

| 파일 | 내용 |
|---|---|
| `PLAN-principled-checker-rm-2026-07-05.md` | 캠페인 계획 (버전정의·에이전트팀 배치) |
| `checker-principles-2026-07-05.md` | **정본** checker 5원리 (결정이론/광도계/노이즈물리/샘플링/시간축) |
| `references-index-2026-07-07.md` | **정본** 참고문헌 통합 인덱스 (theory/principles/survey 3개 문서의 서지·각주를 모두 여기로 이관) |
| `checker-principled-versions-2026-07-05.md` | checker C0..C4 구현·실험 (winner C1 dark16>0.62) |
| `lowlight-feature-principles-2026-07-05.md` | **정본** 저조도 feature 추출 원리 (SNR/VST/tone) |
| `lowlight-rm-principled-versions-2026-07-05.md` | RM R0..R3 mAP+size-AP 실험 (winner R1 full-res VST) |
| `rm-ssd-crosscheck-2026-07-05.md` | SSDLite 3차 검출기 교차검증 |
| `principled-comparison-2026-07-05.md` | **정본** 이전버전 대비 종합 비교·결론 |
| `map_rm_{exdark,coco}_yolov8{n,s}_2026-07-05.csv`, `map_rm_ssd_2026-07-05.csv` | RM 버전 mAP |
| `scratch_frame_stats.csv`, `scratch_adaptive_map_principled.csv` | checker 통계·adaptive mAP |

구현: `tools/checker_versions.py`, `tools/rm_versions.py`, `tools/eval_map_rmversions{,_ssd}.py`, `tools/scratch_adaptive_map_principled.py`.

### principled-v3 refinement (2026-07-05, 재검토+Codex리뷰+세분화)

정본: `principled-v3-refinement-2026-07-05.md` (1차 결론 정정 — RM 이득=binning 제거이고 COCO 견고·ExDark 검출기의존; 최적 checker 임계 dark8~10; C4 nested-CV 기각 확정).

| 파일 | 내용 |
|---|---|
| `principled-v3-refinement-2026-07-05.md` | **정본** 재검토·Codex·세분화 종합 (자체 5갭 + Codex 7findings 반영) |
| `checker_fine_2026-07-05.csv` | dark8~32 미세 sweep + 정직한 5-fold/nested CV |
| `map_rmfine_{coco,exdark}_yolov8n_2026-07-05.csv` | 2×3 resolution×tone factorial (n=150) |
| `map_rmfine575_{coco,exdark}_yolov8{n,s}_2026-07-05.csv` | 결정 셀 전수 + cross-detector |
| `map_rmfine_deployexact_{coco,exdark}_yolov8n_2026-07-05.csv` | bit-exact 배포 톤(floor LUT) 확인 |

구현: `tools/checker_versions_fine.py`, `tools/rm_versions_fine.py`, `tools/eval_map_rmversions_fine.py`.

## 7. 파일 명명 규칙 (앞으로도 이 규칙 유지)

```text
<주제>-<YYYY-MM-DD>.md          보고서 (예: blc-fix-resynthesis-2026-07-03.md)
map_<세대>_<dataset>_<model>.csv  mAP 측정 (최신 세대가 정본)
resource_*.csv / scheduler*.csv   자원·스케줄러 측정
새 실험 추가 시: 파일 생성 → 이 INDEX의 해당 섹션에 한 줄 추가
```
