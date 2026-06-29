#!/usr/bin/env python3
"""B1 — 2nd-detector cross-check of the 4 RM variants with torchvision SSDLite.

Purpose: confirm the mAP-guardrail variant ordering found with ultralytics YOLO
(reg_only >= static >= dfx_bin >> dfx_fp on real low-light ExDark) is *detector-
independent* by re-scoring with a structurally different detector family:
SSD + MobileNet (ssdlite320_mobilenet_v3_large, COCO-pretrained).

It reuses the variant images already built by eval_map_coco.py (per-variant
images/ + YOLO-format labels in COCO80 ids), so the ISP transform is identical to
the YOLO run; only the detector changes. GT labels (COCO80) are mapped to the
COCO91 id space that torchvision detection models emit, and scored with COCOeval.

Usage:
  python3 tools/eval_map_ssd.py --work data/_exdark_bil --tag ExDark \
      --out results/map_exdark_ssd.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

VARIANTS = ["static", "reg_only", "dfx_bin", "dfx_fp"]

# Map the 80-class COCO index (used in the YOLO-format GT labels) to the real
# COCO category id (91-id space with gaps) that torchvision detection models use.
COCO80_TO_COCO91 = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21,
    22, 23, 24, 25, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
    46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    67, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 84, 85, 86, 87, 88, 89, 90,
]


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


def build_gt(work: Path):
    """Build a COCO GT dict from the static variant's labels (identical across
    variants). Returns (gt_dict, stem->image_id, sorted cat ids present)."""
    img_dir = work / "static" / "images"
    lab_dir = work / "static" / "labels"
    stems = sorted(p.stem for p in img_dir.glob("*.jpg") if (lab_dir / f"{p.stem}.txt").exists())
    images, anns, cats = [], [], set()
    sid = {stem: i + 1 for i, stem in enumerate(stems)}
    aid = 1
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        images.append({"id": sid[stem], "file_name": f"{stem}.jpg", "width": w, "height": h})
        for ln in (lab_dir / f"{stem}.txt").read_text().splitlines():
            p = ln.split()
            if len(p) != 5:
                continue
            c80 = int(p[0])
            cid = COCO80_TO_COCO91[c80] if 0 <= c80 < len(COCO80_TO_COCO91) else None
            if cid is None:
                continue
            cx, cy, bw, bh = (float(v) for v in p[1:])
            x = (cx - bw / 2) * w; y = (cy - bh / 2) * h
            ww = bw * w; hh = bh * h
            anns.append({"id": aid, "image_id": sid[stem], "category_id": cid,
                         "bbox": [x, y, ww, hh], "area": ww * hh, "iscrowd": 0})
            cats.add(cid); aid += 1
    gt = {
        "images": images,
        "annotations": anns,
        "categories": [{"id": c, "name": str(c)} for c in sorted(cats)],
    }
    return gt, sid, sorted(cats)


def run(work: Path, tag: str, out_csv: Path, device: str):
    import numpy as np  # noqa: F401  (kept for parity / future use)
    import torch
    from PIL import Image
    from torchvision.models.detection import (
        ssdlite320_mobilenet_v3_large,
        SSDLite320_MobileNet_V3_Large_Weights,
    )
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    dev = torch.device(device if (device != "cuda" or torch.cuda.is_available()) else "cpu")
    print(f"[ssd] device={dev}")
    weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model = ssdlite320_mobilenet_v3_large(weights=weights).eval().to(dev)
    preprocess = weights.transforms()

    gt_dict, sid, cat_ids = build_gt(work)
    n = len(gt_dict["images"])
    print(f"[ssd] {n} images, {len(gt_dict['annotations'])} GT boxes, "
          f"{len(cat_ids)} categories: {cat_ids}")

    # COCO GT object (silence its prints by loading from the in-memory dict)
    coco_gt = COCO()
    coco_gt.dataset = gt_dict
    coco_gt.createIndex()

    res = {}
    for name in VARIANTS:
        img_dir = work / name / "images"
        dets = []
        with torch.no_grad():
            for stem, img_id in sid.items():
                ip = img_dir / f"{stem}.jpg"
                if not ip.exists():
                    continue
                img = Image.open(ip).convert("RGB")
                t = preprocess(img).to(dev)
                out = model([t])[0]
                boxes = out["boxes"].cpu().tolist()
                labels = out["labels"].cpu().tolist()
                scores = out["scores"].cpu().tolist()
                for (x1, y1, x2, y2), lab, sc in zip(boxes, labels, scores):
                    dets.append({"image_id": img_id, "category_id": int(lab),
                                 "bbox": [x1, y1, x2 - x1, y2 - y1], "score": float(sc)})
        if not dets:
            res[name] = float("nan"); print(f"{name}: no detections"); continue
        coco_dt = coco_gt.loadRes(dets)
        ev = COCOeval(coco_gt, coco_dt, "bbox")
        ev.params.catIds = cat_ids          # score only the 12 ExDark-present cats
        ev.params.imgIds = list(sid.values())
        ev.evaluate(); ev.accumulate(); ev.summarize()
        res[name] = float(ev.stats[0])      # mAP@[.5:.95]
        print(f"{name}: mAP={res[name]:.4f}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["metric", "static", "reg_only", "dfx_bin", "dfx_fp", "unit", "notes"])
        wr.writerow([f"mAP_{tag}_pseudoRAW"] + [f"{res[v]:.4f}" for v in VARIANTS]
                    + ["mAP@[.5:.95]", f"model=ssdlite320_mobilenet_v3_large n={n}"])
    print(f"wrote {out_csv}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", default="data/_exdark_bil",
                    help="dir with <variant>/images + <variant>/labels (COCO80 ids)")
    ap.add_argument("--tag", default="ExDark")
    ap.add_argument("--out", default="results/map_exdark_ssd.csv")
    ap.add_argument("--device", default="cuda", help="cuda|cpu")
    args = ap.parse_args()
    run(Path(args.work), args.tag, Path(args.out), args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
