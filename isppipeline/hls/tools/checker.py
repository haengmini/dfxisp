# =============================================================================
# File   : isppipeline/hls/tools/checker.py
# Date   : 2026-07-08
# Function: Adaptive-mode dark-ratio scene checker, decoupled from both the
#           normal and low-light SW proxy pipelines.
# =============================================================================
"""checker: dark-ratio scene checker matching checker_select_mode in
src/dfxisp_accel.cpp (DARK_RATIO_PCT=80, i.e. ratio threshold 0.80; dark-pixel
luminance threshold DARK_Y=50).

This is the decoupled checker used by an eval harness to decide which of
baseline_isp_pipeline.run_normal / low_light_isp_pipeline.run_lowlight to
call per frame. The "adaptive" arm is not internal to any one pipeline file:
it is the composition of this checker plus both pipelines, performed by the
caller.

Fully self-contained (numpy only): carries its own tiny plain-nearest RGGB
demosaic helper (pre-BLC/WB/gain/gamma, the same "none"/checker view used by
canonical) rather than importing it from baseline_isp_pipeline.py, to keep
all three files fully independent per explicit instruction.
"""
from __future__ import annotations

import numpy as np

# ---- parameters (must match dfxisp_accel.cpp checker_select_mode) ---------
SHIFT = 8               # raw16 -> 8-bit domain (>>8 = /256)
DARK_Y = 50             # checker dark-pixel luminance threshold (DARK_Y-equivalent)
DARK_RATIO_PCT = 80     # AUTO -> LOW_LIGHT when dark pixels > 80% (DARK_RATIO_PCT in dfxisp_accel.cpp)
DARK_RATIO = DARK_RATIO_PCT / 100.0


def _demosaic_rggb16(bayer16, w, h):
    """RGGB nearest demosaic, kept in the RAW16 domain (no >>8). Returns int32 planes."""
    b = bayer16.astype(np.int32)
    R = np.zeros((h, w), np.int32); G = np.zeros((h, w), np.int32); B = np.zeros((h, w), np.int32)

    def avg(*a):
        return sum(a) // len(a)

    def shift(a, dy, dx):
        # Clamp-to-edge (matches gen_golden_vectors.sample_clamped / src/dfxisp_accel.cpp).
        # NOT np.roll(): a circular wrap would pull the opposite border's pixels
        # into this array's border neighbors, which the HLS/golden path never does.
        ys = np.clip(np.arange(h) + dy, 0, h - 1)
        xs = np.clip(np.arange(w) + dx, 0, w - 1)
        return a[ys[:, None], xs[None, :]]

    yy, xx = np.mgrid[0:h, 0:w]
    ey = (yy % 2 == 0); ex = (xx % 2 == 0)
    R[ey & ex] = b[ey & ex]
    R[ey & ~ex] = shift(b, 0, -1)[ey & ~ex]
    R[~ey & ex] = shift(b, -1, 0)[~ey & ex]
    R[~ey & ~ex] = shift(b, -1, -1)[~ey & ~ex]
    B[~ey & ~ex] = b[~ey & ~ex]
    B[~ey & ex] = shift(b, 0, 1)[~ey & ex]
    B[ey & ~ex] = shift(b, 1, 0)[ey & ~ex]
    B[ey & ex] = shift(b, 1, 1)[ey & ex]
    G[(ey & ~ex) | (~ey & ex)] = b[(ey & ~ex) | (~ey & ex)]
    gmiss = (ey & ex) | (~ey & ~ex)
    G[gmiss] = avg(shift(b, 0, 1), shift(b, 0, -1), shift(b, 1, 0), shift(b, -1, 0))[gmiss]
    return np.stack([R, G, B], -1)   # int32, RAW16 domain


def demosaic_rggb(bayer16, w, h):
    """8-bit plain demosaic, pre-BLC/WB/gain/gamma -- the checker's view of the frame."""
    return np.clip(_demosaic_rggb16(bayer16, w, h) >> SHIFT, 0, 255).astype(np.uint8)


def luminance(rgb):
    r = rgb[..., 0].astype(np.int32); g = rgb[..., 1].astype(np.int32); b = rgb[..., 2].astype(np.int32)
    return (r + 2 * g + b) // 4


def dark_ratio(rgb):
    return float(np.mean(luminance(rgb) < DARK_Y))


def selected_mode(bayer16, w, h):
    """Return "lowlight" or "normal" per the canonical dark-ratio checker."""
    return "lowlight" if dark_ratio(demosaic_rggb(bayer16, w, h)) > DARK_RATIO else "normal"
