<!--
=============================================================================
File   : isppipeline/hls/results/pascalraw-adapter-2026-07-13.md
Date   : 2026-07-13 KST
Branch : exp/adaptive-tau-realdata-2026-07-13
Campaign: checker-sota false-trigger 선결물 (AODRaw 어댑터와 동일 선례)
Function: PASCALRAW(실 RAW, 100% 주간) → dfxisp SW-eval 레이아웃 어댑터의
          설계·계약·검증 상태 기록. 다운로드 진행 중, 완료 전 선작성.
Sources: aodraw-adapter-2026-07-09.md (동일 계약·선례)
         tools/pascalraw_adapter.py (신규, 본 캠페인)
         tools/aodraw_adapter.py (read_raw/rggb_align_crop/to_shift8_bin/
         extract_exif 재사용, 로직 중복 없음)
         PASCALRAW: Omid-Zohoor/Ta/Murmann, Stanford Digital Repository
         purl.stanford.edu/hq050zr7488
Repro  : cd isppipeline/hls/tools
         python3 pascalraw_adapter.py --selftest   # 순수로직 4종 검증
         # 실 수집(다운로드 완료 후):
         python3 pascalraw_adapter.py --ann-dir <...>/Annotations \
             --raw-dir <...>/NEF --out ../../data/pascalraw_test
=============================================================================
-->
# PASCALRAW 어댑터 (false-trigger 선결물, 선작성, 2026-07-13)

**작성:** 2026-07-13 KST · **브랜치:** `exp/adaptive-tau-realdata-2026-07-13`

> 상태: **완료.** 4,259프레임 전량 변환(2026-07-14) + false-trigger 실측
> (2026-07-15, §7) 끝남. C0(배포) 92.9% / C1 41.8% / adaptive 38.4%
> false-trigger — checker-status-2026-07-10.md §4 "다음 관문" 갭 해소.
> ISO[800,1600) n=28에서 adaptive 역전(96.4%)은 미결로 남음(§7 해석 4).

## 1. 왜 이게 필요한가

`checker-status-2026-07-10.md` §4와 `checker-adaptive-tau-realdata-2026-07-13.md`
§0이 반복해 지적한 갭: **SonyNOD(RAW-NOD Sony 서브셋, 321장)는 전량
저녁/야간 촬영**이라 recall(LOW_LIGHT를 정확히 잡는가)만 측정 가능하고,
checker의 다른 실패 모드인 **false-trigger**(정상조도 장면을 LOW_LIGHT로
오판)는 이 데이터셋에 정상조도 비교군이 없어 여태 미측정이었다. PASCALRAW는
**전량 주간 촬영**(4,259장, Nikon D3200 실 `.NEF`, person/car/bicycle 라벨)
이라 정확히 이 결측을 메운다. 어댑터가 준비돼 있어야 다운로드 완료 직후
`analyze_adaptive_tau_sonynod.py`와 동일한 checker 로직을 이 데이터셋에
돌려 LOW_LIGHT 판정 전부를 false-trigger로 집계할 수 있다.

## 2. PASCALRAW 포맷 (공식 기록 + 논문 기준, 다운로드 전 확인)

- 실 Nikon **`.NEF`** RAW, 12-bit, RGGB, 6034×4012, Nikon D3200 단일 바디.
- 주석은 **PASCAL VOC 가이드라인**을 따른 이미지별 XML
  (`<object><name>/<bndbox><xmin>/<ymin>/<xmax>/<ymax></bndbox></object>`).
- 3 카테고리 — **person / car / bicycle**, COCO-80 이름과 그대로 일치
  (AODRaw의 62→80 리맵과 달리 별도 매핑 테이블 불필요, alias 1개만
  `pedestrian→person` 예비로 둠).
- **100% 주간**(Palo Alto/San Francisco 도로) — 프레임별 light/weather 태그
  자체가 없음 → `light="daylight"`, `illum_label=0`을 전 프레임 고정.
- 실 아카이브의 정확한 폴더명(예: `Annotations/`, `NEF/`)은 다운로드 전
  미확인 — 3rd-party 파생 저장소(`OuYaozhong/pascalraw-root`)는 `.NEF`가
  아닌 변환된 `.png`를 쓰므로 참고만 하고 그대로 따르지 않음. 어댑터는
  폴더명을 가정하지 않고 `--ann-dir`/`--raw-dir`를 받아 stem으로 매칭한다.

## 3. 계약 (aodraw_adapter.py와 동일)

`raw_bin/<stem>.bin`(shift8 RGGB) / `images/<stem>.jpg` / `labels/<stem>.txt`
(YOLO, COCO-80) / `meta.json` / `frames_meta.csv`(light 항상 daylight,
illum_label 항상 0). 흑레벨/화이트레벨/베이어 위상은 단일 카메라 바디임에도
`aodraw_adapter.py`와 동일하게 파일별 rawpy 값을 읽는다(계약 일관성,
비용 없음).

## 4. 검증 상태

`python3 pascalraw_adapter.py --selftest` — 합성 데이터로 4종 순수로직
전부 통과: VOC XML 파싱(3 object, size 200×100), YOLO 변환(person/car
매핑 + 미매칭 `traffic_cone` 드롭), `.NEF`/`.nef` 파일 매칭, alias
(`pedestrian→person`). `aodraw_adapter.py --selftest`도 함께 재실행해
import 공유가 기존 검증을 깨지 않았음을 확인.

**미검증(불가):** 실 `.NEF` rawpy 디코드, XML의 정확한 필드명(예: `<name>`이
실제로 `person`/`car`/`bicycle` 소문자인지)은 실파일/README 확인 전까지
가정.

## 5. 다운로드 완료 후 즉시 실행

```bash
python3 tools/pascalraw_adapter.py \
  --ann-dir <PASCALRAW>/Annotations --raw-dir <PASCALRAW>/NEF \
  --out ../../data/pascalraw_test [--limit 20] [--exiftool /usr/bin/exiftool]
```

첫 검증은 `--limit 20`으로 소수 프레임만 변환해 (a) XML 필드명이 가정과
맞는지, (b) RGGB 위상·BLC가 프리뷰와 대조해 맞는지 확인하는 것 — AODRaw와
동일 순서. 이후 `analyze_adaptive_tau_sonynod.py`의 checker 판정 로직을
이 데이터셋 프레임에 적용해 LOW_LIGHT 오판 비율(=false-trigger rate)을
처음으로 실측한다.

## 6. 산출물

- `tools/pascalraw_adapter.py` — 어댑터(셀프테스트 포함).
- 본 문서.

## 7. false-trigger 실측 결과 (2026-07-15, 최초 측정)

**작성:** 2026-07-15 KST · 도구: `tools/analyze_adaptive_tau_pascalraw.py` ·
데이터: `data/pascalraw_test` 4,259프레임 전량 (ISO 결측 0건 — §5의 exiftool
미설치 문제는 `aodraw_adapter.py:extract_exif`의 exifread 폴백으로 해결됨,
2026-07-15). 결과: `adaptive_tau_pascalraw_results.csv`.

전량 100% 주간(§2)이므로 LOW_LIGHT 판정은 전부 정의상 false-trigger.

**전체 false-trigger rate:**

| 판정 로직 | 임계값 | false-trigger rate |
|---|---|---|
| C0 (배포, `dfxisp_accel.cpp:94`) | dark_ratio@50 > 80% | **92.91%** |
| C1 (권장·미배포) | dark_ratio@16 > 0.62 | **41.82%** |
| adaptive τ | dark_ratio@thr8 > 0.62 | **38.39%** |

**ISO 층화:**

| ISO 구간 | n | C0 FT | C1 FT | adaptive FT |
|---|---|---|---|---|
| [0, 400) | 380 | 0.918 | 0.155 | 0.021 |
| [400, 800) | 3850 | 0.930 | 0.445 | 0.415 |
| [800, 1600) | 28 | 1.000 | 0.321 | 0.964 |
| [1600, 3200) | 1 | 1.000 | 0.000 | 1.000 |

**해석:**

1. **배포된 C0는 주간 장면의 93%를 LOW_LIGHT로 오판** — checker-status-2026-07-10.md
   §4가 이미 "강화 필요"로 지적했던 것과 정합하되, 실측치는 그 우려보다도
   심각하다. dark_ratio@50 임계(80%)가 주간 도로 장면(그림자·아스팔트·차량
   하부 등 어두운 영역 비중이 높은 실사진)에는 사실상 항상 걸린다는 뜻.
2. **C1/adaptive는 C0 대비 각각 2.2배/2.4배 개선**(92.9%→41.8%/38.4%)하지만
   여전히 데이터의 약 40%를 오판 — SonyNOD recall 측정
   (`checker-adaptive-tau-realdata-2026-07-13.md`)이 보여준 개선 방향과
   합쳐도, "recall 개선 + false-trigger 대폭 감소"이지 "false-trigger
   해소"는 아니다.
3. **adaptive가 전체 평균으로는 C1보다 근소 우위(38.4% vs 41.8%)** —
   대부분(ISO[0,800), n=4230/4259)에서 adaptive가 C1보다 뚜렷이 낮다.
4. **주의 — ISO[800,1600) n=28에서 adaptive(96.4%)가 C1(32.1%)보다 훨씬
   나쁨**, 방향이 반전. 표본이 28장뿐이라 노이즈 가능성이 크지만,
   SonyNOD 쪽에서도 ISO≤1600 구간이 표본 부족으로 결론 보류됐던 것과
   같은 패턴(`checker-adaptive-tau-realdata-2026-07-13.md` §5의 지적 2)이라
   우연으로 단정하기엔 이르다 — adaptive τ의 고정 판정 컷오프가 이
   ISO대에서 잘 안 맞을 가능성. 후속 조사 필요, 미결.

**결론:** checker-status-2026-07-10.md §4 "다음 관문" 중 false-trigger 측정
갭이 이제 해소됨. adaptive τ는 recall(SonyNOD)과 false-trigger(PASCALRAW)
양쪽에서 C1 대비 우위 또는 동등 — 단, ISO[800,1600) 표본에서의 역전은
adaptive 채택 전에 짚고 넘어가야 할 미결 항목으로 남긴다.
