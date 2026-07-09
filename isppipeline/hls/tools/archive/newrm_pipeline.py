#!/usr/bin/env python3
"""LEGACY ver0 SW pipeline -- not the canonical DFXISP reference.

Superseded by the 2026-07-02/07-03 reset (RAW-domain-first order, DARK_RATIO
0.80, low-light gain 2.0x, gamma2-style tone, relaxed low-light BLC=8). This
file still reflects the pre-reset parameters (DARK_RATIO=0.40, gain 1.25x,
gamma-4.0, post-demosaic BLC/AWB, BLC_OFFSET=16 fixed) and is kept only for
historical ablations/comparisons that intentionally reference ver0 behavior
(e.g. tools/eval_map_ablation.py lineage). Use gen_golden_vectors.py for
HLS-golden bit-exact behavior and isp_pipeline_ver1.py for current
dataset-scale SW proxy -- do not treat this file as canonical for new work.

Vectorized (numpy) reference of the reset architecture for SW experiments.

shared baseline ISP core + mutually exclusive tone RM slot (RESEARCH.md). This
mirrors the *semantics* of src/dfxisp_accel.cpp for dataset-scale evaluation
(Stage 2 image metrics, Stage 3 mAP). Like tools/eval_map_coco.py it demosaics
RGGB (dataset layout) rather than GRBG (C-sim golden); the arm *behaviour* is
what the SW experiments compare, not per-pixel bit-exactness to the C-sim.

Arms (per RESEARCH condition table):
  none      : demosaic only (no baseline core, no tone)      -> H x W
  normal    : RM_NORMAL_TONE(identity) + baseline core       -> H x W
  lowlight  : RM_LOW_LIGHT_TONE(2x2 RAW bin + gain + gamma4)  -> H/2 x W/2
              wrapped around the baseline core
  adaptive  : checker picks normal vs lowlight per frame

baseline core = BLC(-16) + AWB(Q8 R286/G256/B307) + CCM(identity). No gain/gamma.
"""
from __future__ import annotations

import numpy as np

SHIFT = 8                       # raw_bin 16-bit -> 8-bit domain
BLC_OFFSET = 16
AWB_R, AWB_G, AWB_B = 286, 256, 307
LL_GAIN_NUM, LL_GAIN_DEN = 5, 4
DARK_Y = 50                     # 8-bit dark-pixel luminance threshold
DARK_RATIO = 0.40               # checker: dark_ratio > 0.40 -> low-light

# gamma-4.0 LUT: out = floor((255^3 * v)^(1/4)) == isqrt(isqrt(255^3 * v))
_GAMMA4 = np.array([int(np.floor((16581375 * v) ** 0.25 + 1e-9)) for v in range(256)],
                   dtype=np.int32)
_GAMMA4 = np.clip(_GAMMA4, 0, 255).astype(np.uint8)


def demosaic_rggb(bayer16, w, h):
    """RGGB nearest demosaic -> uint8 RGB (H,W,3). Matches eval_map_coco.py."""
    b = (bayer16 >> SHIFT).astype(np.int32)
    R = np.zeros((h, w), np.int32); G = np.zeros((h, w), np.int32); B = np.zeros((h, w), np.int32)

    def avg(*a):
        return sum(a) // len(a)

    def shift(arr, dy, dx):
        return np.roll(np.roll(arr, -dy, axis=0), -dx, axis=1)

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
    return np.clip(np.stack([R, G, B], -1), 0, 255).astype(np.uint8)


def baseline_core(rgb):
    """demosaic output -> BLC + AWB + CCM(identity). No gain/gamma."""
    x = rgb.astype(np.int32)
    x = np.clip(x - BLC_OFFSET, 0, 255)
    x[..., 0] = np.clip(x[..., 0] * AWB_R // 256, 0, 255)
    x[..., 1] = np.clip(x[..., 1] * AWB_G // 256, 0, 255)
    x[..., 2] = np.clip(x[..., 2] * AWB_B // 256, 0, 255)
    return x.astype(np.uint8)


def _bin_demosaic_rggb(bayer16, w, h):
    """2x2 RAW binning-demosaic (RESEARCH §4.1/§4.2): one RGB per RGGB cell.
    R=top-left, G=(top-right+bottom-left)/2, B=bottom-right. -> (H/2, W/2, 3)."""
    b = (bayer16 >> SHIFT).astype(np.int32)
    h2, w2 = h - (h % 2), w - (w % 2)
    b = b[:h2, :w2]
    R = b[0::2, 0::2]
    G = (b[0::2, 1::2] + b[1::2, 0::2]) // 2
    B = b[1::2, 1::2]
    return np.clip(np.stack([R, G, B], -1), 0, 255).astype(np.uint8)


def tone_low_light(rgb):
    """low-light tone: gain x1.25 then gamma-4.0 LUT."""
    x = np.clip(rgb.astype(np.int32) * LL_GAIN_NUM // LL_GAIN_DEN, 0, 255).astype(np.uint8)
    return _GAMMA4[x]


def luminance(rgb):
    r = rgb[..., 0].astype(np.int32); g = rgb[..., 1].astype(np.int32); b = rgb[..., 2].astype(np.int32)
    return (r + 2 * g + b) // 4


def dark_ratio(rgb):
    return float(np.mean(luminance(rgb) < DARK_Y))


def run_arm(bayer16, w, h, arm):
    """Return uint8 RGB for the requested arm."""
    if arm == "none":
        return demosaic_rggb(bayer16, w, h)
    if arm == "normal":
        return baseline_core(demosaic_rggb(bayer16, w, h))
    if arm == "lowlight":
        half = _bin_demosaic_rggb(bayer16, w, h)   # 2x2 RAW binning-demosaic
        return tone_low_light(baseline_core(half))  # core -> gain -> gamma4
    if arm == "adaptive":
        rgb = demosaic_rggb(bayer16, w, h)          # checker view
        if dark_ratio(rgb) > DARK_RATIO:
            half = _bin_demosaic_rggb(bayer16, w, h)
            return tone_low_light(baseline_core(half))
        return baseline_core(rgb)
    raise ValueError(arm)


def selected_mode(bayer16, w, h):
    """AUTO checker decision on a frame: 'lowlight' or 'normal'."""
    return "lowlight" if dark_ratio(demosaic_rggb(bayer16, w, h)) > DARK_RATIO else "normal"
