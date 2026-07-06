<!--
=============================================================================
File   : isppipeline/hls/results/realraw-sonynod-benchmark-2026-07-06.md
Date   : 2026-07-06
Function: 실제 카메라 센서 raw(.ARW) + 사람이 단 GT로 새 mAP 벤치마크를 구성해
          SPEC.md §11-1의 "SW eval은 proxy(pseudo-RAW)" 한계를 raw 표현 축에서
          부분적으로 해소.
Goal   : "Sony RAW dataset을 어떻게 활용할지" 요청에 대한 응답 -- 새로운 real-RAW
         mAP 벤치마크(SonyNOD)를 만들고 기존 pseudo-RAW(ExDark/COCO) 결과와 비교.
=============================================================================
-->
# Real-RAW 벤치마크: RAW-NOD Sony 서브셋 (2026-07-06)

## 1. 배경

기존 SW mAP 평가(ExDark_val/COCO_val, `tools/eval_map_newrm.py`)는 전부
**pseudo-RAW**를 입력으로 쓴다 — sRGB JPEG을 역-ISP로 합성한 것으로, SPEC.md
§11-1이 명시한 대로 "이미 ISP된 JPEG 역변환"이라는 근본적 한계가 있다
(`최종 판정은 보드 DPU+real-RAW`). 사용자가 Google Drive `dataset/Sony/`에
올려둔 **RAW-NOD**(GenISP 논문, CVPR Workshop 2022) Sony RX100 VII 서브셋은
실제 센서 raw(.ARW) + person/bicycle/car GT bbox를 갖춘 공개 데이터셋으로,
이 한계를 raw 표현 축에서 부분적으로 해소할 수 있는 후보였다.

## 2. 데이터 소스

- 공식 저장소: https://github.com/igor-morawski/RAW-NOD (어노테이션만 배포,
  실제 `.ARW`는 별도 구글 폼 신청 필요 — README 확인 결과)
- 이번 작업 대상: 사용자가 이미 Google Drive `dataset/Sony/Sony-ARW/`에
  업로드해 둔 전체 4,143장(README 통계: 어노테이션 3.2k + 미어노테이션 0.9k와 일치)
  중 **공식 test split** `raw_str_labeled_new_Sony_RX100m7_test.json` 321장.
  train/val이 아닌 test를 고른 이유: 저자가 지정한 held-out 평가셋을 그대로
  써서 임의 샘플링 논란을 없애기 위함.
- GT: person(1) / bicycle(2) / car(3), 총 1,827 bbox.

## 3. 변환 스펙 (`tools/build_sonynod_dataset.py`)

샘플 ARW 2장을 `rawpy`로 직접 조사해 확정한 실측 센서 스펙:

| 항목 | 값 |
|---|---|
| 카메라 | Sony RX100 VII |
| Bayer 패턴 | RGGB (`raw_pattern=[[0,1],[3,2]]`, `color_desc=RGBG`) — 프로젝트 규약과 그대로 일치 |
| 유효 영역 크롭 | top=12, left=12, width=5472, height=3648 (짝수 오프셋 → RGGB phase 보존, GT bbox 좌표계와 정확히 일치) |
| black_level / white_level | 800 / 16380 (14-bit ADC, 2개 샘플에서 채널 간 균일) |
| 출력 양자화 | `u8 = round(clip((raw-800)/(16380-800),0,1)*255)`, `raw16 = u8<<8` — 기존 pseudo-RAW 데이터셋과 **동일한 shift8 규약**(SPEC §2.2)이라 `newrm_pipeline.py`(`bayer16>>SHIFT`)를 코드 수정 없이 그대로 재사용 가능 |
| 라벨 | COCO category_id `{1,2,3}` → COCO-80 0-index `{0,1,2}` (person/bicycle/car), bbox → YOLO 정규화 cx,cy,w,h |

## 4. 검증

- `raw_bin` 하위 8비트가 전부 0(shift8 규약 준수) 확인.
- GT bbox를 밝기 보정한 데모자이크 이미지 위에 오버레이 → 사람 2명 위치와
  정확히 일치(크롭 오프셋·좌표계 변환 정합 확인).
- checker `dark_ratio`가 두 샘플 모두 **1.0** — RAW-NOD가 전부 저녁/야간
  촬영이라는 논문 설명과 일치(전부 low-light 판정, 정상조도 arm 없음).
- 321장 전량 변환 성공(스킵 0, 무-GT 스킵 0) — `data/sonynod_test/meta.json` 참조.

## 5. 결과 — mAP (yolov8n, imgsz=640, ultralytics val)

| dataset | arm | mAP@[.5:.95] | mAP@50 | n |
|---|---|---:|---:|---:|
| **SonyNOD (real-RAW)** | none | **0.1342** | **0.2513** | 321 |
| SonyNOD | normal | 0.0216 | 0.0560 | 321 |
| SonyNOD | lowlight | 0.0356 | 0.0793 | 321 |
| SonyNOD | adaptive | 0.0356 | 0.0793 | 321 |
| ExDark (pseudo-RAW) | none | 0.1561 | 0.3064 | 71 |
| ExDark | normal | 0.0680 | 0.1490 | 71 |
| ExDark | lowlight | 0.0554 | 0.1342 | 71 |
| ExDark | adaptive | 0.0554 | 0.1342 | 71 |
| COCO (pseudo-RAW) | none | 0.3276 | 0.4707 | 80 |

(ExDark/COCO 수치는 동일 스크립트로 이전에 생성된
`results/map_newrm_{exdark,coco}_yolov8n.csv`에서 인용.)

## 6. 해석

1. **`none`이 항상 천장이라는 SPEC §11-1 관찰이 real-RAW에서도 그대로 재현된다**
   — checker/RM/baseline core를 거치는 순간 mAP가 크게 떨어진다. pseudo-RAW
   한계가 아니라 이 파이프라인/평가 방식 자체의 특성임을 다시 확인.
2. **arm 순서가 뒤집힌다.** ExDark(pseudo-RAW)는 `normal(0.068) > lowlight(0.055)`
   인데, SonyNOD(real-RAW)는 `lowlight(0.036) > normal(0.022)`다. pseudo-RAW
   기반 실험(§11-6, BLC/WB가 저조도 mAP 손실의 70%를 차지)에서 도출한 결론이
   real 센서 raw에서는 그대로 성립하지 않을 수 있다는 신호 — low-light 전용
   RM(2x2 binning+gain+gamma)이 실제 센서 noise 특성에서는 오히려 유리하게
   작용할 수 있음을 시사한다. n=321 대 71이라 통계적으로 더 안정적인 비교이기도
   하다.
3. **baseline core의 고정 AWB(Q8 R286/G256/B307)가 실제 카메라 화이트밸런스와
   맞지 않는다.** `adaptive` arm 이미지를 육안 확인한 결과 뚜렷한 녹색 편향이
   나타남 — 이 AWB 상수는 pseudo-RAW(JPEG 역-ISP)의 색 통계에 맞춰진 것이라
   실제 센서 raw에는 재보정이 필요하다는 명확한 근거. 지금 수치(특히 `normal`
   arm이 `lowlight`보다 더 나쁜 것)에 이 domain gap이 얼마나 기여하는지는
   미분리 — 후속 ablation 필요.

## 7. 알려진 한계

- 단일 카메라(Sony RX100 VII)·단일 렌즈, 전부 저녁/야간 조건 — "정상조도"에
  대응하는 real-RAW arm이 없다(RAW-NOD 자체가 low-light 전용 데이터셋).
- yolov8n 1개 detector만 실행(ExDark/COCO는 yolov8s·SSD 교차검증도 있음) —
  교차검증 아직 TODO.
- HW/C-sim(12-bit raw12 경로)은 여전히 합성 fixture만 사용 — 이번 통합은
  SW eval 경로에 한정.
- AWB domain gap(§6-3)을 분리하는 ablation 미실시.
- `data/sonynod_test/`는 17GB(라벨 있는 321장 기준)라 `.gitignore`의 `data/`
  규칙에 따라 커밋하지 않음 — 재현하려면 `tools/build_sonynod_dataset.py` +
  Drive `dataset/Sony/Sony-ARW/` + GitHub `igor-morawski/RAW-NOD` 어노테이션.

## 8. 재현

```bash
# 1) 원본 raw + 어노테이션 확보 (Drive: dataset/Sony/Sony-ARW/, GitHub: annotations/Sony/raw_str_labeled_new_Sony_RX100m7_test.json)
# 2) 변환
python3 isppipeline/hls/tools/build_sonynod_dataset.py \
    raw_str_labeled_new_Sony_RX100m7_test.json <ARW dir> data/sonynod_test
# 3) 평가
cd isppipeline/hls/tools
python3 eval_map_newrm.py --root ../../../data/sonynod_test --tag SonyNOD \
    --model yolov8n.pt --limit 321 --out ../results/map_newrm_sonynod_yolov8n.csv
```
