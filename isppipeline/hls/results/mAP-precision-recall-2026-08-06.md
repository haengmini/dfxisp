# mAP, precision, and recall cross-detector ISP re-simulation (2026-08-06)

## Scope and method

This CPU-only run evaluated 100 images per arm with `blc_offset=2`: daylight `normal`, `default_isp`, and `default_isp_noawb`; night `normal`, `lowlight`, `lowlight_isp`, and the already-supported `lowlight_isp_subsample`. Each arm was evaluated with YOLOv8n and SSDLite MobileNetV3 Large: 14 arm-detector combinations and 1,400 image inferences. No requested minimum arm was skipped. The supported `lowlight_isp_nodenoise` variant was not present in the supplied renderer, so the cheap existing subsample variant was used instead.

mAP@[.5:.95] and mAP@50 are exactly `COCOeval.stats[0]` and `stats[1]`. Precision/recall are independent scalar operating-point metrics: within each image, predictions are sorted by confidence and greedily matched to unmatched same-category ground truths at IoU >= 0.50; TP/FP/FN are aggregated over the full dataset. They are not COCOeval PR-curve summaries.

The unchanged standard inference thresholds were YOLOv8n `0.25` (Ultralytics predict default) and SSDLite `0.001` (the instantiated torchvision model's `score_thresh`). This threshold difference is essential when comparing scalar precision/recall across detectors.

## Daylight - pascal_split_100

| Arm | Detector | mAP@[.5:.95] | mAP@50 | Precision | Recall |
|---|---|---:|---:|---:|---:|
| normal | YOLOv8n | 0.392081 | 0.872496 | 0.600000 | 0.900000 |
| default_isp | YOLOv8n | 0.408189 | 0.902768 | 0.594828 | 0.920000 |
| default_isp_noawb | YOLOv8n | 0.391505 | 0.874920 | 0.604444 | 0.906667 |
| normal | SSDLite-MobileNetV3-Large | 0.364973 | 0.839081 | 0.004833 | 0.966667 |
| default_isp | SSDLite-MobileNetV3-Large | 0.382538 | 0.853223 | 0.004900 | 0.980000 |
| default_isp_noawb | SSDLite-MobileNetV3-Large | 0.364488 | 0.837874 | 0.004833 | 0.966667 |

## Night - split_nod

| Arm | Detector | mAP@[.5:.95] | mAP@50 | Precision | Recall |
|---|---|---:|---:|---:|---:|
| normal | YOLOv8n | 0.125958 | 0.223127 | 0.727273 | 0.282004 |
| lowlight | YOLOv8n | 0.141024 | 0.253394 | 0.729614 | 0.315399 |
| lowlight_isp | YOLOv8n | 0.144668 | 0.262821 | 0.739669 | 0.332096 |
| lowlight_isp_subsample | YOLOv8n | 0.138063 | 0.245539 | 0.708155 | 0.306122 |
| normal | SSDLite-MobileNetV3-Large | 0.101024 | 0.197298 | 0.006867 | 0.382189 |
| lowlight | SSDLite-MobileNetV3-Large | 0.115180 | 0.230700 | 0.007233 | 0.402597 |
| lowlight_isp | SSDLite-MobileNetV3-Large | 0.124960 | 0.242748 | 0.007533 | 0.419295 |
| lowlight_isp_subsample | SSDLite-MobileNetV3-Large | 0.116312 | 0.224827 | 0.006967 | 0.387755 |

## v2 versus v1 findings

- Condition-matched primary comparisons agree across detectors. Daylight `default_isp` beats v1 `normal` on both mAP measures and recall for both detectors: YOLOv8n: mAP@[.5:.95] +0.016107, mAP@50 +0.030271, Precision -0.005172, Recall +0.020000; SSDLite-MobileNetV3-Large: mAP@[.5:.95] +0.017565, mAP@50 +0.014142, Precision +0.000067, Recall +0.013333.
- Night `lowlight_isp` beats v1 `lowlight` on both mAP measures, precision, and recall for both detectors: YOLOv8n: mAP@[.5:.95] +0.003645, mAP@50 +0.009427, Precision +0.010056, Recall +0.016698; SSDLite-MobileNetV3-Large: mAP@[.5:.95] +0.009780, mAP@50 +0.012048, Precision +0.000300, Recall +0.016698.
- The prior YOLO-only daylight conclusion was mixed; under the required default-inference operating point and direct COCOeval used here, it is no longer mixed for the primary `default_isp` arm. Both detectors show positive mAP deltas. However, `default_isp_noawb` does not share that result: YOLOv8n: mAP@[.5:.95] -0.000576, mAP@50 +0.002424, Precision +0.004444, Recall +0.006667; SSDLite-MobileNetV3-Large: mAP@[.5:.95] -0.000485, mAP@50 -0.001207, Precision +0.000000, Recall +0.000000. Thus the daylight conclusion still depends on the v2 arm configuration, specifically AWB.
- The night subsample ablation is not a win: YOLOv8n: mAP@[.5:.95] -0.002961, mAP@50 -0.007855, Precision -0.021459, Recall -0.009276; SSDLite-MobileNetV3-Large: mAP@[.5:.95] +0.001132, mAP@50 -0.005874, Precision -0.000267, Recall -0.014842. Both detectors prefer deployed `lowlight_isp` over this variant.

## What precision/recall adds

For YOLO, v2's main visible gain is recall: daylight rises from 0.900000 to 0.920000 while precision slips from 0.600000 to 0.594828; night recall rises from 0.315399 to 0.332096 and precision rises from 0.729614 to 0.739669. Therefore daylight mAP improvement does not mean an across-the-board operating-point improvement: it trades a small amount of precision for recall.

SSDLite exposes a much stronger threshold effect hidden by mAP. At its standard `0.001` score threshold it returns 300 predictions per image, yielding recall 0.966667-0.980000 in daylight but precision only 0.004833-0.004900. Night precision is likewise only 0.006867-0.007533. These values are correct for the mandated untuned default operating point and should not be read as detector quality independent of threshold.

## Runtime and execution notes

The artifact-producing render cache was created in a measured command that ran 3:02:32 before its original bulk-list YOLO inference was killed at 13.35 GiB peak RSS. Rendering itself had completed fully before that failure. The corrected memory-safe scoring pass reused the verified 700-image render cache and took 6:40.68 wall-clock (`/usr/bin/time`; script scoring interval 377.17 s, peak RSS 1.90 GiB). Total measured time for those two commands was 3:09:12.68, including the failed bulk inference. Two short preliminary render attempts were abandoned before final rendering after diagnosing worker/process memory behavior and are not part of metric counts.

Only the final corrected pass contributed metrics: exactly 14 arm-detector combinations, 100 images each, 1,400 image inferences. The failed pass produced no metric CSV rows.

## Artifacts

- `map_precision_recall_dual_detector_2026-08-06.csv` - unified numeric source of truth
- Four per-detector/day-condition metric charts
- `v2_v1_cross_detector_contrast_2026-08-06.png` - signed v2-minus-v1 deltas
- `map_precision_recall_dual_detector_2026-08-06.run.json` - TP/FP/FN and timing audit details
