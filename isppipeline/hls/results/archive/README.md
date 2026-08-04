# results/archive/ — 대체된(superseded) 중간 산출물

**날짜:** 2026-07-20 · `results/` 상위 레벨을 정본/최신 문서만 남기도록 정리하며
이 디렉터리로 이동한 파일 목록. `tools/archive/`와 동일한 규칙: **이동만 하고
삭제하지 않는다** (`git mv`, 내용 무수정 — 문서 내부의 상대경로/헤더 언급이
이 이동으로 stale해질 수 있으나 의도적으로 그대로 둔다). 각 파일의 전체 이력은
`git log --follow`로 조회 가능.

## 1. 초기 스캐폴드 HW 결과 (G1, 06-29)

`10-hw-csynth-resource-2026-06-29.md`, `resource_csynth.csv` — "구 스캐폴드
기준" 4-variant C-합성 결과. `stage4-hw-synthesis-2026-07-02.md`(정본)로 대체.

## 2. G1~G3 mAP CSV 계보 (INDEX.md §5 "mAP CSV 계보" 기준)

`INDEX.md`가 "최신 정본 수치는 G4(`*_blcfix`), 그 이전은 계보 추적용"이라고
명시한 세대. G4(`map_ver1_{coco,exdark}_yolov8n_blcfix.csv`)만 top level에 남기고
G1~G3은 전부 이동:

- G1(구 스캐폴드): `map_dark.csv`, `map_dark_full.csv`, `map_real.csv`,
  `map_real_full.csv`, `map_exdark.csv`, `map_exdark_bilbin.csv`,
  `map_coco_bilbin.csv`, `map_exdark_yolov8s.csv`, `map_coco_ssd.csv`,
  `map_exdark_ssd.csv`
- G2("newrm" reset 아키텍처): `map_newrm_coco_yolov8n.csv`,
  `map_newrm_coco_yolov8s.csv`, `map_newrm_coco_ssd.csv`,
  `map_newrm_exdark_yolov8n.csv`, `map_newrm_exdark_yolov8s.csv`,
  `map_newrm_exdark_ssd.csv`
- G3(ver1/ver2 개정 + 원인분석 ablation): `map_ver1_coco_yolov8n.csv`,
  `map_ver1_coco_yolov8s.csv`, `map_ver1_exdark_yolov8n.csv`,
  `map_ver1_exdark_yolov8s.csv`, `map_ver1_exdark_ssd.csv`,
  `map_ver2_coco_yolov8n_adaptive.csv`, `map_ver2_exdark_yolov8n_adaptive.csv`,
  `map_ablation_coco_yolov8n.csv`, `map_ablation_exdark_yolov8n.csv`,
  `map_ablation2_coco_yolov8n.csv`, `map_ablation2_exdark_yolov8n.csv`

## 3. `newrm_pipeline.py` 계열 SonyNOD 결과 (legacy 파이프라인)

`newrm_pipeline.py`는 자체 docstring에 "LEGACY, not canonical"이라 명시된
파이프라인. 이 스크립트로 만든 SonyNOD real-RAW 결과 전부 이동:
`map_newrm_sonynod_blcfix_yolov8n.csv`(`isp-pipeline-recalibration-2026-07-08.md`가
명시적으로 superseded 처리), `map_newrm_sonynod_flip13_yolov8n.csv`,
`map_newrm_sonynod_realwb_yolov8n.csv`, `map_newrm_sonynod_yolov8n.csv`.

## 4. `isp_pipeline_ver1.py` 계열 SonyNOD 결과 (gamma 버그)

`isp_pipeline_ver1.py`는 2026-07-08부터 archived/superseded 상태
(`HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` 참고) —
gamma-2.2 부동소수점 LUT를 썼는데 배포 HW는 gamma-2.0 정수 sqrt 공유 LUT.
`map_ver1_sonynod_full321_yolov8n.csv`(§7 "ver1 공정비교")는
`checker-adaptive-tau-realdata-2026-07-13.md` §8이 "비-정본 파이프라인
기준"이라 명시적으로 정정한 결과라서 이동. (§6/§7이 만든 SonyNOD 13프레임/
321프레임 결과는 모두 이동 대상이고, §8/§9의 canonical 재실행 결과
`map_isp_sonynod_flip13_canonical_yolov8n.csv` /
`map_isp_sonynod_boundary31_canonical_yolov8n.csv`는 top level에 그대로 둔다.)

## 5. 계획/실험 문서 (조기 이터레이션, 결론이 후속 정본 문서로 흡수됨)

- `experiment-plan-2026-07-01.md` — INDEX.md가 직접
  "superseded → `experiment-stages-2026-07-02.md`"라고 표기.
- `experiment_ver1_2026-07-02.md`, `experiment_ver2_2026-07-02.md` — ver1
  아키텍처 자체가 위 §4 사유로 archived/superseded.
- `realraw-sonynod-benchmark-2026-07-06.md` — `isp-pipeline-recalibration-2026-07-08.md`
  §5가 "이 문서가 그 결과를 대체(supersede)함을 여기 명시한다"라고 직접 기술.

## 6. 기타 orphan 스크래치 아티팩트

`scratch_frame_hist.npz` — 어떤 top-level 문서에서도 참조되지 않는 미인용
바이너리 산출물(1150프레임 히스토그램 캐시로 추정, 재생성 가능).

## 7. handoff/plan 문서 (2026-07-20, 캠페인 완결로 흡수)

체커 SOTA 강화 캠페인이 2026-07-20에 4개 관문 전부로 종결되면서(`checker-status
-2026-07-10.md` §4), 그 과정에서 쓰인 handoff/plan 문서 4개를 이동했다 —
전부 "실행 완료, 결과는 X 참고"를 스스로 명시하고 있어 내용이 이미 결과
문서로 흡수된 상태였다:

- `checker-adaptive-tau-scenario-b-plan-2026-07-13.md` — 실행 계획.
  결과는 `checker-adaptive-tau-realdata-2026-07-13.md` §6.
- `checker-adaptive-tau-scenario-b-full321-plan-2026-07-13.md` — ver1 공정비교
  실행 계획. 결과는 `checker-adaptive-tau-realdata-2026-07-13.md` §7.
- `HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` — 노트북(RTX 5060)
  인수인계. 실행 결과(+버그 발견·수정)는 `lod-pascal-isp-simulation-2026-07-15.md`.
- `HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` — 파이프라인
  정정 + 재실행 인수인계. 최종 정본 수치는 `checker-adaptive-tau-realdata
  -2026-07-13.md` §8/§9.

## 이동하지 않은 것 (참고)

`*.log` 스크래치 파일(`scratch_rmfine*.log`, `scratch_rmds.log`,
`scratch_rmfx.log` 등)은 `.gitignore`(`*.log`)로 애초에 git 추적 대상이
아니라서(`git mv` 불가) 이번 정리에서 건드리지 않았다 — 이동해도 이력 보존의
의미가 없고, 현재 진행 중인 다른 백그라운드 작업과 무관하게 그대로 둔다.
