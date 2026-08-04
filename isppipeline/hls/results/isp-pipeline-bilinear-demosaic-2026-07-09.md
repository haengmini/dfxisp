<!--
=============================================================================
File   : isppipeline/hls/results/isp-pipeline-bilinear-demosaic-2026-07-09.md
Date   : 2026-07-09
Function: `isp-pipeline-recalibration-2026-07-08.md`의 BLC 재보정 스윕을, 그 문서
          §5(남은 질문/한계)가 열어둔 R/B 데모자이크 fidelity gap(single-nearest-tap
          vs golden의 bilinear)을 닫은 새 파이프라인으로 재실행.
Goal   : `baseline_isp_pipeline.py`/`checker.py`의 `_demosaic_rggb16`을 golden
          (`gen_golden_vectors.demosaic_rggb12`)과 bit-exact한 bilinear로 교체한
          뒤에도 07-08의 두 결론 -- (1) arm 순서 역전 유지, (2) normal이 BLC=1
          부근에서 정점 -- 이 그대로 성립하는지, 그리고 데모자이크 fidelity 자체가
          mAP 수치에 미치는 영향이 있는지 검증.
=============================================================================
-->
# R/B 데모자이크 bilinear 수정 + mAP 재측정 (2026-07-09)

## 1. 왜 다시 돌렸나 -- R/B 데모자이크 fidelity gap

2026-07-08 리뷰(PR #8)가 `baseline_isp_pipeline.py`/`checker.py`의 `_demosaic_rggb16`을
발견 당시 그대로 두고 "out of scope"로 명시했던 문제: 두 파일의 R/B 채널 데모자이크가
크로스컬러 위치(R 픽셀에서 B 값, B 픽셀에서 R 값 등)에서 **single-nearest-tap**(가장
가까운 동색 픽셀 하나만 사용)을 쓰고 있었던 반면, golden 모델
(`gen_golden_vectors.demosaic_rggb12`, `src/dfxisp_accel.cpp`의 bit-exact 미러)은
같은 위치에서 **2~4탭 이웃 평균(bilinear)**을 쓴다. `internal_edge_smoke.py`의
경계-clamp 회귀 테스트는 두 proxy 파일을 *자기 자신과만* 비교했기 때문에 이 불일치를
잡을 수 없었다 -- self-consistent pair는 구조적으로 이런 종류의 버그를 못 잡는다는,
이 저장소가 이미 알고 있는 교훈(`verify_binning_cross_check.py`의 존재 이유)과 정확히
같은 패턴.

수정: `baseline_isp_pipeline.py`/`checker.py`의 `_demosaic_rggb16`을 golden과 동일한
bilinear 알고리즘(R/B 위치별로 2탭 또는 4탭 이웃 평균, clamp-to-edge 경계 유지)으로
교체. 새 독립 fuzz 게이트 `verify_demosaic_cross_check.py`를 추가해 golden
`demosaic_rggb12`와 두 proxy 구현을 200개 랜덤 그리드 × 111,820픽셀에서 bit-exact
검증(`make verify`/`make py-verify`에 편입). `low_light_isp_pipeline.py`의
`_bin_demosaic_rggb16`(2x2 binning-demosaic)은 이미 `verify_binning_cross_check.py`로
bit-exact 검증되어 있던 별개 알고리즘이라 이번 수정 대상이 아니다.

## 2. 새 mAP 표 (yolov8n, n=321, `map_isp_sonynod_bilinear_yolov8n.csv`)

| BLC_OFFSET | normal mAP@.5:.95 | normal mAP@50 | lowlight mAP@.5:.95 | lowlight mAP@50 | adaptive mAP@.5:.95 | adaptive mAP@50 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.1904 | 0.3439 | 0.1965 | 0.3592 | 0.1965 | 0.3589 |
| 1 | **0.2005** | **0.3620** | 0.2130 | 0.3823 | 0.2131 | 0.3823 |
| 2 | 0.1935 | 0.3512 | **0.2140** | **0.3810** | **0.2140** | 0.3806 |
| 4 | 0.1571 | 0.2931 | 0.1759 | 0.3180 | 0.1758 | 0.3179 |
| 8 | 0.0904 | 0.1810 | 0.1030 | 0.2003 | 0.1030 | 0.1998 |
| 16 | 0.0341 | 0.0786 | 0.0372 | 0.0842 | 0.0371 | 0.0839 |

## 3. 구(07-08, single-tap) vs 신(07-09, bilinear) 직접 비교

**normal arm만 변경됨** -- `lowlight`/`adaptive`는 binning-demosaic 경로라 이번 수정과
무관하고, 실제로 아래 표에서 보듯 소수점 4자리까지 사실상 동일(adaptive의 아주 작은
차이는 checker의 dark-ratio 판정에 쓰이는 demosaic이 바뀌면서 생긴 노이즈 수준의
재계산 오차 -- 여전히 321장 전부가 dark로 판정돼 실질적으로 lowlight와 동일한 경로를 탄다).

| BLC_OFFSET | normal 구(single-tap) | **normal 신(bilinear)** | Δ | Δ% |
|---:|---:|---:|---:|---:|
| 0 | 0.1849 | **0.1904** | +0.0055 | **+3.0%** |
| 1 | 0.1932 | **0.2005** | +0.0073 | **+3.8%** |
| 2 | 0.1900 | **0.1935** | +0.0035 | **+1.8%** |
| 4 | 0.1625 | **0.1571** | −0.0054 | **−3.3%** |
| 8 | 0.0918 | **0.0904** | −0.0014 | **−1.5%** |
| 16 | 0.0344 | **0.0341** | −0.0003 | **−0.9%** |

**결론 1 -- arm 순서 역전은 데모자이크 fidelity 수정 이후에도 전 구간에서 유지된다.**
`lowlight/adaptive > normal`이 BLC 0~16 전부에서 여전히 성립한다. 07-08과 07-07(§6ter)에
이어 세 번째로 독립적인 파이프라인 수정을 거치고도 살아남은 결론 -- 데모자이크 fidelity와도
무관한, 구조적으로 매우 견고한 특성으로 봐도 될 것 같다.

**결론 2 -- `normal`의 BLC=1 근방 정점 위치는 그대로 유지된다.** 07-08이 정정했던
"`normal`도 비단조, BLC=1 부근에서 약한 정점"이라는 결론이 bilinear 데모자이크에서도
동일하게 재현된다(BLC=1의 0.2005가 BLC=0의 0.1904, BLC=2의 0.1935보다 높음).

**결론 3 -- 데모자이크 fidelity 수정 자체가 만든 효과: BLC가 낮을 때는 이득, 높을 때는
손실, 방향이 뒤집힌다.** `normal` mAP가 BLC=0/1/2에서는 bilinear가 single-tap보다
**올랐고**(+1.8%~+3.8%), BLC=4/8/16에서는 오히려 **떨어졌다**(−0.9%~−3.3%). 부호가
BLC=2와 4 사이에서 뒤집힌다. 짐작 가능한 설명: BLC가 낮을 때는 원신호가 충분히 남아있어
더 정확한(더 많은 이웃을 평균하는) 데모자이크가 노이즈를 줄이는 이득으로 작동하지만,
BLC가 높아 신호 자체가 이미 깎여나간 구간에서는 여러 이웃을 평균하는 게 오히려 이미 깎인
값들을 더 뭉개는 방향으로 작동할 수 있다 -- 다만 이건 **단일 실행(시드 1회)에서 나온
경향**이라 이 설명 자체를 확정된 결론으로 취급하면 안 된다. 확인하려면 최소한 데이터셋을
바꾸거나 프레임 서브샘플을 바꿔 반복 측정해 이 부호 반전이 노이즈가 아닌지 봐야 한다.

**결론 4 -- lowlight/adaptive 대비 normal의 margin도 BLC에 따라 반대 방향으로 움직인다.**
결론 3의 직접적인 귀결: normal이 오른 구간(BLC 0~2)에서는 margin이 줄고(예: BLC=2에서
+12.6%→+10.6%), normal이 내린 구간(BLC 4~16)에서는 margin이 늘었다(예: BLC=8에서
+12.2%→+13.9%). 즉 "데모자이크를 고치면 격차가 줄어든다"던 07-08 문서의 관찰(그 경우는
gamma 버그 수정 얘기였지만)이 이번엔 BLC 구간별로 부호가 다르게 나타나 단순하지 않다.

## 4. 로그/타이밍

- 스윕: `python3 eval_map_isp.py --root ../../../sonynod_test --blc-offsets
  0,1,2,4,8,16 --tag SonyNOD-Bilinear --model yolov8n.pt --out
  ../results/map_isp_sonynod_bilinear_yolov8n.csv`
- 6개 BLC 값 × 3 arm = 18회의 `model.val()`(321장씩), 각 BLC 값마다 이미지 합성(321장 ×
  3 arm, 원본 해상도 ~2000만 화소 real-RAW)도 포함. 시작 11:36 KST, 완료(CSV write)
  16:34 KST -- **총 약 4시간 58분** 소요(GPU: RTX 5060 Laptop, CUDA). 07-08 실행(4시간
  32분)보다 소폭 길지만, bilinear 데모자이크가 shift/평균 연산을 더 쓰는 걸 감안하면
  합리적인 범위.
- 로그 전체에 에러/트레이스백/NaN/경고 없음, 18행 전부 정상 종료. GPU는 각 BLC 값의
  이미지 합성(CPU-only numpy 단계) 동안은 0% 유휴였다가 `model.val()` 단계에서만
  사용됨 -- 의도된 동작(합성과 추론이 순차 실행).

## 5. 남은 질문 / 한계

- 결론 3/4의 BLC-부호-반전은 단일 실행 결과다. 반복측정(다른 랜덤시드나 데이터 서브셋)
  없이는 이게 실제 신호인지 mAP 측정 자체의 노이즈(YOLO validation은 결정론적이지만,
  321장이라는 작은 표본 크기에서 개별 프레임의 검출 결과가 몇 개만 바뀌어도 mAP가
  흔들릴 수 있음)인지 구분할 수 없다.
- 여전히 §6ter/07-08과 같은 한계: 이 스윕은 gain/AWB/gamma 중 BLC_OFFSET만 격리한
  ablation이다.
- `checker.py`의 dark-ratio 임계값은 이번 데모자이크 수정과 무관하게 그대로이며,
  SonyNOD 321장 전부가 여전히 dark 판정이라 `adaptive`≈`lowlight`가 그대로 재현됐다.
- 구 결과(`results/map_isp_sonynod_blcfix_yolov8n.csv`,
  `isp-pipeline-recalibration-2026-07-08.md`)는 수정/삭제하지 않고 이력 보존.

## 재현

```bash
cd isppipeline/hls/tools
python3 eval_map_isp.py --root ../../../sonynod_test \
    --blc-offsets 0,1,2,4,8,16 --tag SonyNOD-Bilinear --model yolov8n.pt \
    --out ../results/map_isp_sonynod_bilinear_yolov8n.csv
```

## 산출물

- 코드: `tools/baseline_isp_pipeline.py`/`tools/checker.py`(`_demosaic_rggb16`을
  bilinear로 교체), `tools/verify_demosaic_cross_check.py`(신규 cross-check 게이트),
  `Makefile`(`cross-check`/`py-verify`에 새 게이트 편입), `tools/internal_edge_smoke.py`
  / `README.md`(fidelity gap이 닫혔음을 반영하도록 갱신).
- 결과: `results/map_isp_sonynod_bilinear_yolov8n.csv`(신규 18행).
- superseded 아님(병기): `results/map_isp_sonynod_blcfix_yolov8n.csv`,
  `results/isp-pipeline-recalibration-2026-07-08.md` -- normal arm 수치만 갱신되고
  lowlight/adaptive는 재확인(동일)되는 관계라 "대체"가 아니라 "보완"에 가깝다.
