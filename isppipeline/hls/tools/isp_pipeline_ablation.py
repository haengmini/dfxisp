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

WB-relaxation variants (improvement-strategy-2026-07-03.md Phase 1.1 -- test fixes
for the root cause found in lowlight-rm-map-rootcause-2026-07-02.md: the shared
baseline core's STATIC WB gain is what costs ~70% of low-light mAP on ExDark, not
resolution loss):
  ll_wb_relaxed      : WB gain linearly relaxed toward 1.0x as dark_ratio -> 1
                        (scene-adaptive WB strength), BLC/gain/gamma unchanged     -> H/2xW/2
  ll_blc_relaxed     : BLC offset halved (16->8, 8-bit terms), WB/gain/gamma unchanged -> H/2xW/2
  ll_wb_skip         : WB entirely skipped (gain=256/256 all channels), BLC/gain/gamma unchanged -> H/2xW/2
"""
from __future__ import annotations

import numpy as np

import isp_pipeline_ver1 as P  # reuse BLC/WB/AWB constants and RAW-domain helpers

GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN = P.GAIN_LOWLIGHT_NUM, P.GAIN_LOWLIGHT_DEN
GAMMA_LOWLIGHT = P.GAMMA_LOWLIGHT
_LUT_LOWLIGHT = P._LUT_LOWLIGHT

ARMS = ["ll_bin_only", "ll_bin_radiometric", "ll_bin_gain", "ll_bin_full", "ll_fullres_tone",
        "ll_wb_relaxed", "ll_blc_relaxed", "ll_wb_skip"]


def _blc_wb_gain_custom(rgb16, gnum, gden, blc_raw, awb_r, awb_g, awb_b):
    """Generalized RAW-domain BLC->WB->gain, parameterized (cf. P._blc_wb_gain
    which hardcodes P.BLK_RAW/P.AWB_*)."""
    x = np.clip(rgb16 - blc_raw, 0, None)
    x = x.astype(np.int64)
    x[..., 0] = x[..., 0] * awb_r // 256
    x[..., 1] = x[..., 1] * awb_g // 256
    x[..., 2] = x[..., 2] * awb_b // 256
    x = x * gnum // gden
    return np.clip(x >> P.SHIFT, 0, 255).astype(np.uint8)


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
    if arm == "ll_wb_relaxed":
        # dark_ratio from the SAME checker view used to route to this arm.
        dark_ratio = P.dark_ratio(P.demosaic_rggb(bayer16, w, h))
        awb_r = 256 + (P.AWB_R - 256) * (1.0 - dark_ratio)
        awb_b = 256 + (P.AWB_B - 256) * (1.0 - dark_ratio)
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        rgb8 = _blc_wb_gain_custom(half16, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN,
                                    P.BLK_RAW, int(awb_r), P.AWB_G, int(awb_b))
        return _LUT_LOWLIGHT[rgb8]
    if arm == "ll_blc_relaxed":
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        blc_relaxed = 8 << P.SHIFT  # half of P.BLK_RAW (16<<SHIFT)
        rgb8 = _blc_wb_gain_custom(half16, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN,
                                    blc_relaxed, P.AWB_R, P.AWB_G, P.AWB_B)
        return _LUT_LOWLIGHT[rgb8]
    if arm == "ll_wb_skip":
        half16 = P._bin_demosaic_rggb16(bayer16, w, h)
        rgb8 = _blc_wb_gain_custom(half16, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN,
                                    P.BLK_RAW, 256, 256, 256)
        return _LUT_LOWLIGHT[rgb8]
    raise ValueError(arm)
