<!--
=============================================================================
File   : isppipeline/hls/results/realraw-sonynod-benchmark-2026-07-06.md
Date   : 2026-07-06
Function: 실제 카메라 센서 raw(.ARW) + 사람이 단 GT로 새 mAP 벤치마크를 구성해
          SPEC.md §11-1의 "SW eval은 proxy(pseudo-RAW)" 한계를 raw 표현 축에서
          부분적으로 해소. 후속으로 AWB domain-gap ablation(§6bis), 이어서 BLC
          재보정 ablation(§6ter) 수행.
Goal   : "Sony RAW dataset을 어떻게 활용할지" 요청에 대한 응답 -- 새로운 real-RAW
         mAP 벤치마크(SonyNOD)를 만들고 기존 pseudo-RAW(ExDark/COCO) 결과와 비교.
         이어서 "AWB domain-gap 분리 ablation 수행" 요청에 응답 -- 결과: AWB는
         무관하고 BLC가 신호를 먼저 죽이는 것이 실제 원인(§6bis). 이어서 "BLC
         재보정 ablation 수행" 요청에 응답 -- BLC_OFFSET을 16→0~2로 낮추면
         mAP가 4.6~6.3배 회복되지만, lowlight>normal arm 순서 역전은 BLC와
         무관하게 모든 BLC값에서 유지됨을 확인(§6ter).
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

> **범위 노트(2026-07-06 후속):** `none`은 checker/RM/baseline core를 전혀
> 거치지 않는 arm이라 이 파이프라인 연구의 비교 대상이 아니다(사용자 판단:
> "다른 계열의 연구 분야"). 이후 해석은 **normal/lowlight/adaptive만** 비교한다.
> `none` 수치는 §5 표에 참고용으로만 남겨둔다.

1. **arm 순서가 뒤집힌다.** ExDark(pseudo-RAW)는 `normal(0.068) > lowlight(0.055)`
   인데, SonyNOD(real-RAW)는 `lowlight(0.036) > normal(0.022)`다. pseudo-RAW
   기반 실험(§11-6, BLC/WB가 저조도 mAP 손실의 70%를 차지)에서 도출한 결론이
   real 센서 raw에서는 그대로 성립하지 않을 수 있다는 신호 — low-light 전용
   RM(2x2 binning+gain+gamma)이 실제 센서 noise 특성에서는 오히려 유리하게
   작용할 수 있음을 시사한다. n=321 대 71이라 통계적으로 더 안정적인 비교이기도
   하다.
2. **baseline core의 고정 AWB(Q8 R286/G256/B307)가 실제 카메라 화이트밸런스와
   맞지 않는다.** `adaptive`/`normal` arm 이미지를 육안 확인한 결과 뚜렷한
   녹색 편향이 나타남. §6-1의 arm 순서 역전이 이 AWB domain gap 때문인지
   확인하기 위해 아래 ablation을 수행했다.

## 6bis. AWB domain-gap ablation (2026-07-06)

**방법:** 샘플 ARW의 `rawpy` 메타데이터(`camera_whitebalance`)를 321장 전부에서
추출(`camera_wb.json`), Q8 규약(`awb_r=round(256*R_mul/G_mul)`,
`awb_b=round(256*B_mul/G_mul)`)으로 변환해 **프레임별 실제 카메라 AWB**로
baseline core를 재실행(`newrm_pipeline_realwb.py` + `eval_map_newrm_realwb.py`,
BLC/gain/gamma/binning 등 나머지는 전부 고정 — AWB 소스만 바꾼 순수 ablation).
`none`은 AWB/baseline core를 안 거치므로 대상에서 제외(§6 범위 노트와 동일 이유).

측정된 실제 AWB는 고정 상수보다 훨씬 크다 — 321장 전체 통계:

| | R/G ratio | B/G ratio |
|---|---:|---:|
| 파이프라인 고정값 | 1.117 | 1.199 |
| 실제 카메라(min/mean/max) | 1.48 / 1.95 / 2.47 | 1.57 / 2.17 / 3.07 |

**결과 (yolov8n, n=321):**

| arm | AWB | mAP@[.5:.95] | mAP@50 |
|---|---|---:|---:|
| normal | 고정(pseudo-RAW 튜닝) | 0.0216 | 0.0560 |
| normal | 실제 카메라(프레임별) | 0.0214 | 0.0561 |
| lowlight | 고정 | 0.0356 | 0.0793 |
| lowlight | 실제 카메라 | 0.0350 | 0.0791 |
| adaptive | 고정 | 0.0356 | 0.0793 |
| adaptive | 실제 카메라 | 0.0350 | 0.0791 |

**AWB를 실제 값으로 교체해도 mAP가 사실상 변하지 않는다(±0.0006, 노이즈 수준).**
즉 AWB 재보정은 SonyNOD의 mAP 손실이나 §6-1의 arm 순서 역전을 설명하지 못한다
— 육안상 뚜렷한 녹색 편향과는 별개로, **detector 성능에는 거의 영향이 없다.**

**원인 — BLC가 AWB보다 먼저 신호를 죽인다.** `raw_bin`(shift8, 8-bit 도메인)
픽셀 통계를 직접 확인한 결과:

- 두 샘플 모두 8-bit 값의 **50% 이상이 정확히 0**, 99th percentile이 **10**
  (255 만점 기준) — RAW-NOD 야간 장면의 실제 신호가 8-bit 표현폭의 최하단
  4%에만 존재한다.
- `baseline_core`의 `BLC_OFFSET=16`을 적용하면 **픽셀의 99.9%가 0으로 잘려나간다**
  (`(raw8bit - 16) <= 0`인 비율 99.91%/99.90%, 두 샘플).
- AWB는 BLC **다음** 단계에서 곱셈으로 적용되는데, 입력이 이미 0이면 게인이
  얼마든 결과도 0이다 — 이것이 AWB ablation이 무효과로 나온 정확한 이유다.

`BLC_OFFSET=16`은 pseudo-RAW(역-ISP 8-bit 통계)에 맞춰 튜닝된 상수라, 이렇게
극단적으로 어두운(원본 14-bit raw에서 white_level 대비 <1% 반사율) 실제
야간 raw에는 맞지 않는다. **AWB가 아니라 BLC 재보정(혹은 shift8 재양자화 자체를
real-RAW 동적범위에 맞게 재설계)이 다음으로 확인해야 할 도메인 갭이다.**

## 6ter. BLC 재보정 ablation (2026-07-07)

**방법:** §6bis가 지목한 원인("BLC_OFFSET=16이 AWB보다 먼저 신호를 죽인다")을
직접 검증하기 위해 AWB/gain/gamma/demosaic/binning은 파이프라인 기존 고정값
그대로 두고 `BLC_OFFSET`만 파라미터화(`newrm_pipeline_blcfix.py` +
`eval_map_newrm_blcfix.py`, AWB ablation과 동일한 "변수 하나만 격리" 방식).
`BLC_OFFSET ∈ {0,1,2,4,8,16}`을 321장 전체 × normal/lowlight/adaptive에 대해
스윕(`none`은 이전과 동일한 이유로 제외).

**사전 확인 (30장 샘플, shift8 8-bit 픽셀값):** median=2, p90=13, p99=121
(가로등/헤드라이트 하이라이트 꼬리) — 현재 `BLC_OFFSET=16`은 전체 픽셀의
**92.2%**를 0으로 깎는다(`frac<=16`).

**결과 (yolov8n, n=321):**

| BLC_OFFSET | normal mAP@.5:.95 | normal mAP@50 | lowlight/adaptive mAP@.5:.95 | lowlight/adaptive mAP@50 |
|---:|---:|---:|---:|---:|
| 0 | 0.1356 | 0.2526 | 0.1655 | 0.3089 |
| 1 | 0.1270 | 0.2373 | 0.1871 | 0.3381 |
| **2** | 0.1138 | 0.2174 | **0.2004** | **0.3598** |
| 4 | 0.0892 | 0.1766 | 0.1676 | 0.3094 |
| 8 | 0.0528 | 0.1112 | 0.0973 | 0.1916 |
| 16 (현행) | 0.0216 | 0.0560 | 0.0356 | 0.0793 |

**가설 검증됨 — BLC가 신호를 죽인다는 진단이 정량적으로 확인된다.** `normal` arm은
BLC_OFFSET에 대해 **완전히 단조 감소**(0→16 사이 6.28배 차이, 0.1356→0.0216) —
잘라내는 만큼 정확히 mAP가 깎인다. `lowlight`/`adaptive`는 BLC=2에서 정점을
찍는 **비단조** 곡선(0.0356→0.2004, 5.63배)으로, binning으로 이미 SNR을 올린
뒤에는 작은 양의 BLC(read-noise 바이어스 제거)가 여전히 도움이 되지만 4 이상부터는
같은 방식으로 신호를 잘라내기 시작한다.

**단, arm 순서 역전(§6-1)은 BLC와 무관하게 유지된다.** 스윕 전 구간에서
`lowlight/adaptive > normal`이 성립한다(BLC=0조차 0.1655 > 0.1356). 즉 §6-1의
"real-RAW 야간 장면에서 low-light RM(2x2 binning+gain+gamma)이 유리하다"는
결론은 BLC 미스캘리브레이션의 인공물이 아니라 — BLC를 최적화해도 여전히
성립하는 real 센서 low-light의 구조적 특성이다. BLC 재보정은 **손실된 신호를
복구**하지만 **어느 arm이 이기는지는 바꾸지 않는다**.

**남은 질문:** 이 실험은 파이프라인의 다른 모든 상수(AWB Q8, LL_GAIN=1.25,
gamma-4.0)를 pseudo-RAW 튜닝값 그대로 둔 상태에서 BLC_OFFSET만 바꾼 순수
ablation이다. "최적 BLC=2"가 실제 배포 값으로 적합한지는 (i) shift8 재양자화
자체를 real-RAW 동적범위(black_level/white_level)에 맞게 재설계하는 편이
더 원리적인지, (ii) gain/gamma도 함께 재튜닝하면 최적점이 이동하는지 추가
검증이 필요하다(§7 한계 참조).

## 7. 알려진 한계

- 단일 카메라(Sony RX100 VII)·단일 렌즈, 전부 저녁/야간 조건 — "정상조도"에
  대응하는 real-RAW arm이 없다(RAW-NOD 자체가 low-light 전용 데이터셋).
- yolov8n 1개 detector만 실행(ExDark/COCO는 yolov8s·SSD 교차검증도 있음) —
  교차검증 아직 TODO.
- HW/C-sim(12-bit raw12 경로)은 여전히 합성 fixture만 사용 — 이번 통합은
  SW eval 경로에 한정.
- BLC 재보정 ablation(§6ter)은 BLC_OFFSET만 격리한 순수 ablation — AWB/gain/
  gamma를 pseudo-RAW 튜닝값에 고정한 채로 얻은 결과라, 실제 배포 시에는 이들을
  함께 재튜닝하거나 shift8 재양자화 자체를 재설계할 필요가 있는지 아직 미검증.
- `data/sonynod_test/`는 17GB(라벨 있는 321장 기준)라 `.gitignore`의 `data/`
  규칙에 따라 커밋하지 않음 — 재현하려면 `tools/build_sonynod_dataset.py` +
  Drive `dataset/Sony/Sony-ARW/` + GitHub `igor-morawski/RAW-NOD` 어노테이션.

## 8. 재현

```bash
# 1) 원본 raw + 어노테이션 확보 (Drive: dataset/Sony/Sony-ARW/, GitHub: annotations/Sony/raw_str_labeled_new_Sony_RX100m7_test.json)
# 2) 변환
python3 isppipeline/hls/tools/build_sonynod_dataset.py \
    raw_str_labeled_new_Sony_RX100m7_test.json <ARW dir> data/sonynod_test
# 3) 기존 고정-AWB 평가
cd isppipeline/hls/tools
python3 eval_map_newrm.py --root ../../../data/sonynod_test --tag SonyNOD \
    --model yolov8n.pt --limit 321 --out ../results/map_newrm_sonynod_yolov8n.csv
# 4) AWB domain-gap ablation (camera_wb.json: {stem: [R_mul,G_mul,B_mul,G2_mul]}, rawpy camera_whitebalance)
python3 eval_map_newrm_realwb.py --root ../../../data/sonynod_test --wb-table camera_wb.json \
    --tag SonyNOD-RealWB --model yolov8n.pt --out ../results/map_newrm_sonynod_realwb_yolov8n.csv
# 5) BLC recalibration ablation (BLC_OFFSET sweep, AWB/gain/gamma held fixed)
python3 eval_map_newrm_blcfix.py --root ../../../data/sonynod_test --blc-offsets 0,1,2,4,8,16 \
    --tag SonyNOD-BLCFix --model yolov8n.pt --out ../results/map_newrm_sonynod_blcfix_yolov8n.csv
```
