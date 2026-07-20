#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/checker_oracle_label.py
# Date   : 2026-07-20
# Function: gate 2 (checker-status-2026-07-10.md SS4 item 2 / strengthening
#           #4) -- oracle label redefinition. Renders each frame in the
#           Shuffle_split manifest through BOTH the normal and lowlight arms
#           (deployed BLC=2 for both, per src/dfxisp_accel.cpp), scores each
#           render against its YOLO-format GT with YOLOv8n, and defines a
#           per-frame oracle label from the detection delta instead of the
#           naive per-DATASET label (`gt_lowlight` in the manifest: LOD=True,
#           PASCAL=False for every frame regardless of actual content).
#           |delta_f1| <= EPS is don't-care (ambiguous, arm choice doesn't
#           matter for detection quality on that frame).
# =============================================================================
"""checker_oracle_label: per-frame detection-delta oracle vs checker C1.

Usage:
  python3 checker_oracle_label.py --manifest ../results/shuffle_split_2026-07-15.csv \
      --out ../results/oracle_label_shuffle_2026-07-20.csv [--limit 20]
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np
from PIL import Image

import baseline_isp_pipeline as PB
import low_light_isp_pipeline as PL
from model_paths import resolve_yolo_model

EPS = 0.05  # |delta F1| <= EPS -> don't-care (matches Schmitt-band-style small margin used elsewhere in this repo, e.g. checker-status-2026-07-10.md SS1 Schmitt delta=2%p)
CONF, IOU_NMS, IMGSZ = 0.25, 0.45, 640
MATCH_IOU = 0.5


def jpg_dims(p: Path):
    import struct
    d = p.read_bytes(); i = 2
    while i < len(d):
        if d[i] != 0xFF:
            i += 1; continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3):
            h = struct.unpack(">H", d[i + 5:i + 7])[0]; w = struct.unpack(">H", d[i + 7:i + 9])[0]
            return w, h
        ln = struct.unpack(">H", d[i + 2:i + 4])[0]; i += 2 + ln
    raise ValueError(f"no SOF in {p}")


def load_yolo_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    """cls, cx, cy, w, h, all normalized -- resolution-independent, so the
    same label rows are valid against both the full-res normal render and
    the half-res lowlight render without rescaling."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls, cx, cy, w, h = parts
        out.append((int(cls), float(cx), float(cy), float(w), float(h)))
    return out


def cxcywh_to_xyxy_norm(cx, cy, w, h):
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def iou_xyxy(a, b) -> float:
    ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def score_frame(pred_boxes, pred_cls, pred_conf, gt_rows) -> tuple[int, int, int, float]:
    """Greedy class-aware matching (highest-confidence prediction first).
    Returns (TP, FP, FN, F1). F1=1.0 when TP=FP=FN=0 (no GT, no predictions
    -- both arms trivially agree, correctly folded into a near-zero delta)."""
    gt_xyxy = [cxcywh_to_xyxy_norm(cx, cy, w, h) for _, cx, cy, w, h in gt_rows]
    gt_cls = [c for c, *_ in gt_rows]
    matched_gt = [False] * len(gt_rows)

    order = sorted(range(len(pred_conf)), key=lambda i: -pred_conf[i])
    tp = 0
    fp = 0
    for i in order:
        best_j, best_iou = -1, 0.0
        for j in range(len(gt_rows)):
            if matched_gt[j] or gt_cls[j] != pred_cls[i]:
                continue
            v = iou_xyxy(pred_boxes[i], gt_xyxy[j])
            if v > best_iou:
                best_iou, best_j = v, j
        if best_j >= 0 and best_iou >= MATCH_IOU:
            matched_gt[best_j] = True
            tp += 1
        else:
            fp += 1
    fn = matched_gt.count(False)
    if tp == 0 and fp == 0 and fn == 0:
        return 0, 0, 0, 1.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0
    return tp, fp, fn, f1


def predict_frame(model, img_arr, orig_w, orig_h) -> tuple[list, list, list]:
    """Run YOLOv8n on an in-memory RGB uint8 array, return normalized
    xyxy boxes + coco class ids + confidences (image-space, not full-res
    rescaled -- normalized coords make full-res vs half-res renders
    directly comparable to the same GT label rows)."""
    r = model.predict(img_arr, imgsz=IMGSZ, conf=CONF, iou=IOU_NMS, verbose=False)[0]
    h, w = img_arr.shape[0], img_arr.shape[1]
    boxes, clses, confs = [], [], []
    for b in r.boxes:
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
        boxes.append((x1 / w, y1 / h, x2 / w, y2 / h))
        clses.append(int(b.cls[0].item()))
        confs.append(float(b.conf[0].item()))
    return boxes, clses, confs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--eps", type=float, default=EPS)
    args = ap.parse_args()

    from ultralytics import YOLO
    model = YOLO(resolve_yolo_model(args.model))

    with args.manifest.open() as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[:args.limit]

    out_rows = []
    t_start = time.time()
    for i, r in enumerate(rows):
        data_dir = Path(r["data_dir"])  # e.g. data/sonynod_test/raw_bin
        root = Path("../../..") / data_dir.parent
        stem = r["stem"]
        img_path = root / "images" / f"{stem}.jpg"
        lab_path = root / "labels" / f"{stem}.txt"
        raw_path = root / "raw_bin" / f"{stem}.bin"
        if not (img_path.exists() and lab_path.exists() and raw_path.exists()):
            continue

        w, h = jpg_dims(img_path)
        bayer = np.fromfile(raw_path, dtype="<u2")
        if bayer.size != w * h:
            continue
        bayer = bayer.reshape(h, w)
        gt_rows = load_yolo_labels(lab_path)

        out_n = PB.run_arm(bayer, w, h, "normal")       # blc_offset=None -> deployed BLC=2
        out_l = PL.run_arm(bayer, w, h, "lowlight")      # blc_offset=None -> deployed BLC=2

        pb, pc, pconf = predict_frame(model, out_n, w, h)
        tp_n, fp_n, fn_n, f1_n = score_frame(pb, pc, pconf, gt_rows)

        pb, pc, pconf = predict_frame(model, out_l, w, h)
        tp_l, fp_l, fn_l, f1_l = score_frame(pb, pc, pconf, gt_rows)

        delta = f1_l - f1_n
        if delta > args.eps:
            oracle = "True"
        elif delta < -args.eps:
            oracle = "False"
        else:
            oracle = ""  # don't-care

        out_rows.append({
            "source": r["source"], "stem": stem, "iso": r["iso"],
            "n_gt": len(gt_rows),
            "gt_lowlight_naive": r["gt_lowlight"],
            "c0_verdict_lowlight": r["c0_verdict_lowlight"],
            "c1_verdict_lowlight": r["c1_verdict_lowlight"],
            "adaptive_verdict_lowlight": r["adaptive_verdict_lowlight"],
            "tp_normal": tp_n, "fp_normal": fp_n, "fn_normal": fn_n, "f1_normal": f1_n,
            "tp_lowlight": tp_l, "fp_lowlight": fp_l, "fn_lowlight": fn_l, "f1_lowlight": f1_l,
            "delta_f1": delta, "oracle_lowlight": oracle,
        })
        if (i + 1) % 25 == 0 or (i + 1) == len(rows):
            elapsed = time.time() - t_start
            print(f"[{i+1}/{len(rows)}] elapsed={elapsed:.0f}s avg={elapsed/(i+1):.2f}s/frame", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        wr.writeheader()
        wr.writerows(out_rows)
    print(f"wrote {args.out} ({len(out_rows)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
