#!/usr/bin/env python3
"""AWB domain-gap ablation variant of newrm_pipeline.py.

baseline_core's AWB gains (Q8 R286/G256/B307) were tuned for pseudo-RAW
(inverse-ISP'd sRGB JPEG) color statistics. Real Sony RX100 VII sensor raw
needs a much larger correction -- measured via rawpy `camera_whitebalance`
on the SonyNOD real-RAW benchmark (see results/realraw-sonynod-benchmark-*.md):
R/G ~1.48-2.47 (mean ~1.95), B/G ~1.57-3.07 (mean ~2.17), vs the fixed
1.117/1.199 the pipeline applies -- a systematic ~1.7-1.8x undercorrection
that shows up as a visible green cast on real-RAW arm output.

This module reuses demosaic/binning/tone/dark_ratio unchanged from
newrm_pipeline.py and only swaps baseline_core's fixed AWB gains for
per-image real camera AWB (converted to the same Q8 convention), to isolate
how much of the SonyNOD mAP gap / arm-order flip is attributable to this
AWB mismatch specifically (arms: normal, lowlight, adaptive -- "none" is
out of scope, per user direction, since it bypasses the ISP core entirely).
"""
from __future__ import annotations

import numpy as np

from newrm_pipeline import (
    BLC_OFFSET,
    LL_GAIN_DEN,
    LL_GAIN_NUM,
    _GAMMA4,
    _bin_demosaic_rggb,
    dark_ratio,
    demosaic_rggb,
)
from newrm_pipeline import DARK_RATIO as DARK_RATIO_THRESH


def baseline_core_realwb(rgb, awb_r: int, awb_b: int):
    """Same as newrm_pipeline.baseline_core but AWB gains are parameters
    (Q8, G fixed at 256) instead of the fixed pseudo-RAW-tuned constants."""
    x = rgb.astype(np.int32)
    x = np.clip(x - BLC_OFFSET, 0, 255)
    x[..., 0] = np.clip(x[..., 0] * awb_r // 256, 0, 255)
    x[..., 2] = np.clip(x[..., 2] * awb_b // 256, 0, 255)
    return x.astype(np.uint8)


def tone_low_light(rgb):
    x = np.clip(rgb.astype(np.int32) * LL_GAIN_NUM // LL_GAIN_DEN, 0, 255).astype(np.uint8)
    return _GAMMA4[x]


def run_arm_realwb(bayer16, w, h, arm, awb_r: int, awb_b: int):
    """Return uint8 RGB for the requested arm using per-image real AWB gains.
    Only normal/lowlight/adaptive are meaningful here (none bypasses AWB)."""
    if arm == "normal":
        return baseline_core_realwb(demosaic_rggb(bayer16, w, h), awb_r, awb_b)
    if arm == "lowlight":
        half = _bin_demosaic_rggb(bayer16, w, h)
        return tone_low_light(baseline_core_realwb(half, awb_r, awb_b))
    if arm == "adaptive":
        rgb = demosaic_rggb(bayer16, w, h)
        if dark_ratio(rgb) > DARK_RATIO_THRESH:
            half = _bin_demosaic_rggb(bayer16, w, h)
            return tone_low_light(baseline_core_realwb(half, awb_r, awb_b))
        return baseline_core_realwb(rgb, awb_r, awb_b)
    raise ValueError(f"unsupported arm for AWB ablation: {arm}")
