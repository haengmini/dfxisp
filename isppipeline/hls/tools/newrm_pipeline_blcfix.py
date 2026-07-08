#!/usr/bin/env python3
"""BLC recalibration ablation variant of newrm_pipeline.py.

baseline_core's BLC_OFFSET=16 was tuned for pseudo-RAW (inverse-ISP'd sRGB
JPEG) 8-bit statistics. Real Sony RX100 VII sensor raw is far darker: on a
30-image SonyNOD sample, median shift8 pixel value is 2, p90=13, p99=121
(long highlight tail) -- BLC_OFFSET=16 alone clips 92.2% of all pixels to
zero (`frac<=16` above) before AWB/gain/gamma ever act (see
results/realraw-sonynod-benchmark-2026-07-06.md §6bis for the per-frame
99.9% figure on the two darkest samples).

This module reuses demosaic/binning/tone/AWB/dark_ratio unchanged from
newrm_pipeline.py and only swaps baseline_core's fixed BLC_OFFSET=16 for a
parameter, to isolate how much of the SonyNOD mAP gap is attributable to
BLC over-subtraction specifically (arms: normal, lowlight, adaptive --
"none" is out of scope per user direction, since it bypasses the ISP core
entirely). AWB stays at the pipeline's fixed pseudo-RAW-tuned constants
(prior ablation showed real-camera AWB has ~zero effect on mAP here).
"""
from __future__ import annotations

import numpy as np

from newrm_pipeline import (
    AWB_B,
    AWB_G,
    AWB_R,
    LL_GAIN_DEN,
    LL_GAIN_NUM,
    _GAMMA4,
    _bin_demosaic_rggb,
    dark_ratio,
    demosaic_rggb,
)
from newrm_pipeline import DARK_RATIO as DARK_RATIO_THRESH


def baseline_core_blcfix(rgb, blc_offset: int):
    """Same as newrm_pipeline.baseline_core but BLC_OFFSET is a parameter;
    AWB stays fixed at the pipeline's pseudo-RAW-tuned constants."""
    x = rgb.astype(np.int32)
    x = np.clip(x - blc_offset, 0, 255)
    x[..., 0] = np.clip(x[..., 0] * AWB_R // 256, 0, 255)
    x[..., 1] = np.clip(x[..., 1] * AWB_G // 256, 0, 255)
    x[..., 2] = np.clip(x[..., 2] * AWB_B // 256, 0, 255)
    return x.astype(np.uint8)


def tone_low_light(rgb):
    x = np.clip(rgb.astype(np.int32) * LL_GAIN_NUM // LL_GAIN_DEN, 0, 255).astype(np.uint8)
    return _GAMMA4[x]


def run_arm_blcfix(bayer16, w, h, arm, blc_offset: int):
    """Return uint8 RGB for the requested arm using a parameterized BLC
    offset. Only normal/lowlight/adaptive are meaningful here."""
    if arm == "normal":
        return baseline_core_blcfix(demosaic_rggb(bayer16, w, h), blc_offset)
    if arm == "lowlight":
        half = _bin_demosaic_rggb(bayer16, w, h)
        return tone_low_light(baseline_core_blcfix(half, blc_offset))
    if arm == "adaptive":
        rgb = demosaic_rggb(bayer16, w, h)  # checker view: dark_ratio is BLC-independent
        if dark_ratio(rgb) > DARK_RATIO_THRESH:
            half = _bin_demosaic_rggb(bayer16, w, h)
            return tone_low_light(baseline_core_blcfix(half, blc_offset))
        return baseline_core_blcfix(rgb, blc_offset)
    raise ValueError(f"unsupported arm for BLC ablation: {arm}")
