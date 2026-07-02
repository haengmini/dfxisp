#!/usr/bin/env python3
"""Stage 3 cross-check — SSD+MobileNet detector on the reset-architecture arms.

Re-scores the arm images already built by eval_map_newrm.py (data/_newrm_work/
<tag>/<arm>/images + COCO80 labels) with a structurally different detector family
to confirm the mAP-guardrail *ordering* is detector-independent.

Detector: torchvision ssdlite320_mobilenet_v3_large (COCO-pretrained).
Weights are resolved through the repo-local `model/` folder via `model_paths.py`.
The TensorFlow SSD-MobileNetV1 COCO graph is also staged under `model/detectors/`
for TF1/Vitis-AI/DPU-oriented evaluation, while this script remains the
TorchVision SSD-MobileNetV3 software cross-check path.

Per arm the image size differs (lowlight/adaptive are H/2 x W/2), so GT is built
per arm from that arm's own image dimensions (labels are normalized YOLO).

Usage:
  python3 tools/eval_map_newrm_ssd.py --work data/_newrm_work/exdark --tag ExDark \
      --out results/map_newrm_exdark_ssd.csv
"""
from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

from model_paths import configure_torch_model_cache

ARMS = ["none", "normal", "lowlight", "adaptive"]

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
    """COCO GT from this arm's own images (dims differ per arm) + normalized labels."""
    img_dir = arm_dir / "images"; lab_dir = arm_dir / "labels"
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
    gt = {"images": images, "annotations": anns,
          "categories": [{"id": c, "name": str(c)} for c in sorted(cats)]}
    return gt, sid, sorted(cats)


def run(work: Path, tag: str, out_csv: Path, device: str, arms):
    configure_torch_model_cache()
    import torch
    from PIL import Image
    from torchvision.models.detection import (
        ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights)
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    dev = torch.device(device if (device != "cuda" or torch.cuda.is_available()) else "cpu")
    print(f"[ssd] device={dev}")
    weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model = ssdlite320_mobilenet_v3_large(weights=weights).eval().to(dev)
    preprocess = weights.transforms()

    res = {}
    for arm in arms:
        arm_dir = work / arm
        if not (arm_dir / "images").exists():
            print(f"[ssd] {arm}: missing {arm_dir}/images — run eval_map_newrm.py first")
            res[arm] = (float("nan"), float("nan")); continue
        gt_dict, sid, cat_ids = build_gt_for_arm(arm_dir)
        coco_gt = COCO(); coco_gt.dataset = gt_dict; coco_gt.createIndex()
        dets = []
        with torch.no_grad():
            for stem, img_id in sid.items():
                img = Image.open(arm_dir / "images" / f"{stem}.jpg").convert("RGB")
                out = model([preprocess(img).to(dev)])[0]
                for (x1, y1, x2, y2), lab, sc in zip(
                        out["boxes"].cpu().tolist(), out["labels"].cpu().tolist(),
                        out["scores"].cpu().tolist()):
                    dets.append({"image_id": img_id, "category_id": int(lab),
                                 "bbox": [x1, y1, x2 - x1, y2 - y1], "score": float(sc)})
        if not dets:
            res[arm] = (float("nan"), float("nan")); print(f"[{tag}] {arm}: no detections"); continue
        coco_dt = coco_gt.loadRes(dets)
        ev = COCOeval(coco_gt, coco_dt, "bbox")
        ev.params.catIds = cat_ids; ev.params.imgIds = list(sid.values())
        ev.evaluate(); ev.accumulate(); ev.summarize()
        res[arm] = (float(ev.stats[0]), float(ev.stats[1]))  # mAP@[.5:.95], mAP@50
        print(f"[{tag}] {arm:9s} mAP@[.5:.95]={res[arm][0]:.4f}  mAP@50={res[arm][1]:.4f}  "
              f"(n={len(sid)})")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "arm", "mAP_50_95", "mAP_50", "model"])
        for arm in arms:
            wr.writerow([tag, arm, f"{res[arm][0]:.4f}", f"{res[arm][1]:.4f}",
                         "ssdlite320_mobilenet_v3_large"])
    print(f"wrote {out_csv}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True, help="data/_newrm_work/<tag> (per-arm subdirs)")
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--out", default="results/map_newrm_ssd.csv")
    ap.add_argument("--device", default="cpu", help="cuda|cpu")
    ap.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    run(Path(args.work), args.tag, Path(args.out), args.device, arms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
