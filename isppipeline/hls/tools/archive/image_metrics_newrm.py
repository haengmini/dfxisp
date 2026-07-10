#!/usr/bin/env python3
"""Stage 2 — image metrics for the reset-architecture arms (no detector needed).

Applies the new pipeline arms (none / normal / lowlight / adaptive) to dataset
pseudo-RAW frames and reports RESEARCH §6.1 image metrics aggregated per
(dataset, arm): output shape, Y mean/std/min/max, saturation %, dark-ratio
before/after, and the gain/gamma-duplication flag (structurally false).

Usage:
  python3 tools/image_metrics_newrm.py --root ../../data/exdark_val --tag ExDark --limit 200
"""
from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

import numpy as np

import newrm_pipeline as P

ARMS = ["none", "normal", "lowlight", "adaptive"]


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


def frame_metrics(rgb):
    Y = P.luminance(rgb)
    sat = float(np.mean(np.any(rgb >= 255, axis=-1)))
    return {
        "Ymean": float(Y.mean()), "Ystd": float(Y.std()),
        "Ymin": int(Y.min()), "Ymax": int(Y.max()),
        "sat": sat, "dark_after": float(np.mean(Y < P.DARK_Y)),
        "h": rgb.shape[0], "w": rgb.shape[1],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default="DATA")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    raw_dir = root / "raw_bin"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin") if (img_dir / f"{p.stem}.jpg").exists())
    if args.limit:
        stems = stems[:args.limit]

    acc = {a: {k: [] for k in ["Ymean", "Ystd", "Ymin", "Ymax", "sat", "dark_after", "h", "w"]}
           for a in ARMS}
    dark_before = []
    n_lowlight_adaptive = 0
    used = 0
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            continue
        bayer = bayer.reshape(h, w)
        dark_before.append(P.dark_ratio(P.demosaic_rggb(bayer, w, h)))
        if P.selected_mode(bayer, w, h) == "lowlight":
            n_lowlight_adaptive += 1
        for a in ARMS:
            m = frame_metrics(P.run_arm(bayer, w, h, a))
            for k in acc[a]:
                acc[a][k].append(m[k])
        used += 1

    out = Path(args.out) if args.out else Path(f"results/image_metrics_{args.tag.lower()}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "arm", "n", "out_shape", "Y_mean", "Y_std", "Y_min", "Y_max",
                     "saturation_pct", "dark_ratio_before", "dark_ratio_after",
                     "gain_gamma_dup"])
        db = float(np.mean(dark_before)) if dark_before else 0.0
        for a in ARMS:
            v = acc[a]
            shape = f"{int(np.mean(v['w']))}x{int(np.mean(v['h']))}" if a != "adaptive" else "mixed"
            wr.writerow([
                args.tag, a, used, shape,
                f"{np.mean(v['Ymean']):.1f}", f"{np.mean(v['Ystd']):.1f}",
                f"{np.mean(v['Ymin']):.1f}", f"{np.mean(v['Ymax']):.1f}",
                f"{100*np.mean(v['sat']):.2f}", f"{db:.3f}",
                f"{np.mean(v['dark_after']):.3f}", "False",
            ])
    print(f"wrote {out}  (dataset={args.tag}, n={used}, input dark_ratio={db:.3f}, "
          f"adaptive->lowlight {n_lowlight_adaptive}/{used})")
    # console summary
    print(f"{'arm':9s} {'shape':>9s} {'Ymean':>6s} {'sat%':>6s} {'dark_after':>10s}")
    for a in ARMS:
        v = acc[a]
        shape = f"{int(np.mean(v['w']))}x{int(np.mean(v['h']))}" if a != "adaptive" else "mixed"
        print(f"{a:9s} {shape:>9s} {np.mean(v['Ymean']):6.1f} "
              f"{100*np.mean(v['sat']):6.2f} {np.mean(v['dark_after']):10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
