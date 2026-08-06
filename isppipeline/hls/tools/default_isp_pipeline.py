#!/usr/bin/env python3
"""SW eval proxy for default_ISP -- vectorised, canonical-matched.

Canonical status: **SW eval proxy (canonical-matched)** for
src/default_isp.cpp. The scalar canonical golden is
tools/gen_default_isp_golden.py; this module is a numpy port of exactly that
arithmetic so it can render dataset-sized frames (the scalar generator is a
per-pixel Python loop, fine for 8x8 fixtures and hopeless for 5472x3648).

Bit-exactness against the scalar golden is not assumed -- it is tested by
tools/verify_new_arm_pipelines.py, which fuzzes random grids through both.

Interface matches baseline_isp_pipeline / low_light_isp_pipeline so
eval_map_isp.py can dispatch to it the same way:
    run_arm(bayer16, w, h, arm, blc_offset=None) -> H x W x 3 uint8

Domain note: the dataset raw16 is shift8 (an 8-bit value in the high byte),
while default_ISP is defined on the 12-bit HLS domain, so the conversion is
exactly `raw12 = raw16 >> 4` (the low 8 bits are zero by construction).
"""
from __future__ import annotations

import numpy as np

import gen_default_isp_golden as G

# Every constant is imported from the scalar canonical golden rather than
# restated here, so the proxy cannot drift from canon.
RAW12_MAX = G.RAW12_MAX
BLC_LEVEL12 = G.BLC_LEVEL12
BLC_MUL_Q8 = G.BLC_MUL_Q8
GAIN_R_Q8 = G.GAIN_R_Q8
GAIN_B_Q8 = G.GAIN_B_Q8
AWB_GAIN_MIN_Q8 = G.AWB_GAIN_MIN_Q8
AWB_GAIN_MAX_Q8 = G.AWB_GAIN_MAX_Q8
CCM_Q8 = np.asarray(G.CCM_Q8, dtype=np.int64)
AWB_OFF = G.AWB_OFF
AWB_ON = G.AWB_ON
GAMMA2_LUT = np.asarray(G.GAMMA2_LUT, dtype=np.uint8)


def _bayer_gain_plane(h: int, w: int) -> np.ndarray:
    """Per-site gaincontrol factor, RGGB: (0,0)=R (0,1)=G (1,0)=G (1,1)=B."""
    g = np.full((h, w), 256, dtype=np.int64)
    g[0::2, 0::2] = GAIN_R_Q8
    g[1::2, 1::2] = GAIN_B_Q8
    return g


def _corrected_bayer(raw12: np.ndarray) -> np.ndarray:
    """Stages (1) blackLevelCorrection + (2) gaincontrol, Bayer domain."""
    h, w = raw12.shape
    v = raw12.astype(np.int64)
    v = np.where(v > BLC_LEVEL12, v - BLC_LEVEL12, 0)
    v = np.clip((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    v = np.clip((v * _bayer_gain_plane(h, w)) >> 8, 0, RAW12_MAX)
    return v


def _demosaic(corr: np.ndarray):
    """Stage (3): RGGB bilinear on the corrected plane, clamp-to-edge."""
    h, w = corr.shape
    p = np.pad(corr, 1, mode="edge")
    win = [[p[wy:wy + h, wx:wx + w] for wx in range(3)] for wy in range(3)]
    c = win[1][1]

    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    even_y = (yy & 1) == 0
    even_x = (xx & 1) == 0

    horiz2 = (win[1][0] + win[1][2]) // 2
    vert2 = (win[0][1] + win[2][1]) // 2
    cross4 = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
    diag4 = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4

    r = np.select([even_y & even_x, even_y & ~even_x, ~even_y & even_x],
                  [c, horiz2, vert2], default=diag4)
    g = np.select([even_y & even_x, even_y & ~even_x, ~even_y & even_x],
                  [cross4, c, c], default=cross4)
    b = np.select([even_y & even_x, even_y & ~even_x, ~even_y & even_x],
                  [diag4, vert2, horiz2], default=c)
    return r, g, b


def _awb_gains(corr: np.ndarray):
    """Stage (4): gray-world means over corrected Bayer sites.

    Green is the reference channel, so only R and B gains are returned.
    """
    sum_r = int(corr[0::2, 0::2].sum())
    cnt_r = corr[0::2, 0::2].size
    sum_b = int(corr[1::2, 1::2].sum())
    cnt_b = corr[1::2, 1::2].size
    sum_g = int(corr[0::2, 1::2].sum()) + int(corr[1::2, 0::2].sum())
    cnt_g = corr[0::2, 1::2].size + corr[1::2, 0::2].size

    mean_r = sum_r // cnt_r if cnt_r else 0
    mean_g = sum_g // cnt_g if cnt_g else 0
    mean_b = sum_b // cnt_b if cnt_b else 0
    gain_r = (min(max((mean_g * 256) // mean_r, AWB_GAIN_MIN_Q8), AWB_GAIN_MAX_Q8)
              if (mean_r > 0 and mean_g > 0) else 256)
    gain_b = (min(max((mean_g * 256) // mean_b, AWB_GAIN_MIN_Q8), AWB_GAIN_MAX_Q8)
              if (mean_b > 0 and mean_g > 0) else 256)
    return gain_r, gain_b


def _ccm_channel(row: int, r12, g12, b12):
    """Stage (5); accumulator floored before the shift (matches the scalar)."""
    acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12
    acc = np.maximum(acc, 0)
    return np.clip(acc >> 8, 0, RAW12_MAX)


def run_default_isp(bayer16, w: int, h: int, awb_mode: int = AWB_ON) -> np.ndarray:
    """default_ISP over a full frame -> H x W x 3 uint8."""
    raw12 = (np.asarray(bayer16).reshape(h, w).astype(np.int64)) >> 4
    corr = _corrected_bayer(raw12)
    r12, g12, b12 = _demosaic(corr)

    awb_r, awb_b = (256, 256)
    if awb_mode == AWB_ON:
        awb_r, awb_b = _awb_gains(corr)
    r12 = np.clip((r12 * awb_r) >> 8, 0, RAW12_MAX)
    b12 = np.clip((b12 * awb_b) >> 8, 0, RAW12_MAX)   # g12: reference channel

    rc = _ccm_channel(0, r12, g12, b12)
    gc = _ccm_channel(1, r12, g12, b12)
    bc = _ccm_channel(2, r12, g12, b12)

    out = np.empty((h, w, 3), dtype=np.uint8)
    out[..., 0] = GAMMA2_LUT[(rc >> 4).astype(np.uint8)]
    out[..., 1] = GAMMA2_LUT[(gc >> 4).astype(np.uint8)]
    out[..., 2] = GAMMA2_LUT[(bc >> 4).astype(np.uint8)]
    return out


def run_arm(bayer16, w: int, h: int, arm: str, blc_offset=None) -> np.ndarray:
    """eval_map_isp.py dispatch entry.

    `blc_offset` is accepted for interface symmetry with the v1 arms but is
    NOT swept here: default_ISP's black level is a Bayer-domain constant tied
    to its range-restore multiplier, so changing one without the other is not
    a meaningful ablation. Passing a value raises rather than silently
    ignoring it.
    """
    if blc_offset is not None:
        raise ValueError("default_isp does not support the BLC sweep "
                         "(black level is coupled to BLC_MUL_Q8)")
    if arm == "default_isp":
        return run_default_isp(bayer16, w, h, AWB_ON)
    if arm == "default_isp_noawb":
        return run_default_isp(bayer16, w, h, AWB_OFF)
    raise ValueError(arm)
