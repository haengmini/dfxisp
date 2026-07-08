#!/usr/bin/env python3
"""Tiny/odd-dimension smoke + boundary-clamp regression test (2026-07-08 Hermes
robustness review, P1/P2).

Two independent checks:

1. gen_golden_vectors.run_frame() on 1x1..8x8 grids (the sizes Hermes smoke-
   tested ad hoc during the review) -- catches crashes/invalid shapes at the
   tiny end of the size range, both NORMAL and LOW_LIGHT-forced.

2. isp_pipeline_ver1's demosaic boundary-clamp regression: perturbing the far
   border of an image must not change a near-border pixel's demosaiced value.
   This is the actual bug Hermes found -- `_demosaic_rggb16`'s neighbor lookup
   used np.roll() (circular wrap), so a change to the opposite edge leaked
   into this edge's interpolation; clamp-to-edge must not have that leak.

   Note: this checks isp_pipeline_ver1 against *itself* (before/after
   perturbation), not against gen_golden_vectors.demosaic_rggb12. The two
   demosaic implementations use different interpolation taps for the R/B
   planes (gen_golden_vectors bilinear-averages 2-4 neighbors per RESEARCH
   §4; isp_pipeline_ver1 uses single-nearest-tap for cross-color positions)
   and are not bit-exact even away from edges -- that is a separate, larger
   fidelity gap the 2026-07-08 review did not previously catch and is out of
   scope for this boundary fix.

Usage: python3 tools/internal_edge_smoke.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import gen_golden_vectors as G
import isp_pipeline_ver1 as V

GRIDS = [(1, 1), (2, 1), (1, 2), (2, 2), (3, 3), (5, 7), (8, 8)]  # (h, w)


def check_golden_tiny_grids() -> None:
    rng = random.Random(0)
    for h, w in GRIDS:
        raw = [rng.randrange(4096) for _ in range(w * h)]
        for mode in (G.DFXISP_MODE_NORMAL, G.DFXISP_MODE_LOW_LIGHT, G.DFXISP_MODE_AUTO):
            selected, rm, ow, oh, out = G.run_frame(raw, w, h, mode, dark_threshold=256)
            assert len(out) == ow * oh, f"{w}x{h} mode={mode}: len(out)={len(out)} != {ow}*{oh}"
            assert ow > 0 and oh > 0, f"{w}x{h} mode={mode}: non-positive output shape"
        print(f"golden tiny-grid OK: {w}x{h}")


def check_demosaic_boundary_clamp() -> None:
    """Changing the far border must not move the near border's demosaic output."""
    rng = random.Random(1)
    h, w = 16, 16
    raw8 = [rng.randrange(256) for _ in range(w * h)]
    bayer16 = (np.array(raw8, dtype=np.uint16) << 8).reshape(h, w)
    base = V._demosaic_rggb16(bayer16, w, h)

    perturbed = bayer16.copy()
    perturbed[-1, :] = (~perturbed[-1, :].astype(np.uint16)) & 0xFF00  # flip the far (bottom) row
    perturbed[:, -1] = (~perturbed[:, -1].astype(np.uint16)) & 0xFF00  # flip the far (right) col
    after = V._demosaic_rggb16(perturbed, w, h)

    # Rows/cols far from the perturbed edges (top-left quadrant, away from
    # both the bottom row and right column) must be completely unaffected.
    untouched = base[:h // 2, :w // 2]
    untouched_after = after[:h // 2, :w // 2]
    if not np.array_equal(untouched, untouched_after):
        diff = np.argwhere(np.any(untouched != untouched_after, axis=-1))
        raise AssertionError(
            f"boundary leak: perturbing the far edge changed {len(diff)} pixel(s) "
            f"in the near quadrant, e.g. (y,x)={diff[:5].tolist()} -- "
            f"neighbor lookup is not clamped to the local edge"
        )
    print("demosaic boundary-clamp OK: far-edge perturbation did not leak into near edge")


def main() -> int:
    check_golden_tiny_grids()
    check_demosaic_boundary_clamp()
    print(f"edge smoke PASS {GRIDS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
