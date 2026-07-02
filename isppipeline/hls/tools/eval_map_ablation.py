# =============================================================================
# File   : isppipeline/hls/tools/eval_map_ablation.py
# Date   : 2026-07-02
# Time   : 23:10 KST
# Function: Stage 3 mAP eval for the low-light RM ablation
#           (tools/isp_pipeline_ablation.py). Same harness pattern as
#           eval_map_ver1.py, extended to run both the ver1 reference arms
#           (none/normal/lowlight) and the 5 ablation arms in one pass so
#           they're directly comparable on the same frames/model/csv.
# Goal   : Root-cause "why doesn't the low-light RM improve mAP" -- isolate
#          resolution loss vs BLC/WB vs exposure gain vs gamma as the guardrail
#          investigation left open in experiment_ver1_2026-07-02.md ("ver2-A").
# =============================================================================
"""Usage:
  python3 tools/eval_map_ablation.py --root ../../data/exdark_val --tag ExDark \
      --model yolov8n.pt --limit 71 --out results/map_ablation_exdark_yolov8n.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import isp_pipeline_ver1 as P
import isp_pipeline_ablation as A

REF_ARMS = ["none", "normal", "lowlight"]
ALL_ARMS = REF_ARMS + A.ARMS


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


def run_arm_any(bayer, w, h, arm):
    if arm in REF_ARMS:
        return P.run_arm(bayer, w, h, arm)
    return A.run_arm(bayer, w, h, arm)


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
            Image.fromarray(run_arm_any(bayer, w, h, a)).save(work / a / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--work", default="data/_ablation_work")
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=71)
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--out", default="results/map_ablation.csv")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    root = Path(args.root); work = Path(args.work) / args.tag.lower()
    n = build_arm_images(root, work, arms, args.limit)
    print(f"[ablation/{args.tag}] built arm images for {n} frames: {arms}")

    from ultralytics import YOLO
    import yaml  # type: ignore
    model = YOLO(args.model)
    res = {}
    for a in arms:
        ds = work / a
        (ds / "data.yaml").write_text(yaml.safe_dump({
            "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
            "names": [str(i) for i in range(80)]}))
        m = model.val(data=str(ds / "data.yaml"), imgsz=640, verbose=False, save_json=False, plots=False)
        res[a] = (float(m.box.map), float(m.box.map50))
        print(f"[ablation/{args.tag}] {a:20s} mAP@[.5:.95]={res[a][0]:.4f}  mAP@50={res[a][1]:.4f}")

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["pipeline", "dataset", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for a in arms:
            wr.writerow(["ablation", args.tag, a, f"{res[a][0]:.4f}", f"{res[a][1]:.4f}", args.model, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
