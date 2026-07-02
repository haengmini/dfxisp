<!--
=============================================================================
File   : isppipeline/hls/results/experiment_ver1_2026-07-02.md
Date   : 2026-07-02
Time   : 12:10 KST
Function: ver1 ISP 파이프라인(RAW-domain-first 순서) 실험 결과 보고서
Goal   : ver0(post-demosaic 순서, tools/newrm_pipeline.py) 대비 ver1
         (tools/isp_pipeline_ver1.py)이 mAP를 회복하는지 검증하고 정직하게 기록
=============================================================================
-->
# ver1 ISP 파이프라인 실험 — RAW-domain-first 순서

> ver0(현행): `demosaic → BLC → AWB → CCM`, gamma는 저조도만.
> **ver1(제안)**: `BLC → [binning(LL)] → WB → exposure gain → demosaic → CCM → gamma → pack`
> (보정을 RAW 도메인·정밀도에서 먼저, normal에도 gain, 모든 모드에 gamma, 저조도 gamma 완화).
> 도구: `tools/isp_pipeline_ver1.py`, `tools/eval_map_ver1.py`. 데이터: pseudo-RAW COCO/ExDark(SW proxy, CPU).

## 1. ver1 파라미터 (vs ver0)

| 항목 | ver0 | ver1 |
|---|---|---|
| 보정 도메인 | demosaic 후 8-bit | **demosaic 전 RAW16(>>8은 마지막)** |
| BLC | −16 (8-bit) | −16 RAW16(=`16<<8`) |
| WB(AWB) | demosaic 후 | demosaic 전 per-channel Q8 (286/256/307) |
| normal exposure gain | **없음(identity)** | **1.25×(5/4) 추가** |
| low-light gain | 1.25× | 2.0× |
| gamma (normal) | **없음** | **γ2.2 추가** |
| gamma (low-light) | γ4.0 | **γ2.5(완화)** |

## 2. 밝기 sanity (Y mean, n=40) — 다크닝 버그 수정 확인

| dataset · arm | ver0 | ver1 |
|---|---|---|
| ExDark · none | 15.6 | 15.6 (참조 불변) |
| ExDark · normal | **12.0 (none보다 어두움)** | **23.4 (none보다 밝음)** |
| COCO · normal | 47.8 | 91.5 (γ로 sRGB 쪽) |

→ ver0의 "normal이 오히려 어두워지는" 버그를 ver1이 해소.

## 3. mAP 결과 — 조건표 A~G, ver0 vs ver1

### mAP@[.5:.95], YOLOv8n
| 조건 | arm | ver0 | ver1 | Δ |
|---|---|---|---|---|
| A | ExDark·none | 0.1561 | 0.1561 | (참조) |
| B | ExDark·normal | 0.0680 | **0.0826** | +21% |
| C | ExDark·lowlight | 0.0554 | **0.0586** | +6% |
| D | COCO·none | 0.3276 | 0.3276 | (참조) |
| E | COCO·normal | 0.2879 | 0.2772 | −4% |
| F | COCO·lowlight | 0.2574 | **0.2647** | +3% |

### 교차검증 (mAP@[.5:.95])
| dataset · arm | YOLOv8n v0→v1 | YOLOv8s v0→v1 | SSDLite-MNv3 v0→v1 |
|---|---|---|---|
| ExDark·none | 0.156→0.156 | 0.224→0.224 | 0.104→0.104 |
| ExDark·normal | 0.068→**0.083** | 0.125→**0.147** | 0.044→**0.053** |
| ExDark·lowlight | 0.055→**0.059** | 0.128→**0.138** | 0.033→**0.047** |
| COCO·none | 0.328→0.328 | 0.428→0.428 | (COCO SSD 미측정) |
| COCO·normal | 0.288→0.277 | 0.378→**0.384** | — |
| COCO·lowlight | 0.257→**0.265** | 0.340→0.341 | — |

(SSD COCO는 검출기 측 작업이 별도 진행 중이라 이번엔 미측정.)

## 4. 결론 (정직)

1. **ver1은 저조도 ISP arm을 일관되게 개선.** ExDark normal이 세 검출기 모두에서 +약17~21%,
   lowlight도 상승. RAW-domain BLC/WB/gain + normal gain + gamma 추가가 유효했음(다크닝 버그 해소).
2. **그러나 `none`(무처리)이 여전히 모든 조건·검출기에서 최고.** 순서 `none > normal ≳ lowlight` 불변.
   ver1은 격차를 좁혔을 뿐 역전하지 못함.
3. **COCO normal은 소폭 변동(±)** — γ2.2가 정상조도에선 과밝게 만들기도 함(Y 47.8→91.5).
4. ⇒ **guardrail 결론(SW proxy에서 최소 처리가 mAP 최고) 유지** → 방향 A 강화(mAP는 최소/register,
   DFX/RM은 자원·전력으로 정당화).

## 5. 한계 · 해석 주의

- **SW proxy 천장:** 검출기는 COCO sRGB로 사전학습됐고, pseudo-RAW의 `none`(plain demosaic)이
  그 분포에 이미 가장 가깝다. ISP 변환은 분포를 밀어내 mAP가 내려가기 쉽다. **공정한 최종 판정은
  real-RAW + ISP 출력으로 (재)학습/양자화한 검출기(보드 DPU 단계)** 가 필요.
- 즉 본 결과는 "SW proxy에서 ISP 후처리가 사전학습 검출기 mAP를 못 올린다"는 경계이지, 최종
  기여(자원/전력)를 부정하지 않는다.

## 6. 다음 (ver2 후보)

- **ver2-A:** tone(gamma)만 sRGB-encode, BLC/gain 제거 — "무엇이 mAP에 실제로 기여/훼손하는지"
  분리(순수 감마 encode만으로 none에 근접/역전 가능한지).
- **ver2-B:** 정상조도 γ 완화(scene-adaptive gamma) — COCO normal 과밝음 방지.
- **주의:** proxy에서 파라미터를 mAP에 맞춰 과최적화(p-hacking)하지 않는다. 최종 판정은 보드 DPU.
- 교차 검출기(SSD-MobileNetV1/V3 통합)는 별도 작업으로 진행 → 완료 후 ver1/ver2 재채점 병합.

## 산출물
- 도구: `tools/isp_pipeline_ver1.py`, `tools/eval_map_ver1.py`
- 결과: `results/map_ver1_{exdark,coco}_{yolov8n,yolov8s}.csv`, `results/map_ver1_exdark_ssd.csv`
