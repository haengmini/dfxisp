#!/usr/bin/env python3
"""Stage 3 — pseudo-RAW mAP for the reset-architecture arms (ultralytics).

Pipeline per arm (tools/newrm_pipeline.py):
  raw .bin (RGGB16) -> {none | normal | lowlight | adaptive} -> RGB -> YOLO ->
  mAP vs YOLO labels (ultralytics val).

Condition table (RESEARCH / experiment-stages Stage 3):
  ExDark: A=none  B=normal  C=lowlight   (+adaptive)
  COCO  : D=none  E=normal  F=lowlight   (+adaptive)
Labels for both datasets are already COCO-80 ids -> no remap.

Usage:
  python3 tools/eval_map_newrm.py --root ../../data/exdark_val --tag ExDark \
      --model yolov8n.pt --limit 150 --out results/map_newrm_exdark_yolov8n.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

import newrm_pipeline as P
from model_paths import resolve_yolo_model

ARMS = ["none", "normal", "lowlight", "adaptive"]


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


def build_arm_images(root: Path, work: Path, arms, limit: int) -> int:
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
            out = P.run_arm(bayer, w, h, a)
            Image.fromarray(out).save(work / a / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--work", default="data/_newrm_work")
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--model", default="yolov8n.pt",
                    help="YOLO weight name/path; known names resolve to ../../model/detectors/yolo")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="results/map_newrm.csv")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    n = build_arm_images(root, work, arms, args.limit)
    print(f"[{args.tag}] built arm images for {n} frames: {arms}")

    from ultralytics import YOLO
    import yaml  # type: ignore
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)
    res = {}
    for a in arms:
        ds = work / a
        yml = ds / "data.yaml"
        yml.write_text(yaml.safe_dump({
            "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
            "names": [str(i) for i in range(80)],
        }))
        m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False, plots=False)
        res[a] = (float(m.box.map), float(m.box.map50))
        print(f"[{args.tag}] {a:9s} mAP@[.5:.95]={res[a][0]:.4f}  mAP@50={res[a][1]:.4f}")

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for a in arms:
            wr.writerow([args.tag, a, f"{res[a][0]:.4f}", f"{res[a][1]:.4f}", model_path, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
