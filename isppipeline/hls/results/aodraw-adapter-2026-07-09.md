<!--
=============================================================================
File   : isppipeline/hls/results/aodraw-adapter-2026-07-09.md
Date   : 2026-07-09 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign: checker-sota #4-1 (AODRaw adapter, pre-written)
Function: AODRaw(실 RAW) → dfxisp SW-eval 레이아웃 어댑터의 설계·계약·검증
          상태 기록. 다운로드 완료 전 선작성. #4(오라클 라벨)·#1(적응 τ)의
          임계경로 선결물.
Sources: checker-sota-strategy-2026-07-09.md (#4 step 1)
         tools/aodraw_adapter.py (신규, 본 캠페인)
         tools/build_sonynod_dataset.py (실-RAW 수집 선례/계약)
         AODRaw: Li et al., CVPR2025 Highlight, github.com/lzyhha/AODRaw
Repro  : cd isppipeline/hls/tools
         python3 aodraw_adapter.py --selftest         # 순수로직 5종 검증
         # 실 수집(다운로드 완료 후):
         python3 aodraw_adapter.py --ann <...json> --raw-dir <...> --out ../../data/aodraw_test
=============================================================================
-->
# AODRaw 어댑터 (강화전략 #4-1, 선작성, 2026-07-09)

**작성:** 2026-07-09 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05`

> 상태: **코드 완성 + 순수로직 셀프테스트 전부 통과.** 유일한 미검증 경로는
> 실 `.ARW` rawpy 디코드(실파일 필요)이며, 이는 sonynod 어댑터에서 이미
> 입증된 rawpy 관용구를 재사용한다. 다운로드 완료 시 `--ann/--raw-dir/--out`
> 한 줄로 바로 수집 가능.

## 1. 왜 이게 임계경로인가

전략 문서 #4(오라클 라벨)·#1(적응 τ)는 둘 다 **실센서 RAW + 노출/게인
메타데이터**를 전제로 한다. 현행 벤치마크(COCO/ExDark pseudo-RAW)는 (a)
sRGB 역감마 합성이라 SNR 기반 τ(s,g)를 활성화할 수 없고, (b) 라벨이
데이터셋 프록시라 잔존오차 78장이 라벨 아티팩트로 귀속된다(LRT 캠페인
`checker-lrt-2026-07-09.md`에서 실증). AODRaw는 실 Sony RAW + COCO 포맷
주석 + 프레임별 `tag`(조도/날씨)로 이 둘을 동시에 푼다. 어댑터가 없으면
#4·#1 어느 것도 시작할 수 없으므로 다운로드 대기 중 선작성했다.

## 2. AODRaw 포맷 (공식 저장소 확인)

- 실 Sony **`.ARW`** RAW. 원본 6000×4000, `images_downsampled_raw`
  (2000×1333), `images_slice_raw`(1280×1280) 변형 제공.
- 주석 **COCO json**. 이미지 레코드에 `tag` 리스트(예: `["low_light"]`,
  `["daylight","fog"]`)로 **조도/날씨 조건**을 인코딩 — #4의 조도축 + 1차 라벨.
- **62 카테고리** → COCO-80과 이름으로 매칭되는 것만 리맵, 나머지 드롭.
- 흑레벨/화이트레벨/베이어 패턴은 저장소 문서에 명시 없음 → **파일별로
  rawpy에서 읽는다**(다중 조건 데이터셋이므로 하드코딩 금지).
- EXIF(ISO/노출)는 저장소 문서에 미명시. ARW 헤더에는 존재 → exiftool로
  best-effort 추출(아래 §4).

## 3. 계약 (sonynod 선례와 동일 + 신규 메타 CSV)

어댑터 산출물:

| 산출 | 규약 |
|---|---|
| `raw_bin/<stem>.bin` | 리틀엔디안 uint16, **shift8**(`round(linear·255)<<8`), RGGB 위상 (0,0), 짝수 dims → 무수정 baseline core / `newrm_pipeline.py`(`bayer16>>8`) / `checker_stat_sweep.py`(`raw>>8`)가 drop-in 소비 |
| `images/<stem>.jpg` | rawpy postprocess sRGB 프리뷰 (로더가 W,H 복원) |
| `labels/<stem>.txt` | YOLO `cls cx cy w h`(정규화), COCO-80 0-index |
| `meta.json` | 데이터셋 provenance |
| **`frames_meta.csv`** | **신규** — 프레임별 `stem,w,h,light,weather,iso,exposure_s,f_number,black_level,white_level,bayer,dark16,illum_label`. #4 조도 스트라텀·#1 τ(s,g)의 입력 |

## 4. sonynod 대비 핵심 차이 (다중 조건 대응)

1. **파일별 센서 파라미터.** 흑레벨/화이트레벨/베이어 위상을 상수로 박지
   않고 `rawpy`의 `black_level_per_channel`, `white_level`,
   `raw_colors_visible`에서 프레임마다 읽는다. 채널별 흑레벨 차감은
   `raw_colors_visible` 인덱스로 픽셀 단위 수행.
2. **RGGB 위상 정렬.** `rggb_align_crop()`가 4개 위상 오프셋을 탐색해 어떤
   센서 방향이든 좌상단 2×2가 정확히 `R G / G B`가 되게 짝수 크롭 →
   파이프라인의 `demosaic_rggb12` 가정 보존.
3. **조도/날씨 메타.** `parse_tag()`가 `tag` 리스트를 (light, weather)로
   분해(미태그 = daylight/clear). `illum_label`(low_light=1)은 1차 라벨이며,
   #4의 최종 라벨은 다운스트림 오라클(route-and-measure)로 대체 예정.
4. **EXIF pluggable.** `extract_exif()`가 exiftool(`-j -n`)로 ISO/노출/조리개
   추출, 도구 부재 시 null 기록하고 크래시하지 않음(rawpy는 ISO 미노출).
5. **이름 기반 카테고리 리맵.** `build_category_map()`가 AODRaw
   `categories`를 COCO-80 이름(+ aeroplane/sofa 등 별칭)으로 매핑.

`read_raw()`는 **비-ARW 변형(예: 패킹 배열로 배포되는 downsampled_raw)이
나올 경우 유일하게 손볼 함수**로 격리해 두었다.

## 5. 검증 상태

`python3 aodraw_adapter.py --selftest` — 합성 데이터로 5종 순수로직 전부
통과:

- `[ok] rggb_align_crop`: BGGR 위상 센서 → 크롭 후 quad=RGGB
- `[ok] to_shift8_bin`: 채널별 BLC + shift8, `raw>>8 ∈ [0,255]` 경계 확인
- `[ok]` 카테고리 리맵(별칭 aeroplane→airplane, sofa→couch) + 미매칭 드롭
- `[ok] parse_tag`: 조도/날씨 추출(night→low_light 정규화)
- `[ok] extract_exif`: 도구 부재 graceful 폴백

**미검증(불가):** 실 `.ARW` rawpy 디코드 — 실파일 필요. sonynod
`arw_to_raw_bin`과 동일 관용구(`raw_image_visible` → 크롭 → 정규화 →
shift8)라 리스크 낮음.

## 6. 다운로드 완료 후 즉시 실행

```bash
python3 tools/aodraw_adapter.py \
  --ann <AODRaw>/annotations/test_annotations_downsample_scale3_bbox_min_size32.json \
  --raw-dir <AODRaw>/images_downsampled_raw \
  --out ../../data/aodraw_test [--limit N] [--exiftool /usr/bin/exiftool]
```

산출된 `data/aodraw_test/`는 (a) `checker_stat_sweep.py --compute`로 통계
스윕에 바로 투입, (b) `frames_meta.csv`로 #4 조도 스트라텀·#1 τ(s,g) 착수,
(c) `scratch_adaptive_map_principled.py`의 dual-arm 러너로 오라클 라벨 생성에
사용. 첫 검증은 소수 `--limit 20`으로 RGGB 위상·BLC가 실파일에서 맞는지
프리뷰와 대조하는 것.

## 7. 산출물

- `tools/aodraw_adapter.py` — 어댑터(셀프테스트 포함).
- 본 문서.
