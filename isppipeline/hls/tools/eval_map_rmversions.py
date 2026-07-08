#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/eval_map_rmversions.py
# Date   : 2026-07-05 KST
# Branch : exp/principled-checker-rm-2026-07-05
# Campaign version: principled-v3
# Function: mAP + object-size-AP (S/M/L) evaluator for the principled low-light
#           RM versions (tools/rm_versions.py). Uses pycocotools COCOeval so
#           overall mAP@[.5:.95], mAP@.5 AND AP-by-size come from ONE standard
#           COCO evaluation pass (the size decomposition is a named contribution,
#           survey B.2.2: binning resolution cost vs SNR gain).
#
# FAIR SIZE BUCKETING: all arms are scored in a COMMON full-resolution
# coordinate frame. Binned arms (R0,R2) render at H/2 x W/2; their detections
# are normalized by the rendered dims then rescaled to the ORIGINAL full-res
# pixel grid, and GT areas are full-res areas. So an object's size bucket is
# identical across arms -> the S/M/L split isolates the *detection* effect of
# binning, not a coordinate artifact.
#
# Usage:
#   python3 tools/eval_map_rmversions.py --root ../../data/exdark_val --tag ExDark \
#       --model yolov8n.pt --limit 150 --out results/map_rm_exdark_yolov8n_2026-07-05.csv
# =============================================================================
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import rm_versions as RM
from model_paths import resolve_yolo_model

VERSIONS = ["R0", "R1", "R2", "R3"]


def jpg_dims(p: Path):
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


def load_frames(root: Path, limit: int):
    """Return list of (stem, w_full, h_full, bayer[h,w], gt_lines)."""
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists())
    frames = []
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            continue
        gt = (lab_dir / f"{stem}.txt").read_text().strip().splitlines()
        frames.append((stem, w, h, bayer.reshape(h, w), gt))
        if limit and len(frames) >= limit:
            break
    return frames


def build_gt_coco(frames):
    """COCO ground-truth dict in FULL-RES pixel coordinates."""
    images, anns = [], []
    ann_id = 1
    for img_id, (stem, w, h, _bayer, gt) in enumerate(frames):
        images.append({"id": img_id, "width": w, "height": h, "file_name": f"{stem}.jpg"})
        for line in gt:
            parts = line.split()
            if len(parts) < 5:
                continue
            cls = int(float(parts[0])); cx, cy, bw, bh = map(float, parts[1:5])
            x = (cx - bw / 2) * w; y = (cy - bh / 2) * h
            ww = bw * w; hh = bh * h
            anns.append({"id": ann_id, "image_id": img_id, "category_id": cls,
                         "bbox": [x, y, ww, hh], "area": ww * hh, "iscrowd": 0})
            ann_id += 1
    cats = [{"id": i, "name": str(i)} for i in range(80)]
    return {"images": images, "annotations": anns, "categories": cats}


def render_arm(frames, version, work: Path):
    """Render each frame for `version`; return {stem: (img_path, rw, rh)}."""
    out_dir = work / version / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    for stem, w, h, bayer, _gt in frames:
        rgb = RM.run_arm(bayer, w, h, version)
        rh, rw = rgb.shape[:2]
        p = out_dir / f"{stem}.jpg"
        Image.fromarray(rgb).save(p, quality=95)
        meta[stem] = (str(p), rw, rh)
    return meta


def predict_to_coco(model, frames, meta):
    """Run detector on rendered images; return COCO detections rescaled to
    FULL-RES coordinates (normalize by rendered dims, multiply by full dims)."""
    paths = [meta[stem][0] for stem, *_ in frames]
    dets = []
    # stream=True yields results in input order -> map by index (robust; list
    # sources lose real filenames in res.path).
    results = model.predict(source=paths, imgsz=640, conf=0.001, iou=0.7,
                            max_det=300, verbose=False, stream=True)
    for img_id, res in enumerate(results):
        stem, Wf, Hf = frames[img_id][0], frames[img_id][1], frames[img_id][2]
        _p, rw, rh = meta[stem]
        b = res.boxes
        if b is None or len(b) == 0:
            continue
        xyxy = b.xyxy.cpu().numpy(); conf = b.conf.cpu().numpy(); cls = b.cls.cpu().numpy()
        for (x1, y1, x2, y2), sc, c in zip(xyxy, conf, cls):
            # rendered px -> normalized -> full-res px
            fx = x1 / rw * Wf; fy = y1 / rh * Hf
            fw = (x2 - x1) / rw * Wf; fh = (y2 - y1) / rh * Hf
            dets.append({"image_id": img_id, "category_id": int(c),
                         "bbox": [float(fx), float(fy), float(fw), float(fh)],
                         "score": float(sc)})
    return dets


def coco_eval(gt_dict, dets):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    with contextlib.redirect_stdout(io.StringIO()):
        coco_gt = COCO()
        coco_gt.dataset = gt_dict
        coco_gt.createIndex()
        if not dets:
            return dict(map=0.0, map50=0.0, ap_s=-1.0, ap_m=-1.0, ap_l=-1.0)
        coco_dt = coco_gt.loadRes(dets)
        ev = COCOeval(coco_gt, coco_dt, iouType="bbox")
        ev.evaluate(); ev.accumulate(); ev.summarize()
    s = ev.stats
    return dict(map=float(s[0]), map50=float(s[1]),
                ap_s=float(s[3]), ap_m=float(s[4]), ap_l=float(s[5]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--versions", default=",".join(VERSIONS))
    ap.add_argument("--work", default="data/_rmver_work")
    ap.add_argument("--out", default="results/map_rmversions.csv")
    args = ap.parse_args()

    versions = [v.strip() for v in args.versions.split(",") if v.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    frames = load_frames(root, args.limit)
    print(f"[{args.tag}] {len(frames)} frames; versions={versions}", flush=True)
    gt_dict = build_gt_coco(frames)

    from ultralytics import YOLO
    from ultralytics.utils import LOGGER
    import logging
    LOGGER.setLevel(logging.ERROR)
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)

    rows = {}
    for v in versions:
        meta = render_arm(frames, v, work)
        dets = predict_to_coco(model, frames, meta)
        r = coco_eval(gt_dict, dets)
        rows[v] = r
        print(f"[{args.tag}] {RM.VERSION_NAMES.get(v, v):40s} "
              f"mAP={r['map']:.4f} mAP50={r['map50']:.4f} "
              f"AP_S={r['ap_s']:.4f} AP_M={r['ap_m']:.4f} AP_L={r['ap_l']:.4f}", flush=True)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "version", "name", "mAP_50_95", "mAP_50",
                     "AP_small", "AP_medium", "AP_large", "model", "n"])
        for v in versions:
            r = rows[v]
            wr.writerow([args.tag, v, RM.VERSION_NAMES.get(v, v),
                         f"{r['map']:.4f}", f"{r['map50']:.4f}", f"{r['ap_s']:.4f}",
                         f"{r['ap_m']:.4f}", f"{r['ap_l']:.4f}",
                         Path(model_path).name, len(frames)])
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
