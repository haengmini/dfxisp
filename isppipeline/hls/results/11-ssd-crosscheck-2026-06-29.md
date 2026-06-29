# B1 — 2차 detector 교차검증 (SSD MobileNet) 2026-06-29

목표: YOLO 계열에서 찾은 mAP-guardrail **variant 순서**가 **detector에 무관**한지를,
구조가 다른 detector 계열인 **SSD + MobileNet**(`ssdlite320_mobilenet_v3_large`,
torchvision, COCO 사전학습)로 동일 이미지를 재채점하여 검증한다.

- 하니스: `tools/eval_map_ssd.py` (`eval_map_coco.py`가 이미 만든 variant 이미지를
  재사용; GT COCO80 id → COCO91로 변환 후 pycocotools COCOeval로 ExDark 존재 12개
  카테고리에 대해 채점).
- 장치: CPU (호스트 CUDA 드라이버가 torch 2.12에 비해 너무 오래됨); SSDLite는 가볍다.
- ISP 변환은 YOLO 실행과 동일 — detector만 교체한다.

## 저조도 regime — ExDark pseudo-RAW (n=260, bilinear binning)

| variant  | YOLOv8n | YOLOv8s | SSDLite-MNv3 |
|----------|--------:|--------:|-------------:|
| static   |  0.1492 |  0.1714 |       0.1052 |
| **reg_only** | **0.1585** | **0.1902** | **0.1098** |
| dfx_bin  |  0.1576 |  0.1511 |       0.1063 |
| dfx_fp   |  0.0879 |  0.1018 |       0.0656 |

출처: `results/map_exdark_bilbin.csv`, `map_exdark_yolov8s.csv`, `map_exdark_ssd.csv`.

**detector-무관 결론 (저조도):**
1. **register-only가 최고(또는 공동 최고) 경로**임이 세 detector 모두에서 성립 →
   정확도는 register-fast path가 담당한다(방향 A).
2. **DFX-FP가 명백히 최저**임이 세 detector 모두에서 성립(최고 대비 약 40–55 % 낮음) →
   screening 판정(DFX-FP 탈락)은 YOLO 특유의 artifact가 아니다.
3. **DFX-Bin은 static/reg_only 옆 top cluster를 유지**한다(중간 둘은 detector 노이즈
   범위에서 자리 교환) → DFX-Bin의 mAP guardrail이 detector에 무관하게 성립한다.
   (yolov8s는 bin을 static보다 약간 아래로, SSD/yolov8n은 static과 같거나 위로 둔다 —
   모두 ~0.01–0.02 mAP 이내, 즉 guardrail-일관.)

## 정상조도 regime — COCO pseudo-RAW (n=347, bilinear binning)

| variant  | YOLOv8n | SSDLite-MNv3 |
|----------|--------:|-------------:|
| **static** | **0.2984** | **0.2001** |
| reg_only |  0.2952 |       0.1968 |
| dfx_bin  |  0.2839 |       0.1930 |
| dfx_fp   |  0.2518 |       0.1743 |

출처: `results/map_coco_bilbin.csv`, `map_coco_ssd.csv`.

**detector-무관 결론 (정상조도):** 순서가 **동일하다** —
두 detector 모두 `static ≥ reg_only > dfx_bin > dfx_fp`. 저조도 처리는 주간에
**이득이 없다** → 장면 적응 스위칭의 필요성(기여 1/3)을 견고하게 확인한다.

## 시사점
논문의 두 핵심 주장은 **detector에 종속되지 않는다**:
- *정확도 → register 경로* (저조도에서 reg_only 최고, 모든 detector), 그리고
- *DFX-FP는 올바르게 탈락* (저조도에서 최저, 모든 detector),
- *DFX-Bin은 mAP guardrail 통과* (top cluster, 모든 detector),
- *주간 스위칭은 정당* (정상조도에서 static 최고, 모든 detector).

SSDLite-MNv3의 절대 수치는 YOLO보다 낮으나(이 pseudo-RAW 저조도에서 백본이 약함),
**상대 순서 — guardrail이 의존하는 유일한 것 — 는 보존된다**. 정확한 Vitis-AI
`tf_ssdmobilenetv1`(TF1.15)은 on-board DPU end-to-end 단계용으로 따로 둔다(배치
관점의 별개 질문).
