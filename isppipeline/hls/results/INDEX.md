# results/ INDEX — 실험·시뮬레이션 산출물 카탈로그

**갱신:** 2026-07-20 · 이 폴더의 모든 파일을 주제별로 분류한 탐색용 인덱스.
정본 요약은 `ROADMAP.md`(진행 상태) / `SPEC.md`(사양) 참조. 2026-07-20부터
superseded 중간 산출물은 `archive/`로 이동한다(맨 아래 "아카이브 정책" 참고) —
정본/최신 파일은 계속 이 폴더 바로 아래에 두고 여기서 색인한다.

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
| `archive/experiment-plan-2026-07-01.md` | 07-01 | superseded → `experiment-stages-2026-07-02.md` |
| `experiment-stages-2026-07-02.md` | 07-02 | **정본** Stage 0~6 계획 |
| `improvement-strategy-2026-07-03.md` | 07-03 | **정본** 개선 전략 |

## 2. SW 트랙 결과 (Stage 0~3)

| 파일 | 날짜 | 내용 |
|---|---|---|
| `stage1-3-results-2026-07-02.md` | 07-02 | Stage 1~3 SW 실측 (checker/RM/mAP) |
| `archive/experiment_ver1_2026-07-02.md` | 07-02 | ver1 파이프라인 (RAW-domain-first) — 2026-07-08부터 archived/superseded (gamma 버그, `HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` 참고) |
| `archive/experiment_ver2_2026-07-02.md` | 07-02 | ver2 checker dark-level 재보정 |
| `lowlight-rm-map-rootcause-2026-07-02.md` | 07-02 | low-light RM mAP 미개선 원인 ablation |
| `phase0-2-execution-2026-07-03.md` | 07-03 | 개선전략 Phase 0~2 실행 결과 |
| `checker-improvement-theory-2026-07-03.md` | 07-03 | checker 개선 이론 (결정이론/노이즈물리/hysteresis) |
| `checker-improvement-simulation-2026-07-03.md` | 07-03 | checker 통계량 1150프레임 전수 스윕 (dark16 권고) |
| `lowlight-mv-isp-survey-2026-07-03.md` | 07-03 | 저조도 특성 + MV-ISP 모듈 서베이 (RM 후보) |
| `checker-improvement-analysis-2026-07-04.md` | 07-04 | dark16 우월성 원인 규명 + 기존 결과 비교 |
| `isp_analysis.md` / `isp_analysis.csv` | 06-29 | ISP variant proxy 분석 (detector 없음) |
| `11-ssd-crosscheck-2026-06-29.md` | 06-29 | SSD 2차 detector 교차검증 |
| `archive/realraw-sonynod-benchmark-2026-07-06.md` | 07-06 (BLC ablation 07-07 추가) | **real-RAW** 벤치마크 (RAW-NOD Sony, .ARW 원본+실측 GT) + AWB(§6bis)/BLC(§6ter) domain-gap ablation — §6ter는 `isp-pipeline-recalibration-2026-07-08.md`가 명시적으로 superseded 처리 |
| `isp-pipeline-recalibration-2026-07-08.md` | 07-08 | §6ter BLC 재보정 스윕 재측정 -- 구 SW-proxy 파이프라인의 gamma 버그(2.2/2.5/4.0 vs 배포 gamma-2.0) 수정 후 canonical-matched 파이프라인(`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/`checker.py`)으로 재실행, arm 순서 역전은 유지(단 margin 축소)·normal 단조감소 결론은 정정(BLC=1 근방 정점) |
| `demosaic-bilinear-fix-2026-07-09.md` | 07-09 | canonical `_demosaic_rggb16`의 R/B 채널 단일탭 보간을 golden/HW와 tap 단위로 동일한 bilinear로 수정, 신규 3자 교차검증 게이트로 bit-exact 확인. mAP 재검증은 GPU 필요 -- **R5 실행 완료, 아래 `isp-pipeline-bilinear-demosaic-2026-07-09.md` 참조** |
| `isp-pipeline-bilinear-demosaic-2026-07-09.md` | 07-09 (mAP 실행, PR #12로 유입) | **R5: bilinear 데모자이크 반영 mAP 재측정**(yolov8n, n=321, `map_isp_sonynod_bilinear_yolov8n.csv`) — (1) arm 순서 역전(`lowlight/adaptive > normal`)은 BLC 0~16 전 구간 유지(세 번째 독립 재확인), (2) normal의 BLC=1 근방 정점 유지, (3) fidelity 수정 자체의 효과는 BLC 0~2에서 +1.8~+3.8%, BLC 4~16에서 −0.9~−3.3%로 부호 반전(단일 실행 경향, 확정 금지) |
| `lowlight-module-techniques-2026-07-10.md` | 07-10 | **정본** 저조도 모듈(RM_LOW_LIGHT_TONE) 제안 기술 4종(binning/gain/gamma/완화BLC) × 기대 vs 실측 이득. 주효인=완화BLC(+78%), binning=조건부(real-RAW 대기), 별도 톤=기각. RESEARCH.md §1.3 주장1 상세근거 |
| `checker-status-2026-07-10.md` | 07-10 | **정본(빠른 결정)** checker 현행 상태 — 배포(C0) vs 권장(C1) 운영점, 강화안 7항목 채택/기각 표, 다음=LOD real-RAW |
| `checker-strengthening-2026-07-10.md` | 07-10 | **정본(전체 근거)** checker SOTA 강화 종합 — 리뷰(왜 이 레버들) + 7항목 전략 + 캠페인 실측(#2 LRT·#5 타일·#3+#6 시간층·#1 적응τ 판정·수치·재현). 구 review/strategy/lrt/tile/temporal/adaptive-tau 6문서를 대체(원문 git 이력). 도구는 `tools/checker_{lrt,tile_probe,temporal,adaptive_tau}.py` |
| `checker-adaptive-tau-realdata-2026-07-13.md` | 07-13 | checker-status §4 "다음 관문" #1 첫 실데이터 답 — SonyNOD 321장 ISO 층화 fixed-vs-adaptive τ recall. ISO[3200,6400)에서 개선(0.750→1.000, 8프레임) 확인, ISO≤1600(n=7)은 개선 없음(고정 판정 컷오프 재사용 탓, 표본 소). false-trigger는 여전히 미검증(PASCALRAW 필요). 도구는 `tools/analyze_adaptive_tau_sonynod.py` |
| `archive/checker-adaptive-tau-scenario-b-plan-2026-07-13.md` | 07-13 | 위 문서에서 C0/C1/adaptive 분류가 갈린 13프레임을 normal/lowlight 강제 arm으로 mAP 재확인하는 실행 계획 — **실행 완료, 결과는 `checker-adaptive-tau-realdata-2026-07-13.md` §6** (lowlight가 normal 대비 mAP@[.5:.95] +19.7%) |
| `archive/checker-adaptive-tau-scenario-b-full321-plan-2026-07-13.md` | 07-13 | ver0(§6/07-06 벤치마크)의 normal arm이 gain/gamma 없이 사실상 identity라는 공정성 우려 제기 + ver1(공정 비교)로 321장 전체 재실행 계획 — **ver1 실행 완료, 결과는 `checker-adaptive-tau-realdata-2026-07-13.md` §7** (공정 비교 후에도 lowlight가 normal의 2.9배, 우려 기각). normal/lowlight mAP가 소수점까지 우연히 일치하는 부분은 실 ARW 픽셀 직접 대조로 캐시버그 아님을 확인, 이후 스크립트 전수 감사에서 ver0-lowlight와 ver1-normal이 게인 상수(1.25x)를 실제로 공유함(우연 축소, 픽셀 동일은 아님)을 추가 확인(검증 노트). ver0 321장 재실행(§1)은 스킵 |
| `pascalraw-adapter-2026-07-13.md` | 07-13 (false-trigger 실측 07-15 §7 추가) | PASCALRAW(실 Nikon `.NEF`, 100% 주간, person/car/bicycle) 어댑터 -- SonyNOD/AODRaw가 못 채우는 false-trigger 측정용 정상조도 비교군. 4,259장 전량 변환 완료, **§7 실측**: false-trigger rate C0(배포) 92.91% / C1 41.82% / adaptive 38.39% -- checker-status-2026-07-10.md §4 갭 해소, 단 ISO[800,1600) n=28에서 adaptive 역전(96.4%>C1 32.1%)은 미결. 도구는 `tools/pascalraw_adapter.py`(변환), `tools/analyze_adaptive_tau_pascalraw.py`(측정) |
| `lod_split_2026-07-15.csv` / `pascal_split_2026-07-15.csv` / `shuffle_split_2026-07-15.csv` | 07-15 | LOD(SonyNOD, 321장 전량)·PASCAL(PASCALRAW ISO층화 샘플 321장)·Shuffle(둘을 합쳐 셔플, 642장) 동수 매칭 split -- 기존 두 전체분석 CSV(재decode 없이)에서 뽑음, gt_lowlight/verdict 컬럼 통일해 하나의 confusion matrix로 다룰 수 있게 정규화. LOD·PASCAL ISO 분포가 거의 안 겹침(LOD 88%가 [6400,12800), PASCAL 90%가 [400,800))을 확인 -- 프레임 수 매칭이 ISO별 균형 매칭은 아님, 후속 분석 시 주의. 생성 도구는 `tools/build_matched_splits.py`, raw_bin 재구성용 `tools/materialize_split.py` |
| `archive/HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` | 07-15 | **인수인계(노트북 RTX 5060)** -- 위 3개 split에 `eval_map_isp.py`의 기존 `adaptive` 암(체커 동적 파이프라인 선택, 신규 코드 불필요)으로 baseline/lowlight/adaptive mAP 실측 요청. raw_bin 픽셀 데이터(28G→gzip 14.03GiB)는 git 대신 Google Drive `paper/data-handoff/lod-pascal-splits-2026-07-15.tar.gz`로 전달·업로드 완료(용량상 git-lfs 없이 git push 불가 -- gitignore된 `data/` 그대로 유지). **실행 결과는 `lod-pascal-isp-simulation-2026-07-15.md` 참고 — 단, 이 문서가 지시한 그대로의 `adaptive` 암 구현에는 버그가 있었음이 드러남(아래 참고)** |
| `lod-pascal-isp-simulation-2026-07-15.md` | 07-16 (실행: 노트북 RTX 5060) | 위 HANDOFF 실행 결과 -- **버그 발견+수정**: `eval_map_isp.py`의 `adaptive` 암이 실제로는 채택된 adaptive-τ가 아니라 배포된 C0 체커(dark50>0.80)를 측정하고 있었음(PASCAL false-trigger가 C0 92.9% vs adaptive-τ 38.4%로 전혀 다른데 HANDOFF 문서가 둘을 혼동). manifest CSV의 `adaptive_verdict_lowlight`(사전계산된 실제 adaptive-τ 판정)를 쓰도록 `--manifest` 인자를 추가해 수정, 27개 조합(3 split×3 arm×BLC{16,1,2}) 재실행 완료. **핵심 결과**: (1) BLC=16→1/2 전환이 checker/adaptive보다 훨씬 큰 mAP 레버(최대 5.7배) -- 2026-07-08 recalibration을 실 RAW로 첫 재확인, (2) adaptive≈lowlight on LOD(예상대로), (3) Shuffle에서 "adaptive가 둘 다 이긴다"는 기준은 BLC=2에서만 근소하게 충족 -- 과장 금지 |
| `adaptive-tau-improvement-2026-07-20.md` | 07-20 (Codex 실행) | **adaptive-τ 개선 실험 3종(부정적 결과, 정직 기록)** — (1) 센서별 τ8=c·g 피팅은 recall 100%/FT 0%가 나오지만 **sensor/label 완전 confounding 누설**(Nikon=전부 주간, Sony=전부 야간)이라 기각, (2) tau_floor-only가 최선 비누설 변형(holdout J 0.6125 > C1 0.5674)이나 ISO[800,1600) 역전(96.4%)은 못 고침, (3) (τ,cutoff) 공동 보정은 저ISO 표본 부족으로 holdout J 0.3779로 악화. **결론: Path-A를 C1 대신 배포할 근거 아직 없음 — 다음 유효 실험은 동일 센서 day/night 데이터 또는 실측 dark-frame σ_read/K 필요**. 도구 `tools/experiment_adaptive_tau_improvement.py`, 산출물 `adaptive-tau-improvement-{metrics,frames}-2026-07-20.csv` + 히스토그램 캐시 npz |
| `checker-c1-deploy-2026-07-20.md` | 07-20 | **checker C1 정식 배포(관문 4 완료)** — `DARK_RATIO_PCT` 80→62, 드라이버 레지스터 규약 `dark_pixel_threshold=256`(=16<<4). adaptive-τ 대신 C1 선택(ISO[800,1600) 역전 미해명 + mAP 이득 근소 + 배포 복잡도). `checker.py`를 raw 도메인 비교로 바꿔 HW·보정 도메인과 정확히 일치시킴(구 luminance 근사 제거). golden 재생성 + verify/py-verify/rm-verify 통과, 실 RAW 642장에서 manifest dark16/verdict와 오차 0·불일치 0. 남은 관문은 #2 오라클 라벨뿐 |
| `blc-recalibration-deploy-2026-07-20.md` | 07-20 | **BLC 재보정 배포 반영(승인됨)** — 배포 상수 normal 16→2, lowlight 8→2 (`dfxisp_accel.cpp` + SW 미러 3파일). 07-08 스윕 + 07-15 LOD/PASCAL/Shuffle 실측이 근거(1~2가 평평한 정점, Shuffle adaptive pass 지점이 BLC=2). HW golden 재생성 + `make verify`/`rm-verify` bit-exact 전부 통과, 새 기본값이 스윕의 blc_offset=2 출력과 bit-exact 동일 확인. csynth/cosim 재실행은 미결(비트스트림 배포 전 필요) |
| `checker-oracle-label-gate2-2026-07-20.md` | 07-20 | **오라클 라벨 재정의(관문 2, 체커 SOTA 강화 최종 관문 완료)** — Shuffle_split 642장을 normal/lowlight dual-arm 렌더(배포 BLC=2) + 프레임별 YOLOv8n F1 델타(\|Δ\|≤0.05 don't-care)로 정답 재정의. C1 잔존오차 154장 중 **89.6%가 라벨 아티팩트**(진짜 오류 10.4%). dark16 판별력은 naive-라벨 J=0.847→오라클 J=0.008로 붕괴(장면 야간성은 잘 맞히나 프레임별 실제 검출 개선 여부는 약한 신호)하나, C1 임계의 비용-중립점(p(H1\|0.62)=0.510, 오라클 기준)은 유지 — **C1 재조정 불필요** 결론. 도구는 `tools/checker_oracle_{label,analysis}.py`, 산출물 `oracle_label_shuffle_2026-07-20.csv` |
| `HANDOFF-cross-model-yolov8s-2026-08-03.md` | 08-03 | **인수인계(노트북 RTX 5060)** — `lod-pascal-isp-simulation-2026-07-15.md`의 27개 조합(LOD/PASCAL/Shuffle_split × normal/lowlight/adaptive × BLC{16,1,2})을 YOLOv8n 대신 YOLOv8s로 재실행 요청, 새 코드 없이 `--model yolov8s.pt`만 변경. 목적: §8.3 발견("lowlight arm이 100% 주간인 PASCAL에서도 normal과 같거나 우위, 9/9 조합")이 YOLOv8n 특이적 아티팩트가 아님을 확인(논문 일반화 주장 근거, 이미 배포된 BLC 2/2·C1 결정을 막고 있지 않음). SSDLite-MobileNetV3는 `eval_map_isp.py` 미지원이라 별도 인수인계로 분리 — **철회(2026-08-13): YOLO 계열은 YOLOv8n만 사용하기로 결정, 이 인수인계와 그 실행 결과(`cross-model-yolov8s-2026-08-03.md` + CSV 3종)는 저장소에서 제거됨. 교차 검증은 SSDLite(비-YOLO) 인수인계로만 진행** |
| `HANDOFF-cross-model-ssdlite-2026-08-03.md` | 08-03 | **인수인계(노트북 RTX 5060)** — 교차 모델 검증 2단계, 같은 27개 조합을 SSDLite-MobileNetV3로 재실행. 신규 `tools/eval_map_isp_ssd.py`(이번 세션 작성, `eval_map_isp.py`의 이미지 렌더링 코드 재사용 + torchvision SSDLite 채점) 사용, 데스크탑에서 스모크 테스트 완료(CPU — 데스크탑 GPU 드라이버가 CUDA 미지원이라 노트북 GPU로 본 실행 필요). 목적은 YOLOv8s 인수인계와 동일(§8.3 검증), 이번엔 YOLO 계열이 아닌 SSD+MobileNet 구조까지 확장 |
| `archive/HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` | 07-13 | **정정 + 인수인계** — ver1(`isp_pipeline_ver1.py`)도 이미 2026-07-08에 archived/superseded된 파이프라인(gamma-2.2 float LUT, 배포 HW의 gamma-2.0 정수 sqrt 공유 LUT와 불일치)이었음이 드러남. 진짜 정본은 `baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/`checker.py`(07-08, 07-09 반영) — 이미 321장 전체로 실행됨(`isp-pipeline-recalibration-2026-07-08.md`, BLC=16 배포값에서 lowlight +8.1%, BLC=2 후보값 +12.6%, ver1의 +190%는 gamma 버그로 인한 과장). 시나리오 A는 파이프라인 무관이라 그대로 유효. 13프레임 서브셋만 `eval_map_isp.py`(정본)로 재실행 필요 — 노트북 에이전트용 실행 커맨드 포함 — **재실행 완료, 결과는 `checker-adaptive-tau-realdata-2026-07-13.md` §8(최종 정본 수치)**: BLC=16(배포값)에서 lowlight +4.4%(07-08 전체결과와 정합), 단 BLC=1/2(후보 정점)에서는 이 13프레임 한정 normal이 역전(-2.4%~-4.1%, 경계 프레임 표본 특성 가능성) — **§9에서 경계 프레임을 31장으로 확장 재검증, 역전은 n=13 노이즈로 확인(31장에서는 세 BLC 값 모두 lowlight 우세로 복귀), 단 격차 자체는 321장 전체보다 훨씬 작음(<1%p vs 8~13%p)** |

## 3. HW 트랙 결과 (Stage 4~5)

| 파일 | 날짜 | 내용 |
|---|---|---|
| `archive/10-hw-csynth-resource-2026-06-29.md` | 06-29 | 초기 C-합성 자원 (구 스캐폴드 기준) — `stage4-hw-synthesis-2026-07-02.md`(정본)로 대체 |
| `stage4-hw-synthesis-2026-07-02.md` | 07-02 | **정본** Stage 4 HLS 합성 실측 |
| `stage5-dfx-implementation-2026-07-02.md` | 07-02 | **정본** Stage 5 Vivado DFX 구현 |
| `pr-latency-breakdown-2026-07-02.md` | 07-02 | PR latency 단계별 분해 |
| `pr-latency-vivado-sim-2026-07-02.md` | 07-02 | XSIM 기반 ICAP PR latency 실측 시도 |
| `blc-fix-resynthesis-2026-07-03.md` | 07-03 | BLC 완화 반영 전체 재합성 |
| `cosim-waveform-analysis-2026-07-03.md` | 07-03 | C/RTL Co-sim 파형 분석 |
| `design-limitations-2026-07-03.md` | 07-03 | 설계 한계 종합 보고서 |
| `dfx-vivado-considerations-2026-07-03.md` | 07-03 | FPGA DFX 적용 고려사항 (Vivado 실측 기반) |
| `dfxisp-accel-connectivity-2026-07-03.md` | 07-03 | top-level 연결 테이블 (434 signal wires) |
| `blc-c1-csynth-cosim-rerun-2026-07-20.md` | 07-20 | BLC 2/2 + checker C1 반영 csynth/cosim 재실행 — 자원/타이밍 완전 동일 확인 |
| `dfx-reimplementation-2026-08-01.md` | 08-01 | 최신 BLC/C1 상수 반영 Vivado DFX fabric-only 재구현 — BRAM/DSP/timing/pr_verify/bitstream 전부 07-03 기준과 일치, CLB LUT만 34~37% 감소했으나 08-03 후속 조사로 근본 원인 확정(BLC 상수 유도 리터럴 6개뿐 차이 — 상수 기반 Vivado technology mapping의 정상 거동) |
| `HW-INTERFACE-PIN-MODULE-PROTOCOL-2026-08-03.md` | 08-03 | 핀 매핑(csynth 실측 RTL 포트)·모듈/RM 관계·통신 프로토콜(AXI4/AXI4-Lite/DFX 재구성) 브리핑 문서, ASCII 다이어그램 포함 — 다른 세션에 HW 인터페이스 인수인계용 |
| `lowlight-wb-mode-split-2026-08-03.md` | 08-03 | **정본(negative result)** 저조도 WB 모드별 분리 최종 판정 — 배포 WB가 저조도 B를 절반만 보정하는 것은 실측 확인됐으나(gray-world 대비 0.50×) mAP는 무반응(전 범위 spread 0.0020 = BLC 레버의 1/44), 채널 분리 실험이 효과 반증 → **분리하지 않음**. WB 검증 3회 수렴, 재실험 불필요 |
| `v2-arm-ablation-2026-08-06.md` | 08-06 | **v2 arm 첫 mAP + ablation** — NOD/PASCAL 각 100장, YOLOv8n/BLC=2. 야간 v2 lowlight는 v1 대비 +0.0119/+0.0220이나 denoise 비용은 정당화 실패(제거 권고), same-color binning은 지표 혼합으로 불확실. 주광 default v2는 v1 대비 주 지표 −0.0042, AWB 기여 없음. 근거 CSV `map_ablation_{nod100,pascal100}_2026-08-06.csv` |
| `denoise-k-sweep-2026-08-06.md` | 08-06 | **lowlight_ISP denoise 임계 정정 + NOD100 k sweep** — binning 후 채널별 k=2.4 임계 SAMECOLOR R/B=11, G=8 및 SUBSAMPLE R/B=21, G=15로 재유도. 주 지표는 탐색 범위 내 k=4.0이 최고(OFF 대비 +0.0049)이나 mAP@50 −0.0027·경계점·단일 100장 한계로 조건부 권고, 배포는 OFF 유지. 근거 CSV `map_denoise_k_sweep_nod100_2026-08-06.csv` |
| `gat-tone-ablation-2026-08-06.md` | 08-06 | **lowlight_ISP stage ⑤ 톤 커브 단독 ablation** — NOD100/YOLOv8n/BLC=2/shared WB에서 gamma 2.0(0.1876/0.3797) > GAT(0.1775/0.3710) > linear(0.1294/0.2651). **SSDLite MobileNetV3 교차검증에서 순위·효과크기 재현**(gamma−GAT: YOLO +0.0101, SSD +0.0105). GAT 중심 주장은 반증 확정 → **배포 커브를 gamma 2.0으로 교체**(재측정 0.1876/0.3797 일치 확인, csynth LUT 6,939→4,150·BRAM 5→1). 근거 CSV `map_gat_ablation_nod100_2026-08-06.csv`, `map_gat_ablation_nod100_ssdlite_2026-08-06.csv` |
| `csim-rerun-2026-08-14.md` | 08-14 | **clean C-sim 회귀 재실행** — DFXISP/default_ISP/lowlight_ISP 726/528/147픽셀 bit-exact PASS + vectorised SW proxy 40 trials/15,966 channel samples PASS. `c7e182e`의 canonical `../sw/` Makefile 경로 수정과 golden CSV 무변경을 재확인; csynth/co-sim·자원·타이밍은 범위 밖 |

## 4. 다이어그램 / RTL 부속물

| 파일 | 내용 |
|---|---|
| `dfxisp-microarchitecture-2026-07-02.svg` / `.drawio` | 마이크로아키텍처 다이어그램 (Arm2 vs Arm3) |
| `archive/pr_controller/` | (08-06 아카이브) 자체 PR 컨트롤러 1차 RTL + TB — DFXC IP 채택 + `pr_latency_probe.v`로 측정 역할까지 대체돼 은퇴(경위는 그 안 README) |
| `pr_controller/checker_hysteresis.v` + `_tb.v` + `checker_to_pr_tb.v` | (08-06) Schmitt mode arbiter RTL — checker 밴드 플래그 소비, `pr_controller.trigger` request/ack 직접 구동(판단 경로 PS 무개입); 단위·통합 TB xsim PASS |
| `pr_controller/checker_hysteresis.md` | (08-06) 위 모듈 설계 노트 — 플래그 인코딩/트리거 프로토콜/Stage 6 잔여 배선 + pr_controller 통합 이슈 3건(NWORDS 구 bitstream, word당 2사이클, ICAP 100MHz) |
| `pr_controller/dfxc_trigger_adapter.v` + `checker_to_dfxc_tb.v` | (08-06) **AMD DFX Controller IP(PG374) 채택** — checker_hysteresis를 IP 계약(HW trigger + shutdown ack shim)에 잇는 어댑터 + PG374 행위 모델 체인 TB(xsim PASS) |
| (소스 노트) `../src/default_isp.md` | (08-06) **default_ISP** — Vitis Vision `isppipeline` 스테이지 순서로 재구성한 표준 ISP arm. Vitis 대조표·의도적 편차 3건·실측(csynth LUT 12,659 vs RM_NORMAL 5,202, 타이밍 동일)·mAP 측정 완료(주광 100장: v1 normal 0.4197/0.9205 대 default_isp 0.4155/0.9232 = **주 지표 −0.0042**, 적응 AWB 기여 −0.0050, 둘 다 잡음대 안)·남은 일(post-route 미실측, 채택 미결) |
| (소스 노트) `../src/lowlight_isp.md` | (08-06) **lowlight_ISP v2** — 최종 구성은 **same-color 2×2 binning(+5.6~7.1dB) + 2.0× 상류 게인 + gamma 2.0 톤 + H/2×W/2 출력**, denoise 없음. 같은 날 두 번의 제거(denoise 삭제, GAT→gamma 교체)로 csynth **1 BRAM/10 DSP/2,089 FF/4,150 LUT**(v1 4,204의 0.99배, default_ISP의 33%)에 도달했고 타이밍은 3.650ns 불변. 야간 100장 0.1876/0.3797. GAT·구 subsample은 Python 골든의 ablation arm으로 보존 |
| `sonynod_convert_meta_archived-2026-08-06.json` | (08-06) 삭제된 `data/sonynod_test/`의 변환 파라미터 기록 — 카메라(RX100 VII)·Bayer(RGGB)·crop·black 800/white 16380·shift8 스케일. **LOD 재준비 시 이 값들로 동일 변환을 재현할 것**. 원본 ARW는 Drive `Sony-ARW/`(100장) |
| `pascal_split_100_2026-08-06.csv` | (08-06) **PASCAL 100장 축소 split** — 실험 반복 속도용. `build_matched_splits.py --n 100`(ISO 층화 유지: [0,400) 9 / [400,800) 90 / [800,1600) 1)로 4,259장에서 추출. 07-15의 321장 매니페스트는 배포 이력이라 **그대로 보존**하고 별도 파일로 추가. LOD/shuffle split은 이번에 제외(LOD 원본 재준비 예정) |
| `pr_controller/dfxc_adapter.md` | (08-06) IP 채택 결정 기록·근거 비교표·Stage 6 통합 체크리스트(포트명 IP 생성 후 확인 필요) |
| `pr_controller/pr_latency_probe.v` | (08-06) **부수(선택) 계측기** — 스왑 체인 동작에 불필요, 측정(보드 L5 수치)·디버그 시에만 부착. 재구성 레이턴시 계측 — IP엔 내장 타이머가 없어 핸드셰이크 경계(drain: shutdown req→ack, 전체: trigger→decouple 해제)를 카운트; `checker_to_dfxc_tb.v`에서 검증(계약 모델 기준 drain=4/swap=38 cycles) |
| `icap_sim/icap_pr_latency_tb.v` | ICAP PR latency 측정용 testbench |

## 5. mAP CSV 계보 (시간순 — 어느 숫자가 최신인지)

측정 세대가 4번 바뀌었다. **최신 정본 수치는 G4 (`*_blcfix`)**, 그 이전은 계보
추적용 — 2026-07-20 정리로 G1~G3 CSV 전부 `archive/`로 이동(파일명은 동일,
경로만 `archive/` 접두).

```text
G1 (06-29, 구 스캐폴드, → archive/):
                          map_dark, map_dark_full, map_real, map_real_full,
                          map_exdark, map_exdark_bilbin, map_coco_bilbin,
                          map_exdark_yolov8s, map_coco_ssd, map_exdark_ssd
G2 (07-01~02, reset 아키텍처 "newrm", → archive/):
                          map_newrm_{coco,exdark}_{yolov8n,yolov8s,ssd}
G3 (07-02, ver1/ver2 개정, → archive/): map_ver1_{coco,exdark}_{yolov8n,yolov8s,ssd}
                          map_ver2_{coco,exdark}_yolov8n_adaptive
                          map_ablation_*, map_ablation2_* (원인분석 ablation)
G4 (07-03, BLC 완화 최종, top level 유지): map_ver1_coco_yolov8n_blcfix.csv ★
                          map_ver1_exdark_yolov8n_blcfix.csv ★
```

- `archive/map_ablation{,2}_*` — `lowlight-rm-map-rootcause-2026-07-02.md` 의 근거 데이터 (문서 자체는 top level 유지, 데이터만 archive/)
- `image_metrics_{coco,exdark}.csv` — Y 통계/포화율 등 이미지 지표 (Stage 2, top level 유지 — `stage1-3-results-2026-07-02.md`가 여전히 참조)

## 6. 자원/스케줄러 CSV

| 파일 | 내용 |
|---|---|
| `archive/resource_csynth.csv` | variant별 C-합성 자원 (BRAM/DSP/FF/LUT/Fmax) — 구 스캐폴드, `resource_csynth_ver1_2026-07-02.csv`(Stage 4 정본)로 대체 |
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

## 아카이브 정책

top level(이 INDEX가 색인하는 `results/` 바로 아래)에는 정본/최신 문서·CSV만
남긴다. superseded/대체된 중간 산출물(구 세대 mAP CSV, gamma 버그가 있던
파이프라인 결과, INDEX나 후속 문서가 명시적으로 "superseded"/"대체"라 표기한
문서)은 `results/archive/`로 옮긴다 — `tools/archive/`와 동일한 규칙. **이동만
하고 삭제하지 않는다**(`git mv`, 내용 무수정, 전체 이력은 git으로 보존).
어떤 파일이 왜 옮겨졌는지는 `archive/README.md` 참고.
