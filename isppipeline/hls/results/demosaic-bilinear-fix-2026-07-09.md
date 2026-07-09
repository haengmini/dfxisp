<!--
=============================================================================
File   : isppipeline/hls/results/demosaic-bilinear-fix-2026-07-09.md
Date   : 2026-07-09 KST
Branch : fix/canonical-demosaic-bilinear-2026-07-09 (off origin/main @ 4df120e)
Function: 2026-07-08 Hermes 리뷰가 발견했으나 의도적으로 미수정 상태로
          남겨둔 "canonical SW-eval 파이프라인의 R/B 채널 단일탭 보간이
          golden model/HW의 bilinear와 다르다"는 정합성 격차를 검토하고,
          수정 타당성을 판단해 실제 수정·검증까지 수행한 기록.
Goal   : 사용자 지시("고쳐야할 정당성이 있는지 검토 후 직접 판단")에 대한
          응답 — 판단: 수정한다(아래 §2 근거). mAP 재검증은 GPU 필요라
          별도 라운드로 분리.
Sources: internal_edge_smoke.py(구 버전 docstring, 격차를 최초 명시),
         daily-reports/2026-07-08.md, isp-pipeline-recalibration-2026-07-08.md
=============================================================================
-->
# Canonical 파이프라인 demosaic bilinear 정합성 수정 (2026-07-09)

**작성:** 2026-07-09 KST · **브랜치:** `fix/canonical-demosaic-bilinear-2026-07-09`
(`origin/main`의 `4df120e` 기준, PR #8까지 병합된 상태에서 분기)

## 1. 배경 — 무엇이 미결로 남아 있었나

2026-07-08 "Hermes" 병렬 리뷰가 canonical SW-eval 파이프라인
(`baseline_isp_pipeline.py`, `checker.py`)의 `_demosaic_rggb16`을 점검하다
발견했지만 **의도적으로 수정하지 않고** `internal_edge_smoke.py`의
docstring에만 다음과 같이 기록해둔 격차였다:

> "the proxy files use single-nearest-tap for cross-color positions ... a
> separate, larger fidelity gap the 2026-07-08 review did not previously
> catch and is out of scope for this boundary fix."

## 2. 검토 — 실재하는가, 고칠 정당성이 있는가

### 2.1 사실관계 확인 (코드 직접 대조)

세 구현을 나란히 대조했다:

| 구현 | 위치 | R/B 채널(교차색 위치) |
|---|---|---|
| **HW(정본)** | `src/dfxisp_accel.cpp` `demosaic_rggb12()` | G-위 위치: 2-tap 평균 / 대각 위치: 4-tap 평균 |
| **golden(정본)** | `tools/gen_golden_vectors.py` `demosaic_rggb12()` | 위와 동일(코드 자구 일치) |
| **canonical SW-eval(문제)** | `checker.py`, `baseline_isp_pipeline.py` `_demosaic_rggb16()` | **단일 탭**(이웃 평균 없이 한 방향만 샘플) |

G 채널은 세 구현 모두 4-tap 평균으로 일치한다 — **문제는 R/B 채널에만**
있다. 아카이브된 `isp_pipeline_ver1.py`도 동일 버그를 갖고 있었으나,
07-08 리팩터로 "canonical"이라 이름 붙은 새 파일들이 **버그를 그대로
복사해왔다**(원인: `gen_golden_vectors.py`의 스칼라 per-pixel 구현과
한 번도 교차검증되지 않은 채, 벡터화된 재구현이 별도로 작성됨).

### 2.2 이게 "설계상 트레이드오프"가 아니라 "버그"인 이유

이 두 파일의 존재 목적 자체가 "HW를 정확히 미러링하는 SW 대체물"이다
(파일 docstring에 명시: "bit-exact-intent SW proxy of dfxisp_accel.cpp").
참조할 정답(HW 공식)이 이미 명확하고 이미 다른 파일(golden)에서 정확히
구현되어 있다 — BLC 상수나 체커 임계값처럼 "무엇이 최적인가"를 실험으로
정해야 하는 설계 결정이 아니라, **이미 정해진 정답을 잘못 베낀 것**이다.
즉 수정에 판단의 모호함이 없다.

### 2.3 영향 범위(blast radius) 판단

- **영향받는 것:** `normal`/`none` arm의 이미지 내용(전체 Stage 3 mAP
  캠페인이 이 함수를 거친다).
- **영향받지 않는 것:** `lowlight` arm — `low_light_isp_pipeline.py`의
  binning-demosaic은 별도 함수(`_bin_demosaic_rggb16`)이고
  `verify_binning_cross_check.py`로 이미 golden과 bit-exact 검증되어
  있다(§4에서 재확인). HW 소스(`dfxisp_accel.cpp`)나 HLS/Vivado 수치는
  전혀 무관 — 이건 순수 SW 평가 도구의 문제다.
- **수정 리스크:** 낮음. 참조 공식이 명확하고, 기존 golden 대조 인프라
  (`verify_binning_cross_check.py`의 패턴)를 그대로 재사용해 즉시
  검증 가능.

### 2.4 판단

**수정한다.** 근거: (i) 명확한 정답 대비 버그, 설계 트레이드오프 아님,
(ii) 수정 자체는 저위험·저비용, (iii) "canonical"이라는 이름의 존재
이유를 지금 상태로는 충족하지 못함, (iv) 프로젝트가 반복적으로 보여온
관행(BLC·gamma 등 SW/HW 불일치는 발견 즉시 수정 후 재검증)과 일치.
**단, mAP 재검증(§5)은 이번 세션에서 수행하지 않는다** — GPU가 필요한
별도의 큰 캠페인이고, 이 샌드박스는 CUDA를 못 쓴다(§5 참고).

## 3. 수정 내용

`_demosaic_rggb16`을 `gen_golden_vectors.demosaic_rggb12` /
`dfxisp_accel.cpp`와 tap 단위로 동일하게 재작성 — G-native 위치의
교차색은 2-tap(좌우 또는 상하) 평균, 대각(반대색 native) 위치는 4-tap
평균으로 변경. G 채널은 이미 맞았으므로 무변경.

- `isppipeline/hls/tools/checker.py`
- `isppipeline/hls/tools/baseline_isp_pipeline.py`
- (아카이브된 `tools/archive/isp_pipeline_ver1.py`는 프로젝트 관행대로
  이력 보존 목적으로 **수정하지 않음**)

## 4. 검증

신규 게이트 `tools/verify_demosaic_bilinear_cross_check.py`
(`verify_binning_cross_check.py`와 동일한 3자 교차검증 패턴: golden ↔
독립적으로 작성된 SW 사본 2개)을 작성해 `make cross-check` /
`make py-verify`에 편입:

```
[verify_demosaic_bilinear_cross_check] PASS: 300 random grids, 78440 pixel
checks, gen_golden_vectors.demosaic_rggb12 == baseline_isp_pipeline.
_demosaic_rggb16 == checker._demosaic_rggb16 (independent implementations,
bit-exact)
```

수정 전 코드로 동일 스크립트를 재실행(git stash)하면 실제로 실패함을
회귀 확인했다(예: `golden=(1428,995,1332) != sw=(1428,995,2779)` — R은
native 위치라 일치, B는 대각 위치라 불일치, 정확히 예상된 패턴).
`make py-verify` 전체(binning cross-check, scheduler sweep,
internal_edge_smoke 포함)도 전부 PASS — 회귀 없음.

## 5. 영향 규모 사전 측정 (SonyNOD 실센서 RAW 8장, 수정 전후 픽셀 비교)

전체 mAP 재실행은 GPU가 필요하다(07-08 재보정 캠페인은 RTX 5060에서
4시간 32분 소요). 이 세션은 **CUDA를 쓸 수 없는 환경**(`torch.cuda
.is_available()=False`, 드라이버 버전 불일치)이라 mAP 재실행은 다음
GPU 가용 세션으로 미룬다. 대신 **픽셀 값 자체의 변화량**을 값싸게
측정해 어느 정도 규모인지 가늠했다:

| 지표 | 값 |
|---|---|
| 평균 절대차(8-bit 환산), 8프레임 평균 | **0.377 / 255** (≈0.15%) |
| 값이 바뀐 픽셀·채널 비율 | **34.5%** (G는 불변, R/B의 교차색 위치만 이동) |
| 최대 절대차(단일 픽셀) | 최대 raw16 43520 (≈170/255, 8-bit 환산) — 고대비 에지에서 집중 |

**해석:** 평균적으로는 미세(0.15%)하지만, **에지 근방에 국소적으로
집중**된 체계적 변화다(색 모아레/aliasing 감소 방향 — 단일탭은 앨리어싱을
만들고 bilinear는 이를 완화한다). 이 패턴은 (a) BLC·gamma처럼 전 프레임에
걸친 거대한 시스템 변화가 아니므로 **정성적 결론(순서 역전, 체커 방향)을
뒤집을 가능성은 낮음**, 그러나 (b) 객체 검출기가 민감한 바로 그 지점
(경계·질감)에 집중되어 있어 **정밀 mAP 수치는 다시 움직일 것으로 예상**
— R4(gamma fix)와 같은 범주의 "고칠 가치 있음 + 재보정 필요".

## 6. 남은 일 (다음 라운드, 이번 세션에서 미수행)

1. **R5 후보 캠페인:** `eval_map_isp.py`를 이 수정 이후 코드로 재실행,
   Stage 3 R4의 SonyNOD BLC 스윕(`map_isp_sonynod_blcfix_yolov8n.csv`) 및
   COCO/ExDark 조건표를 재확인. GPU 가용 시점에 착수 — §5의 사전측정으로
   보아 정성적 결론 반전은 예상되지 않으나, 정밀 수치는 R4와 마찬가지로
   대체(supersede)될 것이다.
2. **ROADMAP.md 갱신:** `exp/principled-checker-rm-2026-07-05` 브랜치의
   ROADMAP.md에 있는 "미결 항목 — archive된 isp_pipeline_ver1.py 정합성
   격차" 노트를 이 PR 병합 후 "해결됨(고쳐졌고, mAP 재검증은 R5로 예정)"
   으로 갱신할 것 — 두 브랜치가 분기돼 있어 이 문서 하나로는 반영 못함.
3. 본 브랜치를 PR로 올려 리뷰 후 `main` 병합.

## 재현

```bash
cd isppipeline/hls/tools
python3 verify_demosaic_bilinear_cross_check.py --cases 300   # ~수 초, 결정적
cd .. && make py-verify                                        # 전체 회귀 없음 확인
```

## 산출물

- `tools/checker.py`, `tools/baseline_isp_pipeline.py` — `_demosaic_rggb16` 수정.
- `tools/verify_demosaic_bilinear_cross_check.py` — 신규 3자 교차검증 게이트.
- `tools/internal_edge_smoke.py` — docstring 갱신(격차가 닫혔음을 반영).
- `Makefile` — `cross-check`/`py-verify` 타깃에 신규 게이트 편입.
- 본 문서.
