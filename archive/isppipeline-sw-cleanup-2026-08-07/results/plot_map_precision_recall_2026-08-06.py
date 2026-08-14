#!/usr/bin/env python3
"""Generate plots and the Markdown report directly from the unified CSV."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
CSV = HERE / "map_precision_recall_dual_detector_2026-08-06.csv"
METRICS = ["mAP_50_95", "mAP_50", "precision", "recall"]
LABELS = ["mAP@[.5:.95]", "mAP@50", "Precision", "Recall"]

with CSV.open() as f:
    rows = list(csv.DictReader(f))
for row in rows:
    for key in METRICS + ["conf_threshold"]:
        row[key] = float(row[key])
    row["n"] = int(row["n"])

detectors = ["YOLOv8n", "SSDLite-MobileNetV3-Large"]
datasets = [("pascal_split_100", "Daylight"), ("split_nod", "Night")]
created = []
for detector in detectors:
    for dataset, condition in datasets:
        subset = [r for r in rows if r["detector"] == detector and r["dataset"] == dataset]
        x = np.arange(len(subset)); width = 0.19
        fig, ax = plt.subplots(figsize=(11, 5.8))
        for i, (key, label) in enumerate(zip(METRICS, LABELS)):
            ax.bar(x + (i-1.5)*width, [r[key] for r in subset], width, label=label)
        ax.set_xticks(x, [r["arm"] for r in subset], rotation=15, ha="right")
        ax.set_ylim(0, 1.0); ax.set_ylabel("Metric value")
        ax.set_title(f"{condition} ISP comparison - {detector}")
        ax.grid(axis="y", alpha=.25); ax.legend(ncols=4, loc="upper center")
        fig.tight_layout()
        slug = "yolov8n" if detector == "YOLOv8n" else "ssdlite"
        out = HERE / f"map_precision_recall_{dataset}_{slug}_2026-08-06.png"
        fig.savefig(out, dpi=180); plt.close(fig); created.append(out)

index = {(r["dataset"], r["arm"], r["detector"]): r for r in rows}
pairs = [("pascal_split_100", "default_isp", "normal", "Day: default_isp - normal"),
         ("pascal_split_100", "default_isp_noawb", "normal", "Day: noawb - normal"),
         ("split_nod", "lowlight_isp", "lowlight", "Night: lowlight_isp - lowlight"),
         ("split_nod", "lowlight_isp_subsample", "lowlight", "Night: subsample - lowlight")]
fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharey=False)
for ax, (ds, v2, v1, title) in zip(axes.flat, pairs):
    x = np.arange(4); width = .34
    for j, detector in enumerate(detectors):
        delta = [index[(ds,v2,detector)][m] - index[(ds,v1,detector)][m] for m in METRICS]
        ax.bar(x + (j-.5)*width, delta, width, label=detector)
    ax.axhline(0, color="black", linewidth=.8); ax.set_xticks(x, LABELS, rotation=20, ha="right")
    ax.set_title(title); ax.set_ylabel("v2 - v1 delta"); ax.grid(axis="y", alpha=.25)
axes[0,0].legend(fontsize=8)
fig.suptitle("Cross-detector agreement on v2 versus v1")
fig.tight_layout()
contrast = HERE / "v2_v1_cross_detector_contrast_2026-08-06.png"
fig.savefig(contrast, dpi=180); plt.close(fig); created.append(contrast)

def table(dataset):
    lines = ["| Arm | Detector | mAP@[.5:.95] | mAP@50 | Precision | Recall |",
             "|---|---|---:|---:|---:|---:|"]
    for r in rows:
        if r["dataset"] == dataset:
            lines.append(f"| {r['arm']} | {r['detector']} | {r['mAP_50_95']:.6f} | {r['mAP_50']:.6f} | {r['precision']:.6f} | {r['recall']:.6f} |")
    return "\n".join(lines)

def deltas(ds, v2, v1):
    text=[]
    for d in detectors:
        a=index[(ds,v2,d)]; b=index[(ds,v1,d)]
        text.append(f"{d}: " + ", ".join(f"{lab} {a[m]-b[m]:+.6f}" for m,lab in zip(METRICS,LABELS)))
    return "; ".join(text)

report = f"""# mAP, precision, and recall cross-detector ISP re-simulation (2026-08-06)

## Scope and method

This CPU-only run evaluated 100 images per arm with `blc_offset=2`: daylight `normal`, `default_isp`, and `default_isp_noawb`; night `normal`, `lowlight`, `lowlight_isp`, and the already-supported `lowlight_isp_subsample`. Each arm was evaluated with YOLOv8n and SSDLite MobileNetV3 Large: 14 arm-detector combinations and 1,400 image inferences. No requested minimum arm was skipped. The supported `lowlight_isp_nodenoise` variant was not present in the supplied renderer, so the cheap existing subsample variant was used instead.

mAP@[.5:.95] and mAP@50 are exactly `COCOeval.stats[0]` and `stats[1]`. Precision/recall are independent scalar operating-point metrics: within each image, predictions are sorted by confidence and greedily matched to unmatched same-category ground truths at IoU >= 0.50; TP/FP/FN are aggregated over the full dataset. They are not COCOeval PR-curve summaries.

The unchanged standard inference thresholds were YOLOv8n `0.25` (Ultralytics predict default) and SSDLite `0.001` (the instantiated torchvision model's `score_thresh`). This threshold difference is essential when comparing scalar precision/recall across detectors.

## Daylight - pascal_split_100

{table('pascal_split_100')}

## Night - split_nod

{table('split_nod')}

## v2 versus v1 findings

- Condition-matched primary comparisons agree across detectors. Daylight `default_isp` beats v1 `normal` on both mAP measures and recall for both detectors: {deltas('pascal_split_100','default_isp','normal')}.
- Night `lowlight_isp` beats v1 `lowlight` on both mAP measures, precision, and recall for both detectors: {deltas('split_nod','lowlight_isp','lowlight')}.
- The prior YOLO-only daylight conclusion was mixed; under the required default-inference operating point and direct COCOeval used here, it is no longer mixed for the primary `default_isp` arm. Both detectors show positive mAP deltas. However, `default_isp_noawb` does not share that result: {deltas('pascal_split_100','default_isp_noawb','normal')}. Thus the daylight conclusion still depends on the v2 arm configuration, specifically AWB.
- The night subsample ablation is not a win: {deltas('split_nod','lowlight_isp_subsample','lowlight')}. Both detectors prefer deployed `lowlight_isp` over this variant.

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
"""
(HERE / "mAP-precision-recall-2026-08-06.md").write_text(report)
print("\n".join(str(p) for p in created))
