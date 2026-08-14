#!/usr/bin/env python3
"""Verification gate: the vectorised eval proxies must be bit-exact against
the scalar canonical goldens.

`default_isp_pipeline.py` and `lowlight_isp_pipeline.py` exist only because
the scalar generators (`gen_default_isp_golden.py`, `gen_lowlight_isp_golden.py`)
are per-pixel Python loops and cannot render dataset-sized frames. A numpy
rewrite is a second implementation of the same arithmetic, which is exactly
the situation that produced the 2026-07-02 chroma-collapse bug -- a golden
that mirrored the bug it was supposed to catch. So the rewrite is fuzzed
against the scalar reference instead of being assumed correct.

The proxies take dataset raw16 (shift8) and the scalar goldens take raw12,
with `raw12 = raw16 >> 4` exactly; the fuzz feeds both from the same source.

Run: python3 verify_new_arm_pipelines.py [--trials N]
"""
from __future__ import annotations

import argparse
import random

import numpy as np

import default_isp_pipeline as DP
import gen_default_isp_golden as DG
import gen_lowlight_isp_golden as LG
import lowlight_isp_pipeline as LP


def scalar_default(raw12_flat, w, h, awb_mode):
    packed = DG.default_isp(list(raw12_flat), w, h, awb_mode)
    out = np.empty((h, w, 3), dtype=np.uint8)
    for i, v in enumerate(packed):
        out[i // w, i % w] = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
    return out


def scalar_lowlight(raw12_flat, w, h, bin_mode, tone_mode):
    packed, bw, bh = LG.lowlight_isp(list(raw12_flat), w, h, bin_mode, tone_mode)
    out = np.empty((bh, bw, 3), dtype=np.uint8)
    for i, v in enumerate(packed):
        out[i // bw, i % bw] = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20260806)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    checked_px = 0
    # Shapes deliberately include odd dimensions and 1x1: the binning and
    # demosaic edge clamps are where a vectorised rewrite most easily diverges.
    shapes = [(8, 8), (6, 4), (5, 3), (2, 2), (1, 1), (12, 10), (7, 9)]

    for t in range(args.trials):
        w, h = shapes[t % len(shapes)]
        # mix of flat, dark, saturated and random content
        mode = t % 4
        if mode == 0:
            raw12 = [rng.randrange(0, 4096) for _ in range(w * h)]
        elif mode == 1:
            raw12 = [rng.randrange(0, 64) for _ in range(w * h)]       # near floor
        elif mode == 2:
            raw12 = [rng.choice([0, 32, 4095]) for _ in range(w * h)]  # extremes
        else:
            base = rng.randrange(0, 4096)
            raw12 = [min(4095, max(0, base + rng.randrange(-40, 41)))
                     for _ in range(w * h)]                            # flat+noise
        raw16 = np.array([v << 4 for v in raw12], dtype=np.uint16)

        for awb in (DG.AWB_OFF, DG.AWB_ON):
            got = DP.run_default_isp(raw16, w, h, awb)
            exp = scalar_default(raw12, w, h, awb)
            if not np.array_equal(got, exp):
                bad = np.argwhere(got != exp)[0]
                raise SystemExit(
                    f"default_ISP mismatch trial={t} {w}x{h} awb={awb} at {tuple(bad)}: "
                    f"got {got[tuple(bad)]} expected {exp[tuple(bad)]}")
            checked_px += got.size

        for bm in (LG.BIN_SUBSAMPLE, LG.BIN_BINNING):
            for tm in (LG.TONE_GAT, LG.TONE_GAMMA, LG.TONE_LINEAR):
                got = LP.run_lowlight_isp(raw16, w, h, bm, tm)
                exp = scalar_lowlight(raw12, w, h, bm, tm)
                if not np.array_equal(got, exp):
                    bad = np.argwhere(got != exp)[0]
                    raise SystemExit(
                        f"lowlight_ISP mismatch trial={t} {w}x{h} bin={bm} tone={tm} "
                        f"at {tuple(bad)}: got {got[tuple(bad)]} expected {exp[tuple(bad)]}")
                checked_px += got.size

    print(f"[verify_new_arm_pipelines] PASS: {args.trials} trials, "
          f"{checked_px} channel samples, vectorised proxies bit-exact with the "
          f"scalar canonical goldens (default_ISP awb off/on; lowlight_ISP "
          f"binning subsample/samecolour x tone GAT/gamma/linear)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
