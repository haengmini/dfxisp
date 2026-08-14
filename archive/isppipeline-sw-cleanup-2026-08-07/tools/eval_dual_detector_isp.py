#!/usr/bin/env python3
"""Render ISP arms once and evaluate YOLOv8n plus SSDLite on CPU.

COCO mAP is taken verbatim from COCOeval.stats[0:2]. Precision and recall are
an independent dataset-level operating-point calculation: per image, process
predictions by descending score and greedily match an unmatched same-category
GT at IoU >= 0.50, then aggregate TP/FP/FN over all images.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from eval_map_isp import build_arm_images
from eval_map_isp_ssd import COCO80_TO_COCO91, build_gt_for_arm

YOLO_CONF = 0.25  # Ultralytics predict-mode default


def iou_xywh(a, b):
    ax1, ay1, aw, ah = a; bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah; bx2, by2 = bx1 + bw, by1 + bh
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def classic_pr(gt_dict, detections):
    gt_by_image = {im["id"]: [] for im in gt_dict["images"]}
    for ann in gt_dict["annotations"]:
        gt_by_image[ann["image_id"]].append(ann)
    pred_by_image = {im["id"]: [] for im in gt_dict["images"]}
    for det in detections:
        pred_by_image.setdefault(det["image_id"], []).append(det)
    tp = fp = fn = 0
    for image_id, gts in gt_by_image.items():
        matched = set()
        for pred in sorted(pred_by_image.get(image_id, []), key=lambda x: x["score"], reverse=True):
            best_iou, best_idx = 0.0, None
            for idx, gt in enumerate(gts):
                if idx in matched or gt["category_id"] != pred["category_id"]:
                    continue
                ov = iou_xywh(pred["bbox"], gt["bbox"])
                if ov > best_iou:
                    best_iou, best_idx = ov, idx
            if best_idx is not None and best_iou >= 0.5:
                matched.add(best_idx); tp += 1
            else:
                fp += 1
        fn += len(gts) - len(matched)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, tp, fp, fn


def coco_map(gt_dict, detections):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    coco_gt = COCO(); coco_gt.dataset = gt_dict; coco_gt.createIndex()
    if not detections:
        return 0.0, 0.0
    coco_dt = coco_gt.loadRes(detections)
    ev = COCOeval(coco_gt, coco_dt, "bbox")
    ev.params.imgIds = [x["id"] for x in gt_dict["images"]]
    ev.params.catIds = [x["id"] for x in gt_dict["categories"]]
    ev.evaluate(); ev.accumulate(); ev.summarize()
    return float(ev.stats[0]), float(ev.stats[1])


def score_yolo(model, arm_dir):
    gt, sid, _ = build_gt_for_arm(arm_dir)
    dets = []
    for stem, image_id in sid.items():
        # One path per call prevents Ultralytics from retaining decoded 20 MP
        # source images across the full dataset on memory-constrained hosts.
        result = model.predict(str(arm_dir / "images" / f"{stem}.jpg"), imgsz=640,
                               conf=YOLO_CONF, device="cpu", verbose=False)[0]
        for xyxy, cls, score in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.cls.cpu().tolist(), result.boxes.conf.cpu().tolist()):
            x1, y1, x2, y2 = xyxy; c80 = int(cls)
            dets.append({"image_id": image_id, "category_id": COCO80_TO_COCO91[c80],
                         "bbox": [x1, y1, x2-x1, y2-y1], "score": float(score)})
    m1, m50 = coco_map(gt, dets); p, r, tp, fp, fn = classic_pr(gt, dets)
    return m1, m50, p, r, len(sid), len(dets), tp, fp, fn


def score_ssd(model, preprocess, arm_dir):
    import torch
    gt, sid, _ = build_gt_for_arm(arm_dir)
    dets = []
    with torch.inference_mode():
        for stem, image_id in sid.items():
            image = Image.open(arm_dir / "images" / f"{stem}.jpg").convert("RGB")
            out = model([preprocess(image).to("cpu")])[0]
            for xyxy, label, score in zip(out["boxes"].tolist(), out["labels"].tolist(), out["scores"].tolist()):
                x1, y1, x2, y2 = xyxy
                dets.append({"image_id": image_id, "category_id": int(label),
                             "bbox": [x1, y1, x2-x1, y2-y1], "score": float(score)})
    m1, m50 = coco_map(gt, dets); p, r, tp, fp, fn = classic_pr(gt, dets)
    return m1, m50, p, r, len(sid), len(dets), tp, fp, fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, default=Path("tools/_dual_detector_rendered"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--yolo-weights", type=Path, required=True)
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()
    configs = [
        ("pascal_split_100", Path("data/pascal_split_100"), ["normal", "default_isp", "default_isp_noawb"]),
        ("split_nod", Path("data/split_nod"), ["normal", "lowlight", "lowlight_isp", "lowlight_isp_subsample"]),
    ]
    started = time.monotonic(); rows = []; audit = []
    for tag, root, arms in configs:
        if args.skip_render:
            counts = [len(list((args.work / tag / arm / "images").glob("*.jpg"))) for arm in arms]
            if counts != [100] * len(arms):
                raise SystemExit(f"incomplete render cache for {tag}: {dict(zip(arms, counts))}")
            print(f"REUSE {tag}: 100 images x {len(arms)} arms", flush=True)
        else:
            n = build_arm_images(root, args.work / tag, arms, 0, 2, jobs=args.jobs)
            print(f"RENDER {tag}: {n} images x {len(arms)} arms", flush=True)

    from ultralytics import YOLO
    yolo = YOLO(str(args.yolo_weights))
    for tag, _, arms in configs:
        for arm in arms:
            t0 = time.monotonic(); vals = score_yolo(yolo, args.work / tag / arm)
            m1, m50, p, r, n, nd, tp, fp, fn = vals
            rows.append([tag, arm, "YOLOv8n", m1, m50, p, r, YOLO_CONF, n])
            audit.append([tag, arm, "YOLOv8n", nd, tp, fp, fn, time.monotonic()-t0])
            print(f"SCORE {tag}/{arm}/YOLOv8n: {m1:.6f} {m50:.6f} P={p:.6f} R={r:.6f}", flush=True)

    import torch
    from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
    weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    checkpoint = Path.home() / ".cache/torch/hub/checkpoints/ssdlite320_mobilenet_v3_large_coco-a79551df.pth"
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    ssd = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None)
    ssd.load_state_dict(state); ssd.eval().to("cpu")
    ssd_conf = float(ssd.score_thresh)
    for tag, _, arms in configs:
        for arm in arms:
            t0 = time.monotonic(); vals = score_ssd(ssd, weights.transforms(), args.work / tag / arm)
            m1, m50, p, r, n, nd, tp, fp, fn = vals
            rows.append([tag, arm, "SSDLite-MobileNetV3-Large", m1, m50, p, r, ssd_conf, n])
            audit.append([tag, arm, "SSDLite-MobileNetV3-Large", nd, tp, fp, fn, time.monotonic()-t0])
            print(f"SCORE {tag}/{arm}/SSD: {m1:.6f} {m50:.6f} P={p:.6f} R={r:.6f}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dataset","arm","detector","mAP_50_95","mAP_50","precision","recall","conf_threshold","n"])
        for row in rows:
            w.writerow(row[:3] + [f"{x:.8f}" for x in row[3:8]] + [row[8]])
    meta = {"wall_seconds": time.monotonic()-started, "blc_offset": 2,
            "combinations": len(rows), "image_inferences": sum(x[-1] for x in rows),
            "audit_columns": ["dataset","arm","detector","detections","tp","fp","fn","score_seconds"],
            "audit": audit}
    args.out.with_suffix(".run.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"WROTE {args.out} and run metadata; wall={meta['wall_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
