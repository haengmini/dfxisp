# =============================================================================
# File   : isppipeline/hls/tools/isp_pipeline_ver1.py
# Date   : 2026-07-02
# Time   : 12:03 KST
# Function: RAW-domain-first ISP pipeline (SW proxy, numpy) — arm reference model
#           order: BLC -> [binning(LL)] -> WB -> exposure gain -> demosaic
#                  -> CCM -> gamma -> pack  (corrections in RAW before precision loss)
# Goal   : Test the reordering proposal (SPEC §3 / experiment-report analysis) that
#          moving BLC/WB/gain into the RAW domain, adding normal-mode exposure gain,
#          and applying gamma in every mode (milder for low-light) should recover the
#          mAP lost by the current post-demosaic order (ver0 = tools/newrm_pipeline.py).
# Compare: ver0 (newrm_pipeline.py) = demosaic -> BLC -> AWB -> CCM, gamma LL-only.
# Note   : SW proxy on dataset pseudo-RAW (RGGB16, shift8). Not the HW/C-sim GRBG path.
# =============================================================================
"""ver1 ISP pipeline: RAW-domain-first ordering.

Arms (same interface as ver0 newrm_pipeline for the eval harness):
  none      : plain demosaic only (reference, identical to ver0)
  normal    : RAW BLC(16)+WB+gain(1.25x) -> demosaic -> CCM -> gamma 2.2   -> H x W
  lowlight  : 2x2 RAW bin -> BLC(8, relaxed 2026-07-03)+WB+gain(2.0x) -> demosaic
              -> CCM -> gamma 2.5 -> H/2 x W/2
  adaptive  : checker (Y<50, ratio>0.80, recalibrated 2026-07-02) picks normal
              vs lowlight per frame
"""
from __future__ import annotations

import numpy as np

# ---- parameters (ver1) ------------------------------------------------------
SHIFT = 8                          # raw_bin 16-bit -> 8-bit domain (>>8 = /256)
BLK_RAW = 16 << SHIFT              # black level in RAW16 domain (= 8-bit 16), normal mode
# Low-light-only BLC relaxation (2026-07-03, root-cause ablation -- see
# src/dfxisp_accel.cpp header / results/phase0-2-execution-2026-07-03.md):
# splitting the earlier "BLC/WB" ablation bucket showed BLC (not WB) is the
# actual driver of low-light mAP loss; halving it recovered ExDark mAP from
# 0.062 to 0.150 (exceeding 'normal'), with no COCO regression.
BLK_RAW_LOWLIGHT = 8 << SHIFT      # black level in RAW16 domain (= 8-bit 8), low-light mode
AWB_R, AWB_G, AWB_B = 286, 256, 307    # Q8 per-channel white balance (color)
GAIN_NORMAL_NUM, GAIN_NORMAL_DEN = 5, 4     # normal exposure gain 1.25x (NEW vs ver0)
GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN = 2, 1  # low-light exposure gain 2.0x
GAMMA_NORMAL = 2.2                 # normal tone curve (NEW vs ver0: ver0 had none)
GAMMA_LOWLIGHT = 2.5               # low-light tone curve (milder than ver0 gamma-4.0)
DARK_Y = 50                        # checker dark-pixel luminance threshold
# Recalibrated 2026-07-02 from measured dataset separation (Youden's J sweep
# over data/{coco_val,exdark_val}): old 0.40 gave ExDark recall=1.00 but COCO
# false-trigger=0.80; 0.80 gives recall=0.90, false-trigger=0.11 (J~=0.79,
# near the J-max at 0.83). See results/experiment_ver2_2026-07-02.md.
DARK_RATIO = 0.80                  # checker: dark_ratio > 0.80 -> low-light


def _gamma_lut(g: float) -> np.ndarray:
    return np.clip(np.round(255.0 * (np.arange(256) / 255.0) ** (1.0 / g)), 0, 255).astype(np.uint8)


_LUT_NORMAL = _gamma_lut(GAMMA_NORMAL)
_LUT_LOWLIGHT = _gamma_lut(GAMMA_LOWLIGHT)


def _demosaic_rggb16(bayer16, w, h):
    """RGGB nearest demosaic, kept in the RAW16 domain (no >>8). Returns int32 planes."""
    b = bayer16.astype(np.int32)
    R = np.zeros((h, w), np.int32); G = np.zeros((h, w), np.int32); B = np.zeros((h, w), np.int32)

    def avg(*a):
        return sum(a) // len(a)

    def shift(a, dy, dx):
        return np.roll(np.roll(a, -dy, axis=0), -dx, axis=1)

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


def _bin_demosaic_rggb16(bayer16, w, h):
    """2x2 RAW binning-demosaic in RAW16 domain (RESEARCH §4.2). -> (H/2, W/2, 3) int32."""
    b = bayer16.astype(np.int32)
    h2, w2 = h - (h % 2), w - (w % 2)
    b = b[:h2, :w2]
    R = b[0::2, 0::2]
    G = (b[0::2, 1::2] + b[1::2, 0::2]) // 2
    B = b[1::2, 1::2]
    return np.stack([R, G, B], -1)   # int32, RAW16 domain


def _blc_wb_gain(rgb16, gnum, gden, blk_raw=BLK_RAW):
    """RAW-domain corrections (before >>8): BLC -> WB(Q8) -> exposure gain."""
    x = np.clip(rgb16 - blk_raw, 0, None)                 # BLC (subtract first)
    x[..., 0] = x[..., 0] * AWB_R // 256                  # WB per channel (Q8)
    x[..., 1] = x[..., 1] * AWB_G // 256
    x[..., 2] = x[..., 2] * AWB_B // 256
    x = x * gnum // gden                                  # exposure gain
    return (np.clip(x >> SHIFT, 0, 255)).astype(np.uint8)  # -> 8-bit LAST (precision preserved)


def demosaic_rggb(bayer16, w, h):
    """8-bit plain demosaic for the 'none' arm and checker view (= ver0 semantics)."""
    return np.clip(_demosaic_rggb16(bayer16, w, h) >> SHIFT, 0, 255).astype(np.uint8)


def luminance(rgb):
    r = rgb[..., 0].astype(np.int32); g = rgb[..., 1].astype(np.int32); b = rgb[..., 2].astype(np.int32)
    return (r + 2 * g + b) // 4


def dark_ratio(rgb):
    return float(np.mean(luminance(rgb) < DARK_Y))


def run_arm(bayer16, w, h, arm):
    if arm == "none":
        return demosaic_rggb(bayer16, w, h)                       # plain demosaic (reference)
    if arm == "normal":
        rgb8 = _blc_wb_gain(_demosaic_rggb16(bayer16, w, h),      # RAW BLC+WB+gain 1.25x
                            GAIN_NORMAL_NUM, GAIN_NORMAL_DEN)
        return _LUT_NORMAL[rgb8]                                   # CCM identity -> gamma 2.2
    if arm == "lowlight":
        rgb8 = _blc_wb_gain(_bin_demosaic_rggb16(bayer16, w, h),  # 2x2 RAW bin -> relaxed BLC+WB+gain 2.0x
                            GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN, BLK_RAW_LOWLIGHT)
        return _LUT_LOWLIGHT[rgb8]                                 # gamma 2.5 (milder)
    if arm == "adaptive":
        if dark_ratio(demosaic_rggb(bayer16, w, h)) > DARK_RATIO:
            return run_arm(bayer16, w, h, "lowlight")
        return run_arm(bayer16, w, h, "normal")
    raise ValueError(arm)


def selected_mode(bayer16, w, h):
    return "lowlight" if dark_ratio(demosaic_rggb(bayer16, w, h)) > DARK_RATIO else "normal"
