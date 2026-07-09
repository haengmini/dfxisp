#!/usr/bin/env python3
"""BLC recalibration ablation: SonyNOD real-RAW mAP swept over BLC_OFFSET,
holding AWB/gain/gamma/demosaic/binning fixed at the pipeline's existing
pseudo-RAW-tuned values.

Companion to eval_map_newrm.py / newrm_pipeline_blcfix.py. See
results/realraw-sonynod-benchmark-2026-07-06.md §6bis for why BLC (not AWB)
is the suspected root cause of the SonyNOD mAP gap.

"none" is intentionally excluded: it bypasses baseline_core/BLC entirely and
is out of scope for this ablation (and for arm comparisons in general, per
user direction).

Usage:
  python3 tools/eval_map_newrm_blcfix.py --root ../../../data/sonynod_test \
      --blc-offsets 0,1,2,4,8,16 --tag SonyNOD-BLCFix --model yolov8n.pt \
      --out ../results/map_newrm_sonynod_blcfix_yolov8n.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import newrm_pipeline_blcfix as PB
from model_paths import resolve_yolo_model

ARMS = ["normal", "lowlight", "adaptive"]


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


def build_arm_images(root: Path, work: Path, arms, limit: int, blc_offset: int) -> int:
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists())
    if limit:
        stems = stems[:limit]
    for a in arms:
        (work / a / "images").mkdir(parents=True, exist_ok=True)
        (work / a / "labels").mkdir(parents=True, exist_ok=True)
    built = 0
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            continue
        bayer = bayer.reshape(h, w)
        for a in arms:
            out = PB.run_arm_blcfix(bayer, w, h, a, blc_offset)
            Image.fromarray(out).save(work / a / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--blc-offsets", default="0,1,2,4,8,16", help="comma-separated BLC_OFFSET sweep values")
    ap.add_argument("--work", default="data/_newrm_work")
    ap.add_argument("--tag", default="DATA-BLCFix")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="results/map_newrm_blcfix.csv")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    blc_offsets = [int(v.strip()) for v in args.blc_offsets.split(",") if v.strip() != ""]
    root = Path(args.root)

    from ultralytics import YOLO
    import yaml  # type: ignore
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)

    rows = []
    n = None
    for blc in blc_offsets:
        work = Path(args.work) / f"{args.tag.lower()}_blc{blc}"
        n = build_arm_images(root, work, arms, args.limit, blc)
        print(f"[{args.tag}] blc_offset={blc}: built arm images for {n} frames: {arms}")
        for a in arms:
            ds = work / a
            yml = ds / "data.yaml"
            yml.write_text(yaml.safe_dump({
                "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
                "names": [str(i) for i in range(80)],
            }))
            m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False, plots=False)
            map5095, map50 = float(m.box.map), float(m.box.map50)
            print(f"[{args.tag}] blc_offset={blc:2d} {a:9s} mAP@[.5:.95]={map5095:.4f}  mAP@50={map50:.4f}")
            rows.append((args.tag, blc, a, map5095, map50, model_path, n))

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "blc_offset", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for tag, blc, a, m5095, m50, model_path, n in rows:
            wr.writerow([tag, blc, a, f"{m5095:.4f}", f"{m50:.4f}", model_path, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
