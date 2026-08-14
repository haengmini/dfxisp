#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/AWB/awb_figure_data.py
# Date   : 2026-08-13
# Function: Measure everything the AWB figures need, straight from the RAW
#           files that are actually on disk now (dataset/{LOD,PASCAL}_test/raw),
#           in one pass. Extends awb_channel_diagnostic.py's measurement to
#           (a) both datasets, (b) full post-BLC histograms, (c) clipping /
#           saturation fractions, (d) per-frame as-shot camera WB.
# Why not reuse awb_channel_diagnostic.py as-is: it reads a materialised
#           raw_bin/ root (dataset/LOD_test_eval), which no longer exists and
#           is not to be recreated -- derived sets stay out of dataset/ during
#           the SW experiments. The post-BLC domain definition itself IS reused
#           (imported, not copied), so this stays consistent with AWB_report.md.
# Contract: the shift8 convention is reproduced in memory exactly as
#           build_lod_test_eval_root.arw_to_raw_bin wrote it --
#           round(clip((bayer-black)/(white-black),0,1)*255) << 8 -- then >>4,
#           so the 12-bit values seen here are bit-identical to what
#           awb_channel_diagnostic.py read off LOD_test_eval/raw_bin.
# Usage:
#   python3 awb_figure_data.py --dataset LOD    [--limit N]
#   python3 awb_figure_data.py --dataset PASCAL [--limit N]
# =============================================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rawpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # isppipeline/sw
sys.path.insert(0, str(Path(__file__).resolve().parent))       # this dir

import gen_lowlight_isp_golden as G                    # noqa: E402
from lowlight_isp_pipeline import _binned_raw          # noqa: E402
from awb_channel_diagnostic import blc_only            # noqa: E402  (same domain)

DATASETS = {
    "LOD":    ("../../../../dataset/LOD_test/raw",    (".ARW", ".arw")),
    "PASCAL": ("../../../../dataset/PASCAL_test/raw", (".nef", ".NEF")),
}
NBINS = G.RAW12_MAX + 1


def read_raw12(path: Path) -> tuple[np.ndarray, list[float], dict]:
    """RAW file -> (raw12 mosaic, as-shot WB [R,G,B]/G, meta).

    Reproduces build_lod_test_eval_root.arw_to_raw_bin's shift8 quantisation
    then >>4, so downstream numbers stay comparable with AWB_report.md."""
    with rawpy.imread(str(path)) as raw:
        bayer = raw.raw_image_visible.astype(np.float64)
        s = raw.sizes
        if s.crop_width and s.crop_height:             # Sony ARW: 12,12 margins
            bayer = bayer[s.crop_top_margin:s.crop_top_margin + s.crop_height,
                          s.crop_left_margin:s.crop_left_margin + s.crop_width]
        h, w = bayer.shape
        bayer = bayer[:h - h % 2, :w - w % 2]          # keep the 2x2 CFA phase
        black = float(np.median(raw.black_level_per_channel))
        white = float(np.ravel(raw.white_level)[0])
        cam = [float(v) for v in raw.camera_whitebalance]
    lin = np.clip((bayer - black) / (white - black), 0.0, 1.0)
    raw12 = (np.round(lin * 255).astype(np.int64)) << 4        # shift8 >> 4
    wb = [cam[0] / cam[1], 1.0, cam[2] / cam[1]] if cam[1] else [0.0, 1.0, 0.0]
    return raw12, wb, {"black": black, "white": white, "shape": [w, h]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=sorted(DATASETS), required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent))
    a = ap.parse_args()

    rel, exts = DATASETS[a.dataset]
    raw_dir = (Path(__file__).resolve().parent / rel).resolve()
    files = sorted(p for p in raw_dir.iterdir() if p.suffix in exts)
    if a.limit:
        files = files[:a.limit]
    if not files:
        print(f"ERROR: no raw files under {raw_dir}")
        return 2

    hist = {c: np.zeros(NBINS, dtype=np.int64) for c in "rgb"}
    means, asshot, frames = [], [], []
    for i, p in enumerate(files):
        raw12, wb, meta = read_raw12(p)
        h, w = raw12.shape
        bw, bh = G.bin_dim(w), G.bin_dim(h)
        planes = _binned_raw(raw12, bw, bh, G.BIN_BINNING)
        planes = [blc_only(x) for x in planes]                  # post-BLC, pre-gain
        for c, v in zip("rgb", planes):
            hist[c] += np.bincount(v.ravel(), minlength=NBINS)
        m = [float(v.mean()) for v in planes]
        means.append(m)
        asshot.append(wb)
        frames.append({"stem": p.stem, "mean_rgb": m, "as_shot_wb": wb,
                       "clip0_pct": [float((v == 0).mean() * 100) for v in planes],
                       "sat_pct": [float((v >= G.RAW12_MAX).mean() * 100) for v in planes],
                       **meta})
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(files)}", flush=True)

    arr = np.array(means)
    mr, mg, mb = arr.mean(axis=0)
    gw_r, gw_b = round(256.0 * mg / mr), round(256.0 * mg / mb)
    tot = {c: hist[c].sum() for c in "rgb"}
    out = {
        "dataset": a.dataset, "n_images": len(files), "raw_dir": str(raw_dir),
        "domain": "post-BLC, pre-gain, 2x2 binned (AWB.md 2.1 / AWB_report.md 2)",
        "channel_means_rgb": [mr, mg, mb],
        "ratio_rg": mr / mg, "ratio_bg": mb / mg,
        "gray_world_wb_q8": {"R": gw_r, "G": 256, "B": gw_b},
        "deployed_wb_q8": {"R": G.WB_R_Q8, "G": G.WB_G_Q8, "B": G.WB_B_Q8},
        "deployed_over_grayworld": {"R": G.WB_R_Q8 / gw_r, "B": G.WB_B_Q8 / gw_b},
        "clip0_pct_rgb": [float(hist[c][0] / tot[c] * 100) for c in "rgb"],
        "sat_pct_rgb": [float(hist[c][-1] / tot[c] * 100) for c in "rgb"],
        "as_shot_wb_median_rgb": np.median(np.array(asshot), axis=0).tolist(),
        "frames": frames,
    }
    od = Path(a.out_dir)
    (od / f"awb_stats_{a.dataset.lower()}.json").write_text(json.dumps(out, indent=2))
    np.savez_compressed(od / f"awb_hist_{a.dataset.lower()}.npz",
                        **{c: hist[c] for c in "rgb"})
    print(f"\n{a.dataset}  n={len(files)}")
    print(f"  post-BLC means R={mr:.2f} G={mg:.2f} B={mb:.2f}"
          f"   R/G={mr/mg:.3f}  B/G={mb/mg:.3f}")
    print(f"  gray-world WB (Q8): R={gw_r} B={gw_b}"
          f"   deployed/gray-world: R={G.WB_R_Q8/gw_r:.2f}x B={G.WB_B_Q8/gw_b:.2f}x")
    print(f"  clip@0 %: " + " ".join(f"{c.upper()}={out['clip0_pct_rgb'][i]:.1f}"
                                     for i, c in enumerate("rgb")))
    print(f"  sat %   : " + " ".join(f"{c.upper()}={out['sat_pct_rgb'][i]:.2f}"
                                     for i, c in enumerate("rgb")))
    print(f"  as-shot WB median (R,G,B)/G: "
          f"{[round(v, 3) for v in out['as_shot_wb_median_rgb']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
