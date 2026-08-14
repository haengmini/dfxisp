#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/AWB/awb_channel_diagnostic.py
# Date   : 2026-08-12
# Function: AWB.md §2.1's gray-world channel diagnostic, rewritten from
#           scratch for LOD_test (the original one-off script is lost --
#           AWB.md §2.4/§4 says so explicitly). Measures post-BLC
#           (pedestal-subtracted + range-restored, PRE-gain/WB) per-channel
#           means over dataset/LOD_test_eval/raw_bin/*.bin, derives the
#           gray-world WB (G=256 fixed) those means imply, and compares it
#           to the deployed shared WB (286/256/307).
# Sources: isppipeline/sw/sim/AWB/AWB.md §2.1, isppipeline/sw/gen_lowlight_isp_golden.py,
#          isppipeline/sw/lowlight_isp_pipeline.py.
# =============================================================================
"""awb_channel_diagnostic: post-BLC gray-world channel stats for LOD_test.

binned_raw()'s vectorised twin (_binned_raw in lowlight_isp_pipeline.py) is
reused unmodified for stage (1); only the BLC-only (pedestal subtract +
range restore, NO gain/WB) tail is defined locally here, because
correct_channel() always fuses BLC with gain -- there is no "BLC alone" entry
point in the golden to call instead (same situation blc_sim.py/gain_sim.py
already worked around).

Usage:
    python3 awb_channel_diagnostic.py --raw-bin-dir ../../../../dataset/LOD_test_eval/raw_bin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw

import gen_lowlight_isp_golden as G  # noqa: E402
from lowlight_isp_pipeline import _binned_raw  # noqa: E402


def blc_only(v: np.ndarray) -> np.ndarray:
    """correct_channel()'s pedestal-subtract + range-restore lines, gain
    line omitted -- the post-BLC / pre-gain domain AWB.md §2.1 measures in."""
    v = np.where(v > G.BLC_LEVEL12, v - G.BLC_LEVEL12, 0)
    return np.clip((v.astype(np.int64) * G.BLC_MUL_Q8) >> 8, 0, G.RAW12_MAX)


def per_image_means(path: Path, w: int, h: int) -> tuple[float, float, float]:
    raw16 = np.fromfile(path, dtype="<u2")
    if raw16.size != w * h:
        raise ValueError(f"{path}: size {raw16.size} != {w}*{h}={w*h}")
    raw12 = (raw16.reshape(h, w) >> 4).astype(np.int64)
    bw, bh = G.bin_dim(w), G.bin_dim(h)
    r, g, b = _binned_raw(raw12, bw, bh, G.BIN_BINNING)
    r, g, b = blc_only(r), blc_only(g), blc_only(b)
    return float(r.mean()), float(g.mean()), float(b.mean())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-bin-dir", default=str(
        Path(__file__).resolve().parents[4] / "dataset" / "LOD_test_eval" / "raw_bin"))
    ap.add_argument("--width", type=int, default=5472)
    ap.add_argument("--height", type=int, default=3648)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    raw_dir = Path(args.raw_bin_dir)
    files = sorted(raw_dir.glob("*.bin"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"ERROR: no .bin files under {raw_dir}")
        return 2

    means = []
    for i, f in enumerate(files):
        r, g, b = per_image_means(f, args.width, args.height)
        means.append((r, g, b))
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(files)} processed")

    arr = np.array(means)  # (n, 3) columns R,G,B
    mean_r, mean_g, mean_b = arr.mean(axis=0)
    ratio_rg = mean_r / mean_g
    ratio_bg = mean_b / mean_g

    gw_r = round(256.0 * mean_g / mean_r)
    gw_g = 256
    gw_b = round(256.0 * mean_g / mean_b)

    dep_r, dep_g, dep_b = G.WB_R_Q8, G.WB_G_Q8, G.WB_B_Q8

    print(f"\nn_images = {len(files)}")
    print(f"post-BLC channel means (pre-gain, 12-bit domain): "
          f"R={mean_r:.2f}  G={mean_g:.2f}  B={mean_b:.2f}")
    print(f"channel ratios (vs G): R/G={ratio_rg:.3f}  B/G={ratio_bg:.3f}")
    print(f"gray-world WB (Q8, G=256): R={gw_r}  B={gw_b}")
    print(f"deployed WB (Q8): R={dep_r}  G={dep_g}  B={dep_b}")
    print(f"deployed / gray-world: R={dep_r/gw_r:.2f}x  B={dep_b/gw_b:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
