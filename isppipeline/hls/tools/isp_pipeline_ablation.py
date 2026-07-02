# =============================================================================
# File   : isppipeline/hls/tools/isp_pipeline_ablation.py
# Date   : 2026-07-02
# Time   : 23:10 KST
# Function: Low-light RM ablation -- decompose the lowlight arm (2x2 bin ->
#           BLC/WB -> gain 2.0x -> gamma 2.5, isp_pipeline_ver1.py) into its
#           constituent stages and isolate each stage's effect on mAP, plus an
#           inverse ablation (same tone curve at full resolution, no binning)
#           to separate "resolution loss" from "tone-curve" as causes.
# Goal   : experiment_ver1_2026-07-02.md left this as an open TODO ("ver2-A:
#          tone(gamma)만 분리 실험") -- this executes it. Reuses
#          tools/isp_pipeline_ver1.py's RAW-domain helper functions verbatim
#          (same BLC/WB/AWB constants) so results are directly comparable to
#          the existing 'lowlight' arm numbers.
# =============================================================================
"""Ablation arms for the low-light RM, same interface as isp_pipeline_ver1.run_arm.

  ll_bin_only        : 2x2 RAW bin-demosaic only, plain >>8, no BLC/WB/gain/gamma -> H/2xW/2
                        (isolates: resolution loss alone, radiometrically neutral)
  ll_bin_radiometric : + BLC/WB (Q8, no gain, no gamma)                             -> H/2xW/2
                        (isolates: + black-level/white-balance correction)
  ll_bin_gain        : + exposure gain 2.0x (still no gamma, linear)                -> H/2xW/2
                        (isolates: + exposure gain)
  ll_bin_full        : + gamma 2.5 (== isp_pipeline_ver1's 'lowlight' arm, included
                        here for a single-harness comparison)                       -> H/2xW/2
  ll_fullres_tone    : SAME BLC/WB/gain(2.0x)/gamma(2.5) tone chain, but on the
                        FULL-RES demosaic (no 2x2 binning)                          -> HxW
                        (isolates: tone-curve effect alone, resolution held constant
                        against 'normal'/'none' -- the inverse ablation)
"""
from __future__ import annotations

import numpy as np

import isp_pipeline_ver1 as P  # reuse BLC/WB/AWB constants and RAW-domain helpers

GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN = P.GAIN_LOWLIGHT_NUM, P.GAIN_LOWLIGHT_DEN
GAMMA_LOWLIGHT = P.GAMMA_LOWLIGHT
_LUT_LOWLIGHT = P._LUT_LOWLIGHT

ARMS = ["ll_bin_only", "ll_bin_radiometric", "ll_bin_gain", "ll_bin_full", "ll_fullres_tone"]


def _to_u8_plain(rgb16):
    """Plain >>8, no correction (radiometrically neutral downsample)."""
    return np.clip(rgb16 >> P.SHIFT, 0, 255).astype(np.uint8)


def _blc_wb_only(rgb16):
    """BLC + WB (Q8), NO exposure gain, NO gamma -- gain=1/1 through _blc_wb_gain."""
    return P._blc_wb_gain(rgb16, 1, 1)


def _blc_wb_gain_only(rgb16, gnum, gden):
    """BLC + WB + exposure gain, NO gamma (linear 8-bit output)."""
    return P._blc_wb_gain(rgb16, gnum, gden)


def run_arm(bayer16, w, h, arm):
    if arm == "ll_bin_only":
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        return _to_u8_plain(half16)
    if arm == "ll_bin_radiometric":
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        return _blc_wb_only(half16)
    if arm == "ll_bin_gain":
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        return _blc_wb_gain_only(half16, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN)
    if arm == "ll_bin_full":
        return P.run_arm(bayer16, w, h, "lowlight")
    if arm == "ll_fullres_tone":
        full16 = P._demosaic_rggb16(bayer16, w, h)
        rgb8 = P._blc_wb_gain(full16, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN)
        return _LUT_LOWLIGHT[rgb8]
    raise ValueError(arm)
