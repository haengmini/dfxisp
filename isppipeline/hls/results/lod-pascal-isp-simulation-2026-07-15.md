<!--
=============================================================================
File   : isppipeline/hls/results/lod-pascal-isp-simulation-2026-07-15.md
Date   : 2026-07-16 KST (실행: 07-15 데스크톱 인수인계 -> 07-16 노트북 실행)
Function: HANDOFF-lod-pascal-isp-simulation-2026-07-15.md의 후속 -- LOD_split/
          PASCAL_split/Shuffle_split 세 데이터셋에 normal/lowlight/adaptive
          ISP arm을 BLC{16,1,2} 스윕으로 렌더링해 mAP로 실측한다. 실행 도중
          eval_map_isp.py의 "adaptive" arm이 실제로는 채택된 adaptive-tau가
          아니라 배포된 C0 체커를 측정하고 있던 버그를 발견·수정하고 재실행
          했다 -- 이 문서의 결과는 수정 후(정본) 수치다.
Sources: HANDOFF-lod-pascal-isp-simulation-2026-07-15.md (원 인수인계),
         checker-status-2026-07-10.md SS1-2 (C0/C1/adaptive-tau 운영점 정의),
         pascalraw-adapter-2026-07-13.md SS7 (adaptive-tau false-trigger 38.4%),
         checker-adaptive-tau-realdata-2026-07-13.md (adaptive-tau recall),
         isp-pipeline-recalibration-2026-07-08.md (BLC=1/2 후보 정점, 이전
         SonyNOD 단독 결과),
         tools/eval_map_isp.py(이번 세션에서 --manifest 인자 추가 수정),
         tools/checker.py / checker_adaptive_tau.py / build_matched_splits.py
=============================================================================
-->
# LOD/PASCAL/Shuffle split ISP 시뮬레이션 (2026-07-16, 노트북 RTX 5060 실행)

## 0. 결론부터

세 데이터셋(LOD_split 321장/PASCAL_split 321장/Shuffle_split 642장) × 3개 arm
(normal/lowlight/adaptive) × BLC{16,1,2} = 27개 조합을 전부 실측했다.

1. **가장 큰 효과는 checker/adaptive가 아니라 BLC 값이다.** 배포값 BLC=16 대비
   후보값 BLC=1/2가 **모든 split·모든 arm에서 압도적으로 높은 mAP**를 낸다
   (LOD는 최대 5.7배, PASCAL은 +35%, Shuffle은 최대 2.2배). 2026-07-08
   recalibration의 결론(BLC=1~2 근방이 정점)을 **실 센서 RAW(LOD+PASCAL)로
   처음 재확인**했다 — 현재 배포된 BLC=16은 실측상 명백히 최적이 아니다.
2. **adaptive는 예상대로 LOD에서 lowlight와 거의 동일**했다(모든 BLC에서
   ±0.0001 수준). SonyNOD에서 adaptive-tau recall이 매우 높다는 기존 실측과
   정합한다.
3. **PASCAL에서 adaptive는 normal과 lowlight 사이**로, 대체로 normal에 더
   가깝다(전에 발견했던 버그가 고쳐진 뒤의 정상적인 모습) — 단 BLC=1에서는
   셋 중 최저치를 기록했는데 격차(0.0004)가 노이즈 수준이라 단정하기 어렵다.
4. **Shuffle에서 "adaptive가 normal/lowlight 둘 다 이겨야 한다"는
   핸드오프의 통과 기준은 BLC=2에서만, 그것도 근소한 차이(+0.0002)로
   충족됐다.** BLC=16/1에서는 lowlight를 근소하게 못 이겼다(-0.0012/-0.0003).
   "확실히 이긴다"고 과장할 수 있는 수준은 아니다.
5. **부수 발견**: lowlight arm이 100% 주간인 PASCAL에서도 9개 BLC×비교
   조합 전부에서 normal과 같거나 높은 mAP를 냈다 — 단일 모델/단일 run이라
   확대해석은 금물이나, 방향이 일관돼 우연으로 보기 어렵다.

## 1. 실험 준비물

### 1.1 데이터셋 (build_matched_splits.py, 07-15 생성)
| 이름 | 프레임 수 | 원본 소스 | 조도 | 비고 |
|---|---|---|---|---|
| **LOD_split** | 321 | SonyNOD 전량(Sony `.ARW`) | 100% 실야간 | `data/lod_split/{raw_bin,images,labels}` |
| **PASCAL_split** | 321 | PASCALRAW 4,259장 중 ISO-stratified 샘플(Nikon `.NEF`) | 100% 주간 | `data/pascal_split/` |
| **Shuffle_split** | 642 | 위 둘의 union, 셔플 | 혼합(실배포 근사) | `data/shuffle_split/` |

세 디렉터리 모두 `materialize_split.py`(symlink 모드)로 이미 이 노트북에
구성되어 있었다(원본 raw_bin 픽셀은 Google Drive
`paper/data-handoff/lod-pascal-splits-2026-07-15.tar.gz`로 전달됨). LOD/PASCAL
ISO 분포는 거의 겹치지 않는다(LOD 88%가 ISO[6400,12800), PASCAL 90%가
ISO[400,800)) — 프레임 수 매칭이지 ISO 균형 매칭은 아니다.

### 1.2 manifest CSV (results/{lod,pascal,shuffle}_split_2026-07-15.csv)
`build_matched_splits.py`가 만든, 프레임별 사전계산 컬럼을 담은 CSV:
`source, stem, iso, exposure_s, dark50, dark16, adaptive_thr8, dark_adaptive,
c0_verdict_lowlight, c1_verdict_lowlight, adaptive_verdict_lowlight,
gt_lowlight, data_dir`. **`adaptive_verdict_lowlight`가 이번 실험의 핵심
입력** — `checker_adaptive_tau.tau_for_frame()`(EXIF 기반 센서 적응 τ, Path A,
checker-strengthening-2026-07-10.md #1 채택안)으로 이미 계산되어 있다.

### 1.3 코드 모듈
- `tools/baseline_isp_pipeline.py` — normal arm (demosaic bilinear → BLC →
  WB → gain 1.25x → gamma2.0)
- `tools/low_light_isp_pipeline.py` — lowlight arm (2x2 binning-demosaic →
  BLC → WB → gain 2.0x → 동일 gamma2.0 LUT)
- `tools/checker.py` — 배포된 C0 규칙(dark50 ratio>0.80)의 참조 구현. 이번
  실험에서는 `--manifest` 미지정 시의 하위호환 폴백으로만 쓰임(§7.1 참고)
- `tools/checker_adaptive_tau.py` — 채택된 adaptive-τ(Path A) 산출 로직,
  EXIF(ISO/노출) 필요 — manifest 생성 시에 이미 실행되어 있어 이번
  eval에서는 직접 호출하지 않음
- `tools/eval_map_isp.py` — 실행 하네스, **이번 세션에서 `--manifest` 인자
  추가(§7.1)**

### 1.4 모델 / 하드웨어
- 검출기: YOLOv8n(`model/detectors/yolo/yolov8n.pt`), `ultralytics` `val()`,
  imgsz=640, mAP@[.5:.95]/@50(COCO 방식)
- 실행 환경: 노트북, NVIDIA GeForce RTX 5060 Laptop GPU(8,151MiB), driver
  572.97, torch 2.11.0+cu128, CUDA 사용 가능 확인(`torch.cuda.is_available()`)

## 2. 방법

각 (split, BLC, arm) 조합마다:
1. `raw_bin/*.bin`(headerless little-endian uint16, RGGB, shift8)을 읽어
   프레임별로 렌더링.
2. **normal**: `_demosaic_rggb16`(bilinear) → BLC 오프셋 차감(스윕값) → WB
   Q8(286/256/307) → gain 5/4 → `>>8` → 공유 `GAMMA2_LUT`(γ=2.0, isqrt).
3. **lowlight**: `_bin_demosaic_rggb16`(2x2, R=TL/G=avg(TR,BL)/B=BR, 채널
   보존) → 동일 BLC/WB 적용(스윕값) → gain 2/1 → `>>8` → 동일 GAMMA2_LUT.
   출력 해상도 H/2×W/2.
4. **adaptive**: manifest에서 해당 stem의 `adaptive_verdict_lowlight`를
   조회 → True면 lowlight 렌더링, False면 normal 렌더링 호출(3번을 다시
   렌더링하는 게 아니라 두 함수 중 하나만 실행).
5. 렌더된 jpg + 원본 라벨(txt, YOLO 포맷, COCO-80 id)을 arm별 임시 디렉터리에
   기록 → `data.yaml` 생성(nc=80) → `YOLO(...).val()` 호출 → mAP 기록.

## 3. 시나리오

| 축 | 값 |
|---|---|
| split | LOD_split(321) / PASCAL_split(321) / Shuffle_split(642) |
| arm | normal / lowlight / adaptive |
| BLC_OFFSET | 16(현재 배포값) / 1 / 2(2026-07-08 후보 정점) |

3×3×3 = **27개 조합**, `HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` §3.3의
커맨드 그대로(단 `--manifest` 인자 추가).

## 4. 예상 결과 (실행 전, HANDOFF §4 근거)

- **LOD_split**: adaptive mAP ≈ lowlight mAP. 크게 갈리면 체커의 recall
  miss가 mAP에 미치는 영향을 보여주는 것.
- **PASCAL_split**: adaptive vs normal 격차가 핵심 — §7 adaptive
  false-trigger 38.4%가 이 격차의 원인일 것으로 예상(격차가 크면 "판정
  오류의 실제 mAP 비용"을 처음 정량화하는 것).
- **Shuffle_split**: adaptive가 normal/lowlight **둘 다보다 나은지**가
  캠페인 전체의 pass/fail 기준.

## 5. 실험 과정

1. **(07-15, 데스크톱 세션)** LOD/PASCAL/Shuffle_split 구성 + Google
   Drive 업로드 + `HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` 작성,
   노트북(RTX 5060)으로 인수인계.
2. **(07-16, 이번 세션 초반)** 재실행 전 코드 감사 도중, `eval_map_isp.py`의
   `adaptive` arm이 `checker.py`의 `selected_mode()`(배포 C0, dark50>0.80)를
   그대로 호출하고 있음을 발견. HANDOFF 문서 §4가 "adaptive false-trigger
   38.4%"를 이 arm의 근거로 서술했지만, 38.4%는 `checker_adaptive_tau.py`
   기반 별도 측정치이고 C0 자체의 PASCAL false-trigger는 92.9%로 전혀
   다르다 — 두 개의 "adaptive" 개념이 문서에서 섞여 있었다(§7.1 상세).
3. `--limit 10` 스모크 테스트로 버그 재현: PASCAL_split 10프레임에서
   adaptive(0.3439)가 normal(0.3421)이 아니라 lowlight(0.3795)에 가까운
   패턴(수정 전 3개 CSV의 전체 패턴과 일치) 확인.
4. `eval_map_isp.py`에 `--manifest` 인자 추가 — manifest의
   `adaptive_verdict_lowlight`(실제 adaptive-τ 판정)를 stem별로 읽어
   adaptive arm 라우팅에 사용. `--manifest` 미지정 시 기존 C0 폴백 유지
   (하위호환, 단 `--help`에 "이건 adaptive-tau가 아니다" 명시).
5. 수정 검증: PASCAL manifest 로드 결과 127/321(39.6%)가 lowlight 판정 —
   기존 38.4% false-trigger 실측과 부합, C0의 92.9%와는 확연히 다름 → 올바른
   소스를 가리키고 있음을 확인.
6. BLC=16만 먼저 재실행(3 split × 3 arm) → 수정 효과 육안 확인(PASCAL
   adaptive가 normal에 가까워짐, §7.2 전/후 비교).
7. 사용자 승인 하에 BLC{16,1,2} 전체 스윕 실행 — **약 6시간 50분** 소요
   (백그라운드), 27개 조합 전부 완료(exit code 0).

## 6. 실험 결과

전체 27개 조합(mAP@[.5:.95] / mAP@50):

### LOD_split (n=321)
| BLC | normal | lowlight | adaptive |
|---|---|---|---|
| 16 | 0.0341 / 0.0786 | 0.0372 / 0.0842 | **0.0373 / 0.0842** |
| 1  | 0.2005 / 0.3620 | 0.2130 / 0.3823 | **0.2130 / 0.3822** |
| 2  | 0.1935 / 0.3512 | 0.2140 / 0.3810 | **0.2139 / 0.3810** |

### PASCAL_split (n=321)
| BLC | normal | lowlight | adaptive |
|---|---|---|---|
| 16 | 0.2915 / 0.6953 | 0.2995 / 0.7041 | **0.2943 / 0.7034** |
| 1  | 0.3929 / 0.8939 | 0.3948 / 0.8927 | **0.3925 / 0.8942** |
| 2  | 0.3927 / 0.8956 | 0.3930 / 0.9007 | **0.3939 / 0.8964** |

### Shuffle_split (n=642)
| BLC | normal | lowlight | adaptive |
|---|---|---|---|
| 16 | 0.1006 / 0.2467 | 0.1049 / 0.2538 | **0.1037 / 0.2532** |
| 1  | 0.2230 / 0.4883 | 0.2312 / 0.5045 | **0.2309 / 0.5042** |
| 2  | 0.2184 / 0.4808 | 0.2315 / 0.5050 | **0.2317 / 0.5036** |

원본 CSV: `map_isp_lod_split_2026-07-15.csv`, `map_isp_pascal_split_2026-07-15.csv`,
`map_isp_shuffle_split_2026-07-15.csv`.

## 7. 실험 중 이슈 (원인 · 해결)

### 7.1 [주요] adaptive arm이 채택된 adaptive-τ가 아니라 배포된 C0를 측정하고 있었음
- **증상**: 수정 전 실행한 결과(07-15 첫 실행분)에서 PASCAL_split의
  `adaptive` mAP(0.2997)가 `lowlight` 강제 arm(0.2995)과 사실상 동일 —
  "주간 데이터에서도 adaptive가 이득"이라는, 상식과 어긋나는 결과가 나옴.
- **원인**: `eval_map_isp.py:65`가 `checker.selected_mode()`를 직접
  호출하는데, 이 함수는 `DARK_Y=50, DARK_RATIO_PCT=80`(배포된 C0 규칙)을
  구현한다. 반면 채택·검증된 것은 `checker_adaptive_tau.py`의 센서 적응
  τ(Path A)이고, 이 둘은 완전히 다른 임계 규칙이다(PASCAL false-trigger:
  C0 92.9% vs adaptive-τ 38.4%, `pascalraw-adapter-2026-07-13.md` §7). C0가
  PASCAL 프레임의 92.9%를 (오판으로) lowlight로 보내니, "adaptive"가 사실상
  "거의 항상 lowlight"와 같아져 lowlight 강제 arm과 거의 동일한 mAP가
  나온 것 — `HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` 작성 시 이
  둘을 같은 것으로 서술한 것이 근본 원인.
- **해결**: manifest CSV에 이미 계산되어 있던 `adaptive_verdict_lowlight`
  컬럼(진짜 adaptive-τ 판정)을 `eval_map_isp.py`가 stem별로 조회하도록
  `--manifest` 인자를 추가. `checker.py` 자체는 손대지 않음(배포 C0 구현으로
  올바름 — 문제는 eval 하네스가 잘못된 판정 소스를 참조한 것이지 checker.py의
  버그가 아니었음).
- **검증**: 수정 후 PASCAL manifest 로드 시 lowlight 판정 127/321(39.6%) —
  38.4% false-trigger와 부합. 실행 결과에서도 PASCAL adaptive(0.2943)가
  lowlight(0.2995)가 아니라 normal(0.2915)에 훨씬 가까워짐(§6 참고).

### 7.2 실행 시간이 예상보다 훨씬 길었음
- **증상**: BLC=16 단독(9 조합) 실행도 120초 타임아웃을 넘겨 백그라운드로
  전환됐고, 전체 BLC{16,1,2} 스윕(27 조합)은 약 6시간 50분 소요.
- **원인**: PASCAL/SonyNOD 원본 해상도가 크고(각각 약 6034×4012, 5472×3648
  ≈ 20~24MP) demosaic·binning 연산이 순수 numpy 마스킹 기반(벡터화는
  되어 있으나 C/JIT 최적화 없음)이라 프레임당 렌더 비용이 상당함. 27
  조합 × 최대 642프레임 누적.
- **해결/완화**: 별도 최적화 없이 백그라운드 실행으로 완주. 성능 개선은
  이번 캠페인의 목표가 아니므로 비긴급 과제로 기록만 함 — 다음에 이
  규모의 재실행이 필요하면 render 단계 벡터화/캐싱을 먼저 검토할 가치 있음.

### 7.3 [경미] Bash 툴 120초 타임아웃으로 명령이 자동 백그라운드 전환
세션 운영상의 사소한 이슈 — 실행 자체나 결과에는 영향 없음, 진행 상황
확인 방식(로그 파일 tail, `ps -o etime`)만 조정했다.

## 8. 실험 결과 분석

### 8.1 BLC=16(배포값) vs BLC=1/2(후보 정점) — 이 캠페인의 가장 큰 레버
모든 split·모든 arm에서 BLC=1 또는 2가 BLC=16을 압도한다:
- LOD normal: 0.0341 → 0.2005(BLC1)/0.1935(BLC2), **약 5.7배**
- PASCAL normal: 0.2915 → 0.3929/0.3927, **약 +35%**
- Shuffle normal: 0.1006 → 0.2230/0.2184, **약 2.2배**

이는 `isp-pipeline-recalibration-2026-07-08.md`가 SonyNOD 단독으로 냈던
결론(BLC=1~2 근방이 정점)을 **LOD+PASCAL 실 센서 RAW로 처음
재확인**한다. adaptive-τ나 체커 개선보다 **BLC 재보정 자체가 훨씬 더 큰
mAP 레버**라는 뜻이며, 이는 checker-status-2026-07-10.md §4의 "다음
관문"(C1/adaptive 배포)과는 별개로 검토할 가치가 있는 발견이다.

### 8.2 split별 adaptive 거동
- **LOD(야간)**: 모든 BLC에서 adaptive≈lowlight(차이 ≤0.0001) — 예상과
  정확히 일치. `checker-adaptive-tau-realdata-2026-07-13.md`의 높은 recall
  실측과 정합.
- **PASCAL(주간)**: BLC=16/2에서는 adaptive가 normal과 lowlight 사이,
  대체로 normal 쪽에 더 가깝다. BLC=1에서는 adaptive(0.3925)가 셋 중
  최저(normal 0.3929보다도 낮음)인데, 격차(0.0004)가 단일 run 노이즈
  수준이라 "정말 adaptive가 더 나쁘다"고 단정할 근거는 아니다.
- **Shuffle(혼합)**: adaptive는 normal은 항상 이긴다(+0.0031~+0.0133).
  lowlight 대비로는 BLC=16(-0.0012)·BLC=1(-0.0003)에서 근소하게 못
  이기고, **BLC=2에서만 근소하게(+0.0002) 이긴다.** 핸드오프가 정의한
  "adaptive가 둘 다 이겨야 pass"라는 기준은 BLC=2에서, 그것도 노이즈에
  가까운 margin으로만 충족된다 — "확실한 승리"로 과장할 수 없고, 정직하게는
  "동등~근소 우위" 수준으로 기록한다.

### 8.3 부수 발견 — lowlight arm이 주간(PASCAL) 데이터에서도 normal과 같거나 우위
PASCAL_split의 BLC×비교 9개 조합 전부에서 `lowlight ≥ normal`이다(BLC=16에서
격차 +0.008로 크고, BLC=1/2에서는 +0.0001~+0.0019로 작음). 100% 주간
데이터에서 나온 결과라는 점이 이례적 — binning-demosaic의 노이즈 감소
효과, 혹은 2배 노출 게인/해상도 축소가 YOLOv8n 검출에 중립적이거나 오히려
유리하게 작용할 가능성을 시사한다. 방향이 9/9 조합에서 일관돼 우연으로
보기는 어렵지만, **단일 모델(YOLOv8n)·단일 run**이라 이것만으로 결론 내리지
않는다 — 교차 모델(YOLOv8s/SSDLite, SPEC.md §9)로 재검증이 필요한 가설로만
기록.

### 8.4 한계
- 단일 seed·단일 detector(YOLOv8n)만 사용 — SPEC.md §9가 요구하는 교차
  검증(YOLOv8s, SSDLite-MobileNetV3)은 미실시.
- PASCAL_split은 PASCALRAW 4,259장 중 ISO-stratified 321장 샘플 — 전량이
  아니다.
- PASCALRAW ISO[800,1600) n=28 구간의 adaptive 역전(false-trigger 지표,
  `pascalraw-adapter-2026-07-13.md` §7)은 이번 mAP 결과로 직접 설명되지
  않는다(다른 지표) — 필요 시 Shuffle_split manifest의 `iso` 컬럼으로 계층별
  mAP를 추가로 뽑아볼 수 있으나 이번엔 미실시.
- BLC=1/2가 이렇게 크게 이긴다는 것 자체가 review 필요 — 혹시 BLC 값이
  너무 낮아 노이즈/암전류가 그대로 남아있는데 detector가 우연히 그걸
  선호하는 것인지, 실제 화질 개선인지는 육안 확인이나 다른 지표(PSNR 등)로
  별도 확인이 필요하다(이번 캠페인 범위 밖).

## 9. 결론 및 다음 단계

**확정된 사실:**
1. 07-15에 도착했던 최초 결과(수정 전 C0 기반 "adaptive")는 무효 처리 —
   이 문서의 27개 조합이 정본이다.
2. BLC=16→1/2 전환이 checker/adaptive보다 훨씬 큰 mAP 레버라는 것을 실
   RAW 데이터로 처음 확인했다.
3. adaptive-τ가 "두 강제 arm보다 항상 우위"라는 강한 주장은 아직 성립하지
   않는다(BLC=2에서만, 근소하게) — 과장 금지 원칙 유지.

**다음 단계 후보(우선순위 미확정, 사용자 결정 필요):**
- BLC=1/2 재보정을 실제로 반영할지 결정 — 반영 시 `make verify`
  bit-exact 재확인 + HW golden 재생성 필요(checker-status-2026-07-10.md §4
  관문 4와 병행 검토).
- lowlight>normal-on-PASCAL 가설을 YOLOv8s/SSDLite로 교차검증.
- 필요 시 Shuffle_split의 ISO 계층별 세부 mAP 분석(PASCALRAW ISO[800,1600)
  역전과의 연관성 확인).
