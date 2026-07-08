#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/eval_map_rmversions_fine.py
# Date   : 2026-07-05 KST · Branch exp/principled-checker-rm-2026-07-05 · principled-v3
# Function: mAP + size-AP for the FINE factorial RM versions (rm_versions_fine),
#           reusing the fair-size-bucketing COCOeval harness of
#           eval_map_rmversions.py but with a --bootstrap image-level 95% CI on
#           mAP so the small-n deltas get an honest uncertainty (gap G-STAT-1).
# Usage:
#   python3 tools/eval_map_rmversions_fine.py --root ../../data/coco_val --tag COCO \
#       --versions F_g25,F_g20,F_vst,B_g25,B_g20,B_vst,B_vst_dn,F_vst_knee \
#       --model yolov8n.pt --limit 150 --bootstrap 500 \
#       --out results/map_rmfine_coco_yolov8n_2026-07-05.csv
# =============================================================================
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

import eval_map_rmversions as E   # reuse load_frames/build_gt/render/predict/coco_eval
import rm_versions_fine as RMF
from model_paths import resolve_yolo_model

# Route the harness renderer at the fine module (E.render_arm calls E.RM.run_arm).
E.RM = RMF


def bootstrap_map_ci(gt_dict, dets, frames, n_boot: int, seed: int = 0):
    """Image-level bootstrap 95% CI on overall mAP@[.5:.95]: resample images with
    replacement, rebuild GT+dets subset, re-run COCOeval. Returns (lo, hi, sd)."""
    if n_boot <= 0:
        return (float("nan"), float("nan"), float("nan"))
    ids = [im["id"] for im in gt_dict["images"]]
    by_img_ann = {i: [] for i in ids}
    for a in gt_dict["annotations"]:
        by_img_ann[a["image_id"]].append(a)
    by_img_det = {i: [] for i in ids}
    for d in dets:
        by_img_det[d["image_id"]].append(d)
    imeta = {im["id"]: im for im in gt_dict["images"]}
    cats = gt_dict["categories"]
    rng = np.random.default_rng(seed)
    maps = []
    for _ in range(n_boot):
        pick = rng.choice(ids, size=len(ids), replace=True)
        images, anns, bdets = [], [], []
        aid = 1
        for new_id, old in enumerate(pick):
            im = dict(imeta[old]); im["id"] = new_id
            images.append(im)
            for a in by_img_ann[old]:
                a2 = dict(a); a2["image_id"] = new_id; a2["id"] = aid; aid += 1
                anns.append(a2)
            for d in by_img_det[old]:
                d2 = dict(d); d2["image_id"] = new_id
                bdets.append(d2)
        gt_b = {"images": images, "annotations": anns, "categories": cats}
        maps.append(E.coco_eval(gt_b, bdets)["map"])
    maps = np.asarray(maps)
    return float(np.percentile(maps, 2.5)), float(np.percentile(maps, 97.5)), float(maps.std())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--versions", default=",".join(RMF.FACTORIAL))
    ap.add_argument("--work", default="data/_rmfine_work")
    ap.add_argument("--bootstrap", type=int, default=0)
    ap.add_argument("--out", default="results/map_rmfine.csv")
    args = ap.parse_args()

    versions = [v.strip() for v in args.versions.split(",") if v.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    frames = E.load_frames(root, args.limit)
    print(f"[{args.tag}] {len(frames)} frames; versions={versions}", flush=True)
    gt_dict = E.build_gt_coco(frames)

    from ultralytics import YOLO
    from ultralytics.utils import LOGGER
    import logging
    LOGGER.setLevel(logging.ERROR)
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)

    rows = {}
    for v in versions:
        meta = E.render_arm(frames, v, work)
        dets = E.predict_to_coco(model, frames, meta)
        r = E.coco_eval(gt_dict, dets)
        lo, hi, sd = bootstrap_map_ci(gt_dict, dets, frames, args.bootstrap)
        r.update(ci_lo=lo, ci_hi=hi, ci_sd=sd)
        rows[v] = r
        ci = f" 95%CI[{lo:.4f},{hi:.4f}]" if args.bootstrap else ""
        print(f"[{args.tag}] {RMF.VERSION_NAMES.get(v, v):45s} "
              f"mAP={r['map']:.4f}{ci} mAP50={r['map50']:.4f} "
              f"AP_S={r['ap_s']:.4f} AP_M={r['ap_m']:.4f} AP_L={r['ap_l']:.4f}", flush=True)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "version", "name", "mAP_50_95", "ci_lo", "ci_hi",
                     "ci_sd", "mAP_50", "AP_small", "AP_medium", "AP_large", "model", "n"])
        for v in versions:
            r = rows[v]
            wr.writerow([args.tag, v, RMF.VERSION_NAMES.get(v, v),
                         f"{r['map']:.4f}", f"{r['ci_lo']:.4f}", f"{r['ci_hi']:.4f}",
                         f"{r['ci_sd']:.4f}", f"{r['map50']:.4f}", f"{r['ap_s']:.4f}",
                         f"{r['ap_m']:.4f}", f"{r['ap_l']:.4f}",
                         Path(model_path).name, len(frames)])
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
