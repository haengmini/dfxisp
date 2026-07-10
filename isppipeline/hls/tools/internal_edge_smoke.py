#!/usr/bin/env python3
"""Tiny/odd-dimension smoke + boundary-clamp regression test (2026-07-08 Hermes
robustness review, P1/P2; repointed 2026-07-08 at baseline_isp_pipeline.py /
checker.py after isp_pipeline_ver1.py was archived and superseded).

Two independent checks:

1. gen_golden_vectors.run_frame() on 1x1..8x8 grids (the sizes Hermes smoke-
   tested ad hoc during the review) -- catches crashes/invalid shapes at the
   tiny end of the size range, both NORMAL and LOW_LIGHT-forced.

2. Demosaic boundary-clamp regression, checked against BOTH SW-proxy files
   that carry their own independent copy of the RGGB demosaic
   (baseline_isp_pipeline.py and checker.py -- kept deliberately un-shared,
   see those files' docstrings): perturbing the far border of an image must
   not change a near-border pixel's demosaiced value. This is the actual bug
   Hermes found in the now-archived isp_pipeline_ver1.py -- `_demosaic_rggb16`'s
   neighbor lookup used np.roll() (circular wrap), so a change to the opposite
   edge leaked into this edge's interpolation; the fix (clamp-to-edge) was
   ported into both baseline_isp_pipeline.py and checker.py when they replaced
   isp_pipeline_ver1.py, and this test now guards both copies independently so
   a future edit to either one can't silently reintroduce the wrap-around bug.

   Note: this checks each proxy against *itself* (before/after perturbation),
   not against gen_golden_vectors.demosaic_rggb12. At the time this test was
   written (07-08), the two demosaic implementations used different
   interpolation taps for the R/B planes (gen_golden_vectors bilinear-averages
   2-4 neighbors per RESEARCH §4; the proxy files used single-nearest-tap for
   cross-color positions) and were not bit-exact even away from edges -- that
   gap has since been CLOSED (2026-07-09 fix, both proxy files now bilinear-
   average R/B identically to gen_golden_vectors) and is now covered by its
   own independent cross-check, tools/verify_demosaic_bilinear_cross_check.py
   (same rationale as verify_binning_cross_check.py -- a self-consistency test
   can't catch a shared mistake, so a third independently-written reference
   closes the gap). See results/demosaic-bilinear-fix-2026-07-09.md.

Usage: python3 tools/internal_edge_smoke.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import baseline_isp_pipeline as B
import checker as C
import gen_golden_vectors as G

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


def check_demosaic_boundary_clamp(label: str, demosaic_fn) -> None:
    """Changing the far border must not move the near border's demosaic output."""
    rng = random.Random(1)
    h, w = 16, 16
    raw8 = [rng.randrange(256) for _ in range(w * h)]
    bayer16 = (np.array(raw8, dtype=np.uint16) << 8).reshape(h, w)
    base = demosaic_fn(bayer16, w, h)

    perturbed = bayer16.copy()
    perturbed[-1, :] = (~perturbed[-1, :].astype(np.uint16)) & 0xFF00  # flip the far (bottom) row
    perturbed[:, -1] = (~perturbed[:, -1].astype(np.uint16)) & 0xFF00  # flip the far (right) col
    after = demosaic_fn(perturbed, w, h)

    # Rows/cols far from the perturbed edges (top-left quadrant, away from
    # both the bottom row and right column) must be completely unaffected.
    untouched = base[:h // 2, :w // 2]
    untouched_after = after[:h // 2, :w // 2]
    if not np.array_equal(untouched, untouched_after):
        diff = np.argwhere(np.any(untouched != untouched_after, axis=-1))
        raise AssertionError(
            f"[{label}] boundary leak: perturbing the far edge changed {len(diff)} pixel(s) "
            f"in the near quadrant, e.g. (y,x)={diff[:5].tolist()} -- "
            f"neighbor lookup is not clamped to the local edge"
        )
    print(f"demosaic boundary-clamp OK ({label}): far-edge perturbation did not leak into near edge")


def main() -> int:
    check_golden_tiny_grids()
    check_demosaic_boundary_clamp("baseline_isp_pipeline", B._demosaic_rggb16)
    check_demosaic_boundary_clamp("checker", C._demosaic_rggb16)
    print(f"edge smoke PASS {GRIDS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
