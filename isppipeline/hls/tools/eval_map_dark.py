#!/usr/bin/env python3
"""E2 (dark regime) — mAP on the darkest COCO pseudo-RAW frames.

Reuses variant images already built by eval_map_coco.py (data/_variant_work/<variant>/),
selects the darkest K frames by raw mean luminance, and evaluates mAP per variant
on that low-light subset. This isolates the regime the low-light RM targets.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

VARIANTS = ["static", "reg_only", "dfx_bin", "dfx_fp"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", default="data/_variant_work")
    ap.add_argument("--root", default="data/coco_val", help="for raw_bin darkness ranking")
    ap.add_argument("--k", type=int, default=40)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--out", default="results/map_dark.csv")
    args = ap.parse_args()

    work = Path(args.work); root = Path(args.root)
    built = sorted(p.stem for p in (work / "static" / "images").glob("*.jpg"))
    # darkness = mean of raw bin (already 16-bit); lower = darker
    dark = []
    for stem in built:
        b = np.fromfile(root / "raw_bin" / f"{stem}.bin", dtype="<u2")
        dark.append((float(b.mean()), stem))
    dark.sort()
    picked = [s for _, s in dark[:args.k]]
    print(f"selected {len(picked)} darkest frames (mean raw "
          f"{dark[0][0]:.0f}..{dark[min(args.k,len(dark))-1][0]:.0f})")

    from ultralytics import YOLO
    import yaml
    model = YOLO(args.model)
    res = {}
    for name in VARIANTS:
        ds = work / name
        lst = ds / "dark.txt"
        lst.write_text("\n".join(str((ds / "images" / f"{s}.jpg").resolve()) for s in picked) + "\n")
        yml = ds / "data_dark.yaml"
        yml.write_text(yaml.safe_dump({
            "path": str(ds.resolve()), "train": "dark.txt", "val": "dark.txt",
            "nc": 80, "names": [str(i) for i in range(80)],
        }))
        m = model.val(data=str(yml), imgsz=640, verbose=False)
        res[name] = float(m.box.map)
        print(f"{name}: mAP={res[name]:.4f}")

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["metric", "static", "reg_only", "dfx_bin", "dfx_fp", "unit", "notes"])
        wr.writerow(["mAP_COCO_darkK_pseudoRAW"] + [f"{res[n]:.4f}" for n in VARIANTS]
                    + ["mAP@[.5:.95]", f"darkest {len(picked)} frames, {args.model}"])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
