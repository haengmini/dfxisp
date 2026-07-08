#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/eval_map_rmversions_ssd.py
# Date   : 2026-07-05 KST
# Branch : exp/principled-checker-rm-2026-07-05
# Campaign version: principled-v3
# Function: INDEPENDENT third-detector cross-check of the principled low-light
#           RM versions (tools/rm_versions.py) using torchvision SSDLite
#           MobileNetV3-Large (COCO-pretrained) -- a structurally different
#           detector family from the YOLOv8n/YOLOv8s validation already done
#           in eval_map_rmversions.py. Tests whether "R1 (full-res VST-LUT)
#           beats R0 (2x2 bin baseline)" generalizes beyond the YOLO family.
#
# SCRATCH FILE: adapts eval_map_rmversions.py's frame loading + RM rendering
# with eval_map_newrm_ssd.py's torchvision SSDLite detector-loading pattern.
# Does NOT edit either canonical file.
#
# COCO80 -> COCO91 id remap because torchvision SSD models emit ids in the
# gapped 91-category COCO space (same remap table as eval_map_newrm_ssd.py /
# eval_map_ssd.py).
#
# Usage:
#   python3 tools/eval_map_rmversions_ssd.py --root ../../data/exdark_val \
#       --tag ExDark --versions R0,R1 --limit 150 \
#       --out results/map_rm_ssd_2026-07-05.csv
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
from model_paths import configure_torch_model_cache

VERSIONS = ["R0", "R1", "R2", "R3"]

COCO80_TO_COCO91 = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21,
    22, 23, 24, 25, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
    46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    67, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 84, 85, 86, 87, 88, 89, 90,
]


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
    """COCO GT dict in FULL-RES pixel coords, category ids remapped to COCO91
    so they align with torchvision SSD's output id space."""
    images, anns, cats = [], [], set()
    ann_id = 1
    for img_id, (stem, w, h, _bayer, gt) in enumerate(frames):
        images.append({"id": img_id, "width": w, "height": h, "file_name": f"{stem}.jpg"})
        for line in gt:
            parts = line.split()
            if len(parts) < 5:
                continue
            c80 = int(float(parts[0]))
            cid = COCO80_TO_COCO91[c80] if 0 <= c80 < len(COCO80_TO_COCO91) else None
            if cid is None:
                continue
            cx, cy, bw, bh = map(float, parts[1:5])
            x = (cx - bw / 2) * w; y = (cy - bh / 2) * h
            ww = bw * w; hh = bh * h
            anns.append({"id": ann_id, "image_id": img_id, "category_id": cid,
                         "bbox": [x, y, ww, hh], "area": ww * hh, "iscrowd": 0})
            cats.add(cid); ann_id += 1
    cat_dict = {"images": images, "annotations": anns,
                "categories": [{"id": c, "name": str(c)} for c in sorted(cats)]}
    return cat_dict, sorted(cats)


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


def predict_to_coco(model, preprocess, dev, frames, meta):
    """Run SSD detector on rendered images; return COCO91 detections
    rescaled to FULL-RES coordinates (rendered px -> normalized -> full px)."""
    import torch
    dets = []
    with torch.no_grad():
        for img_id, (stem, Wf, Hf, _bayer, _gt) in enumerate(frames):
            p, rw, rh = meta[stem]
            img = Image.open(p).convert("RGB")
            out = model([preprocess(img).to(dev)])[0]
            for (x1, y1, x2, y2), lab, sc in zip(
                    out["boxes"].cpu().tolist(), out["labels"].cpu().tolist(),
                    out["scores"].cpu().tolist()):
                fx = x1 / rw * Wf; fy = y1 / rh * Hf
                fw = (x2 - x1) / rw * Wf; fh = (y2 - y1) / rh * Hf
                dets.append({"image_id": img_id, "category_id": int(lab),
                             "bbox": [float(fx), float(fy), float(fw), float(fh)],
                             "score": float(sc)})
    return dets


def coco_eval(gt_dict, cat_ids, img_ids, dets):
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
        ev.params.catIds = cat_ids; ev.params.imgIds = img_ids
        ev.evaluate(); ev.accumulate(); ev.summarize()
    s = ev.stats
    return dict(map=float(s[0]), map50=float(s[1]),
                ap_s=float(s[3]), ap_m=float(s[4]), ap_l=float(s[5]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--versions", default="R0,R1")
    ap.add_argument("--work", default="data/_rmver_ssd_work")
    ap.add_argument("--out", default="results/map_rm_ssd.csv")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    versions = [v.strip() for v in args.versions.split(",") if v.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    frames = load_frames(root, args.limit)
    print(f"[{args.tag}] {len(frames)} frames; versions={versions}", flush=True)
    gt_dict, cat_ids = build_gt_coco(frames)
    img_ids = [img["id"] for img in gt_dict["images"]]

    configure_torch_model_cache()
    import torch
    from torchvision.models.detection import (
        ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights)

    dev = torch.device(args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu")
    print(f"[ssd] device={dev}", flush=True)
    weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model = ssdlite320_mobilenet_v3_large(weights=weights).eval().to(dev)
    preprocess = weights.transforms()

    rows = {}
    for v in versions:
        meta = render_arm(frames, v, work)
        dets = predict_to_coco(model, preprocess, dev, frames, meta)
        r = coco_eval(gt_dict, cat_ids, img_ids, dets)
        rows[v] = r
        print(f"[{args.tag}] {RM.VERSION_NAMES.get(v, v):40s} "
              f"mAP={r['map']:.4f} mAP50={r['map50']:.4f} "
              f"AP_S={r['ap_s']:.4f} AP_M={r['ap_m']:.4f} AP_L={r['ap_l']:.4f}", flush=True)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out.exists()
    with out.open("a", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        if write_header:
            wr.writerow(["dataset", "version", "name", "mAP_50_95", "mAP_50",
                         "AP_small", "AP_medium", "AP_large", "model", "n"])
        for v in versions:
            r = rows[v]
            wr.writerow([args.tag, v, RM.VERSION_NAMES.get(v, v),
                         f"{r['map']:.4f}", f"{r['map50']:.4f}", f"{r['ap_s']:.4f}",
                         f"{r['ap_m']:.4f}", f"{r['ap_l']:.4f}",
                         "ssdlite320_mobilenet_v3_large", len(frames)])
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
