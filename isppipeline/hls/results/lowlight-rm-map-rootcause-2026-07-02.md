<!--
=============================================================================
File   : isppipeline/hls/results/lowlight-rm-map-rootcause-2026-07-02.md
Date   : 2026-07-02
Time   : 23:35 KST
Function: RM_LOW_LIGHT_TONE이 mAP를 개선하지 못하는 원인을 단계별 ablation으로
          분해해 실측 근거를 확보. experiment_ver1_2026-07-02.md §6에서 TODO로
          남겨졌던 "ver2-A: tone(gamma)만 분리 실험"을 실행한 결과.
Goal   : "low-light RM이 왜 mAP를 개선하지 못하는지 이유를 찾아봐" 요청에 대한 응답.
         기존 추정("gamma-4.0 과증폭 + H/2 해상도 손실")을 실측으로 검증/반증.
=============================================================================
-->
# RM_LOW_LIGHT_TONE mAP 미개선 원인 분석 (ablation, 2026-07-02)

## 1. 배경 — 기존 추정과 왜 검증이 필요했나

`experiment-report-2026-07-02.md` §5.2는 "gamma-4.0 과증폭 + H/2 해상도 손실이 원인으로
추정"이라고 적었지만, 이 문장 자체가 **추정("추정")이지 실측이 아니었다.** 게다가
`tools/newrm_pipeline.py`(그 mAP 표를 만든 스크립트)의 gamma-4.0/gain1.25x는 이후
`tools/isp_pipeline_ver1.py`(ver1, 현재 HW와 정합: gain2.0x + gamma2.5)로 이미
교체되었는데도 원인 분석 자체는 갱신되지 않았다. 따라서 low-light RM의 5단계
(2x2 binning → BLC → WB → exposure gain 2.0x → gamma2.5)를 **개별적으로 켜고 끄며**
mAP에 미치는 순수 기여도를 직접 측정했다.

## 2. 방법

`tools/isp_pipeline_ablation.py`(신규) — `isp_pipeline_ver1.py`의 BLC/WB/AWB 상수를
그대로 재사용해 5개 arm을 단계적으로 누적:

| arm | 누적 처리 | 출력 형상 |
|---|---|---|
| `ll_bin_only` | 2x2 RAW bin-demosaic만(방사측정 보정 없음, 순수 `>>8`) | H/2×W/2 |
| `ll_bin_radiometric` | + BLC(−16) + WB(Q8 R286/G256/B307) | H/2×W/2 |
| `ll_bin_gain` | + exposure gain 2.0×(감마 없음, 선형) | H/2×W/2 |
| `ll_bin_full` | + gamma 2.5 (= 현재 `lowlight` arm과 동일) | H/2×W/2 |
| `ll_fullres_tone` | **역(逆) ablation**: 동일 BLC/WB/gain2.0x/gamma2.5를 binning 없이 **원해상도**에 적용 | H×W |

`ll_fullres_tone`이 핵심 대조군이다 — "해상도 손실"과 "톤 커브(BLC/WB/gain/gamma)"의
기여를 분리하기 위해, 톤 체인은 그대로 두고 해상도 손실만 제거했다.

`tools/eval_map_ablation.py`(신규)로 `none`/`normal`/`lowlight`(참조) + 5개 ablation arm을
**동일 프레임 집합·동일 모델(YOLOv8n)**에서 한 번에 측정(재현 가능, `--root`/`--limit` 인자).

## 3. 결과

### 3.1 ExDark (저조도, n=31, mAP@[.5:.95])
| arm | mAP | Δ(직전 단계 대비) | Δ(none 대비) |
|---|---:|---:|---:|
| none (참조) | **0.2201** | — | — |
| `ll_bin_only`(해상도 손실만) | 0.2171 | **−1.4%** | −1.4% |
| `ll_bin_radiometric`(+BLC/WB) | 0.1094 | **−49.6%** | −50.3% |
| `ll_bin_gain`(+gain2.0x) | 0.0842 | −23.0% | −61.7% |
| `ll_bin_full`(+gamma2.5, = lowlight) | 0.0619 | −26.5% | −71.9% |
| `ll_fullres_tone`(같은 톤 체인, 원해상도) | 0.0751 | — | −65.9% |
| normal(참조, 원해상도+동일 BLC/WB+gain1.25x+γ2.2) | 0.1053 | — | −52.2% |

### 3.2 COCO (정상조도, n=39, mAP@[.5:.95])
| arm | mAP | Δ(직전 단계 대비) | Δ(none 대비) |
|---|---:|---:|---:|
| none (참조) | **0.2480** | — | — |
| `ll_bin_only`(해상도 손실만) | 0.2190 | **−11.7%** | −11.7% |
| `ll_bin_radiometric`(+BLC/WB) | 0.2149 | −1.9% | −13.3% |
| `ll_bin_gain`(+gain2.0x) | 0.2054 | −4.4% | −17.2% |
| `ll_bin_full`(+gamma2.5, = lowlight) | 0.2089 | +1.7% | −15.8% |
| `ll_fullres_tone`(같은 톤 체인, 원해상도) | 0.2392 | — | −3.5% |
| normal(참조) | 0.2476 | — | −0.2% |

## 4. 해석 — 원인은 조도 조건에 따라 다르다 (단일 원인 아님)

1. **ExDark(저조도)에서 진짜 범인은 해상도 손실이 아니라 BLC/WB다.** `ll_bin_only`
   (해상도만 절반, 색·밝기 보정 없음)는 `none` 대비 겨우 −1.4% — 사실상 무해하다.
   피해의 **대부분(−49.6%p, 전체 손실의 약 70%)**은 그다음 단계, 즉 BLC(−16)와
   정적 Q8 WB 게인(R×1.117/G×1.0/B×1.199)을 적용하는 순간 발생한다. gain(2.0x)과
   gamma(2.5) 추가는 그보다 작은 추가 손상(각각 −23%, −26.5% 상대)을 낸다.
   → **기존 "H/2 해상도 손실이 원인" 추정은 ExDark에서는 반증된다.**
2. **같은 BLC/WB가 `normal` arm(원해상도)에도 거의 동일한 비율로 피해를 준다**
   (none 대비 −52.2%, `ll_bin_radiometric`의 −50.3%와 거의 같음). 즉 이 손상은
   low-light RM 고유의 문제가 아니라 **두 RM이 공유하는 baseline core(BLC+WB)
   자체의 문제**다 — "저조도 RM을 재설계하면 해결"이 아니라 "공유 core의 정적 WB
   게인이 저조도 장면에서 검출기 pretrained 분포와 어긋난다"는 더 근본적인 문제.
3. **COCO(정상조도)에서는 반대로 해상도 손실이 압도적이다.** `ll_bin_only`만으로
   이미 −11.7%가 발생하고, 이후 BLC/WB(−1.9%)·gain(−4.4%)·gamma(+1.7%, 거의 무해)는
   훨씬 작다. `ll_fullres_tone`(동일 톤 체인, 원해상도)이 −3.5%까지 회복하는 것이
   결정적 증거 — **같은 톤 체인이라도 해상도만 지키면 손상이 1/4로 줄어든다.**
   → COCO에서는 기존 추정("해상도 손실")이 맞다.
4. **정성적 설명(가설, 추가 검증 필요):** ExDark는 원래 신호 대비 잡음비가 낮은
   저조도 장면이라, demosaic 직후 픽셀값에 색 잡음이 많이 섞여 있다. 이 상태에서
   **장면에 무관한 고정(static) WB 게인**을 곱하면 색 잡음이 증폭되고, 사전학습
   detector가 학습한 "정상적인 색 통계"에서 크게 벗어난다(SW proxy 천장 가설과 정합
   — `none`이 raw demosaic만이라 색 통계가 가장 자연스러움). COCO는 이미 신호가
   충분해 WB 게인의 상대적 왜곡이 작고, 대신 픽셀 절반이 사라지는 해상도 손실이
   작은 물체 검출(소형 객체 recall)에 직접 타격을 준다.
5. **checker mAP guardrail의 함의:** low-light RM은 "저조도에서 켜지도록" 설계됐는데
   바로 그 조건(ExDark)에서 공유 baseline core(BLC/WB)가 가장 큰 손상을 준다 —
   **RM이 정확히 필요한 상황에서 정확히 가장 취약**하다는 역설. 반대로 COCO처럼
   RM이 필요 없는 상황에 잘못 걸리면(checker 오판) 해상도 손실로 손해를 본다.

## 5. 설계 함의 (다음 실험 후보)

- **(a) 저조도 전용 WB 완화/비활성화:** dark_ratio가 높을수록 정적 AWB 게인의
  강도를 줄이거나(scene-adaptive WB), BLC 오프셋을 낮춰 저조도에서 색 잡음 증폭을
  줄이는 실험 — 이번 ablation이 직접 가리키는 후속 액션.
- **(b) COCO/밝은 장면 대비책:** `ll_fullres_tone`이 거의 `none`에 근접했다는 것은,
  **저조도가 아닌 장면에 RM이 오적용되더라도 해상도만 지키면 피해가 제한적**임을
  시사 — checker 오판(false-trigger)에 대한 안전판으로 Policy A(해상도 반감)보다
  Policy B(해상도 보존)가 더 안전할 수 있음(RESEARCH §11 (b) 항목과 연결).
- **(c) 여전히 SW proxy 한계:** pseudo-RAW는 실제 센서 노이즈가 없는 역변환
  이미지라, "저조도 색잡음 증폭" 가설은 **실제 RAW 센서 데이터**로 재검증해야
  확정할 수 있다. 최종 판정은 보드 DPU + real-RAW 단계.

## 6. 재현

```bash
cd isppipeline/hls
python3 tools/eval_map_ablation.py --root ../../data/exdark_val --tag ExDark \
    --model yolov8n.pt --limit 71 --out results/map_ablation_exdark_yolov8n.csv
python3 tools/eval_map_ablation.py --root ../../data/coco_val --tag COCO \
    --model yolov8n.pt --limit 80 --out results/map_ablation_coco_yolov8n.csv
```

## 7. 한계
- n=31(ExDark)/n=39(COCO) — 기존 Stage 3(n=71/80)보다 작은 유효 프레임 부분집합
  (raw==jpg 크기 일치 + limit 순서 교차). **같은 실행 내에서 만든 `none`/`normal`/
  `lowlight` 참조값과만 비교할 것** — 다른 문서의 n=71/80 표와 절대값을 직접
  비교하지 말 것(표본이 다름). 경향(부호·상대크기)은 일관되게 재현됨.
- YOLOv8n 단일 모델만 사용 — Stage 3처럼 3-detector 교차검증은 하지 않음(경향
  검증이 목적이라 우선순위를 낮춤). 필요시 YOLOv8s/SSD로 확장 가능.
- §4.4의 "색 잡음 증폭" 설명은 가설이며, 정량 검증(색 잡음 지표 측정)은 하지 않음.

## 산출물
- 코드: `tools/isp_pipeline_ablation.py`, `tools/eval_map_ablation.py`
- 결과: `results/map_ablation_exdark_yolov8n.csv`, `results/map_ablation_coco_yolov8n.csv`
