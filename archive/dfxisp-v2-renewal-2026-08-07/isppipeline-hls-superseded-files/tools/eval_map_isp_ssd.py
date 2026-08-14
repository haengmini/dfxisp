#!/usr/bin/env python3
"""SSDLite-MobileNetV3 cross-model check for the eval_map_isp.py BLC/arm sweep
(cross-model validation stage 2 -- ROADMAP.md "즉시 다음" #2, following the
YOLOv8s stage 1 in results/HANDOFF-cross-model-yolov8s-2026-08-03.md).

Reuses eval_map_isp.py's own build_arm_images()/load_adaptive_verdicts() so the
rendered images (BLC offset, arm choice, adaptive-tau verdict) are byte-identical
to the YOLOv8n/YOLOv8s runs -- only the detector differs. Scoring follows
eval_map_ssd.py / eval_map_newrm_ssd.py: torchvision SSDLite is not an
Ultralytics checkpoint, so it can't go through eval_map_isp.py's
YOLO(...).val() path -- instead a COCO GT dict is built from the same
YOLO-format labels eval_map_isp.py copies per arm (COCO80 index remapped to
the COCO91 id space torchvision detection models emit) and scored with
pycocotools COCOeval. Output CSV schema matches eval_map_isp.py's
(dataset,blc_offset,arm,mAP_50_95,mAP_50,model,n) so rows from both scripts
can be diffed/merged directly.

Usage:
  python3 eval_map_isp_ssd.py \
      --root ../../../data/pascal_split --manifest ../results/pascal_split_2026-07-15.csv \
      --blc-offsets 16,1,2 --tag PASCAL-split-ssdlite-2026-08-03 \
      --out ../results/map_isp_pascal_split_ssdlite_2026-08-03.csv
"""
from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

from eval_map_isp import ARMS, build_arm_images, load_adaptive_verdicts
from model_paths import configure_torch_model_cache

# Same 80(YOLO GT index)->91(torchvision detection id space, has gaps) remap
# used by eval_map_ssd.py / eval_map_newrm_ssd.py.
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


def build_gt_for_arm(arm_dir: Path):
    """COCO GT dict from this arm's own images (lowlight/adaptive-into-lowlight
    frames are H/2 x W/2, unlike normal) and its normalized YOLO-format labels."""
    img_dir = arm_dir / "images"; lab_dir = arm_dir / "labels"
    stems = sorted(p.stem for p in img_dir.glob("*.jpg") if (lab_dir / f"{p.stem}.txt").exists())
    images, anns, cats = [], [], set()
    sid = {stem: i + 1 for i, stem in enumerate(stems)}
    aid = 1
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        images.append({"id": sid[stem], "file_name": f"{stem}.jpg", "width": w, "height": h})
        for ln in (lab_dir / f"{stem}.txt").read_text().splitlines():
            parts = ln.split()
            if len(parts) != 5:
                continue
            c80 = int(parts[0])
            cid = COCO80_TO_COCO91[c80] if 0 <= c80 < len(COCO80_TO_COCO91) else None
            if cid is None:
                continue
            cx, cy, bw, bh = (float(v) for v in parts[1:])
            x = (cx - bw / 2) * w; y = (cy - bh / 2) * h
            ww = bw * w; hh = bh * h
            anns.append({"id": aid, "image_id": sid[stem], "category_id": cid,
                         "bbox": [x, y, ww, hh], "area": ww * hh, "iscrowd": 0})
            cats.add(cid); aid += 1
    gt = {"images": images, "annotations": anns,
          "categories": [{"id": c, "name": str(c)} for c in sorted(cats)]}
    return gt, sid, sorted(cats)


def score_arm(model, preprocess, dev, arm_dir: Path):
    import torch
    from PIL import Image
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    gt_dict, sid, cat_ids = build_gt_for_arm(arm_dir)
    if not sid:
        return float("nan"), float("nan"), 0
    coco_gt = COCO(); coco_gt.dataset = gt_dict; coco_gt.createIndex()
    dets = []
    img_dir = arm_dir / "images"
    with torch.no_grad():
        for stem, img_id in sid.items():
            img = Image.open(img_dir / f"{stem}.jpg").convert("RGB")
            out = model([preprocess(img).to(dev)])[0]
            for (x1, y1, x2, y2), lab, sc in zip(
                    out["boxes"].cpu().tolist(), out["labels"].cpu().tolist(),
                    out["scores"].cpu().tolist()):
                dets.append({"image_id": img_id, "category_id": int(lab),
                             "bbox": [x1, y1, x2 - x1, y2 - y1], "score": float(sc)})
    if not dets:
        return float("nan"), float("nan"), len(sid)
    coco_dt = coco_gt.loadRes(dets)
    ev = COCOeval(coco_gt, coco_dt, "bbox")
    ev.params.catIds = cat_ids; ev.params.imgIds = list(sid.values())
    ev.evaluate(); ev.accumulate(); ev.summarize()
    return float(ev.stats[0]), float(ev.stats[1]), len(sid)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="../../../sonynod_test")
    ap.add_argument("--blc-offsets", default="0,1,2,4,8,16", help="comma-separated BLC_OFFSET sweep values")
    ap.add_argument("--work", default="data/_isp_work")
    ap.add_argument("--tag", default="SonyNOD-ISPFix-SSDLite")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="results/map_isp_ssdlite.csv")
    ap.add_argument("--manifest", type=Path, default=None,
                     help="same build_matched_splits.py manifest eval_map_isp.py takes -- "
                          "required for LOD/PASCAL/Shuffle split runs so the 'adaptive' arm "
                          "uses the adopted adaptive-tau verdicts instead of silently falling "
                          "back to the deployed checker (see eval_map_isp.py's own warning).")
    ap.add_argument("--device", default="cuda", help="cuda|cpu")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    blc_offsets = [int(v.strip()) for v in args.blc_offsets.split(",") if v.strip() != ""]
    root = Path(args.root)
    adaptive_verdicts = load_adaptive_verdicts(args.manifest) if args.manifest else None

    configure_torch_model_cache()
    import torch
    from torchvision.models.detection import (
        ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights)

    dev = torch.device(args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu")
    print(f"[ssd] device={dev}")
    weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model = ssdlite320_mobilenet_v3_large(weights=weights).eval().to(dev)
    preprocess = weights.transforms()
    model_name = "ssdlite320_mobilenet_v3_large"

    rows = []
    for blc in blc_offsets:
        work = Path(args.work) / f"{args.tag.lower()}_blc{blc}"
        n = build_arm_images(root, work, arms, args.limit, blc, adaptive_verdicts=adaptive_verdicts)
        print(f"[{args.tag}] blc_offset={blc}: built arm images for {n} frames: {arms}")
        for a in arms:
            map5095, map50, an = score_arm(model, preprocess, dev, work / a)
            print(f"[{args.tag}] blc_offset={blc:2d} {a:9s} mAP@[.5:.95]={map5095:.4f}  mAP@50={map50:.4f}")
            rows.append((args.tag, blc, a, map5095, map50, model_name, an))

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "blc_offset", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for tag, blc, a, m5095, m50, mname, n in rows:
            wr.writerow([tag, blc, a, f"{m5095:.4f}", f"{m50:.4f}", mname, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
