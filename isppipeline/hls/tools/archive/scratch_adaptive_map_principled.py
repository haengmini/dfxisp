#!/usr/bin/env python3
"""scratch_adaptive_map_principled.py -- downstream mAP for checker C0 vs C1.

principled-v3 / Agent CHK. Non-destructive scratch runner (does NOT edit
eval_map_newrm.py / newrm_pipeline.py; imports them). Renders the adaptive arm
under two per-frame checker decisions and evaluates each with yolov8n:

  C0 : dark50 ratio > 0.80  (current HW checker)
  C1 : dark16 ratio > 0.62  (principled Youden-J*, recommended winner)

Both use the SAME normal/lowlight arm renderers (newrm_pipeline.run_arm); only
the per-frame arm SELECTION differs, so the mAP delta isolates the checker.

Checker score uses the raw-domain dark ratio mean((raw>>8) < T8) -- identical to
the statistic evaluated in tools/checker_versions.py and checker_stat_sweep.py.

Usage:
  python3 tools/scratch_adaptive_map_principled.py --root ../../data/exdark_val \
      --tag ExDark --limit 150 --out results/scratch_adaptive_map_principled.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

import newrm_pipeline as P
from eval_map_newrm import jpg_dims
from model_paths import resolve_yolo_model

CHECKERS = {
    "C0_dark50_0p80": ("dark50", 0.80),
    "C1_dark16_0p62": ("dark16", 0.62),
}


def dark_ratio_raw(bayer16: np.ndarray, t8: int) -> float:
    """mean((raw>>8) < t8) -- dataset-domain dark-pixel ratio (matches
    checker_versions.py dark{T8} column)."""
    return float(np.mean((bayer16 >> P.SHIFT) < t8))


def build(root: Path, work: Path, limit: int):
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists()
                   and (lab_dir / f"{p.stem}.txt").exists())
    if limit:
        stems = stems[:limit]
    for c in CHECKERS:
        (work / c / "images").mkdir(parents=True, exist_ok=True)
        (work / c / "labels").mkdir(parents=True, exist_ok=True)
    counts = {c: 0 for c in CHECKERS}   # frames routed to LOW_LIGHT
    built = 0
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            w, h = w - w % 2, h - h % 2
            if bayer.size != w * h:
                continue
        bayer = bayer.reshape(h, w)
        for c, (stat, thr) in CHECKERS.items():
            t8 = 50 if stat == "dark50" else 16
            low = dark_ratio_raw(bayer, t8) > thr
            arm = "lowlight" if low else "normal"
            counts[c] += int(low)
            out = P.run_arm(bayer, w, h, arm)
            Image.fromarray(out).save(work / c / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / c / "labels" / f"{stem}.txt")
        built += 1
    return built, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--work", default="data/_adaptive_principled_work")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--out", default="results/scratch_adaptive_map_principled.csv")
    args = ap.parse_args()

    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    n, counts = build(root, work, args.limit)
    print(f"[{args.tag}] built {n} frames; LOW_LIGHT routing: "
          + ", ".join(f"{c}={counts[c]}/{n}" for c in CHECKERS))

    from ultralytics import YOLO
    import yaml  # type: ignore
    model = YOLO(resolve_yolo_model(args.model))
    rows = []
    for c in CHECKERS:
        ds = work / c
        yml = ds / "data.yaml"
        yml.write_text(yaml.safe_dump({
            "path": str(ds.resolve()), "train": "images", "val": "images",
            "nc": 80, "names": [str(i) for i in range(80)]}))
        m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False,
                      plots=False)
        map5095, map50 = float(m.box.map), float(m.box.map50)
        print(f"[{args.tag}] {c:16s} mAP@[.5:.95]={map5095:.4f} mAP@50={map50:.4f} "
              f"(LOW_LIGHT {counts[c]}/{n})")
        rows.append([args.tag, c, f"{map5095:.4f}", f"{map50:.4f}",
                     counts[c], n])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out.exists()
    with out.open("a", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        if write_header:
            wr.writerow(["dataset", "checker", "mAP_50_95", "mAP_50",
                         "n_lowlight", "n"])
        wr.writerows(rows)
    print(f"appended {len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
