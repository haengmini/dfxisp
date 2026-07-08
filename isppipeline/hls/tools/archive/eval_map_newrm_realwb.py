#!/usr/bin/env python3
"""AWB domain-gap ablation: SonyNOD real-RAW mAP with per-image real camera
AWB instead of the pipeline's fixed pseudo-RAW-tuned AWB gains.

Companion to eval_map_newrm.py / newrm_pipeline_realwb.py. Requires a
per-stem camera AWB table (JSON: {stem: [R_mul, G_mul, B_mul, G2_mul]} from
rawpy `camera_whitebalance`, e.g. produced while decoding the source .ARW
files -- see results/realraw-sonynod-benchmark-2026-07-06.md).

"none" is intentionally excluded: it bypasses baseline_core/AWB entirely and
is out of scope for this ablation (and for arm comparisons in general, per
user direction -- it belongs to a different research question).

Usage:
  python3 tools/eval_map_newrm_realwb.py --root ../../../data/sonynod_test \
      --wb-table camera_wb.json --tag SonyNOD-RealWB --model yolov8n.pt \
      --out ../results/map_newrm_sonynod_realwb_yolov8n.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

import newrm_pipeline_realwb as PW
from model_paths import resolve_yolo_model

ARMS = ["normal", "lowlight", "adaptive"]


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


def q8_awb(wb: list[float]) -> tuple[int, int]:
    """[R_mul, G_mul, B_mul, G2_mul] -> Q8 (awb_r, awb_b) with G fixed at 256."""
    r_mul, g_mul, b_mul = wb[0], wb[1], wb[2]
    return round(256 * r_mul / g_mul), round(256 * b_mul / g_mul)


def build_arm_images(root: Path, work: Path, arms, limit: int, wb_table: dict) -> int:
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists()
                   and p.stem in wb_table)
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
        awb_r, awb_b = q8_awb(wb_table[stem])
        for a in arms:
            out = PW.run_arm_realwb(bayer, w, h, a, awb_r, awb_b)
            Image.fromarray(out).save(work / a / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--wb-table", required=True, help="JSON: {stem: [R_mul,G_mul,B_mul,G2_mul]}")
    ap.add_argument("--work", default="data/_newrm_work")
    ap.add_argument("--tag", default="DATA-RealWB")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="results/map_newrm_realwb.csv")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    wb_table = json.loads(Path(args.wb_table).read_text())
    n = build_arm_images(root, work, arms, args.limit, wb_table)
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
