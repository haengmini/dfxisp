#!/usr/bin/env python3
"""SW eval proxy for lowlight_ISP -- vectorised, canonical-matched.

Canonical status: **SW eval proxy (canonical-matched)** for
src/lowlight_isp.cpp. The scalar canonical golden is
tools/gen_lowlight_isp_golden.py; this module is a numpy port of exactly that
arithmetic so it can render dataset-sized frames.

Every constant (including the 4096-entry GAT table) is IMPORTED from the
scalar golden rather than restated, so the proxy cannot drift from canon.
Bit-exactness of the arithmetic is fuzz-tested by
tools/verify_new_arm_pipelines.py.

Interface matches the other arm modules:
    run_arm(bayer16, w, h, arm) -> (H/2) x (W/2) x 3 uint8   (Policy A)

Domain note: dataset raw16 is shift8, lowlight_ISP is defined on the 12-bit
HLS domain, so `raw12 = raw16 >> 4` exactly.
"""
from __future__ import annotations

import numpy as np

import gen_lowlight_isp_golden as G

RAW12_MAX = G.RAW12_MAX
# One 4096-entry uint8 table per stage-(5) curve, built from the scalar golden's
# derivation so the proxy cannot drift. GAMMA is the deployed curve; GAT and
# LINEAR exist only for the tone-curve ablation (see the golden for why).
# GAMMA is the deployed curve since 2026-08-06.
TONE_LUTS = {mode: np.asarray(G.tone_lut(mode), dtype=np.uint8)
             for mode in (G.TONE_GAT, G.TONE_GAMMA, G.TONE_LINEAR)}
# int32 throughout: the widest intermediate is the CCM accumulator
# (288 * 4095 * 3 ~ 3.5e6) and the BLC range-restore (4095 * 258 ~ 1.06e6),
# both far inside int32. Halves peak memory per 20MP frame, which is what
# limits how many render workers fit in RAM.
CCM_Q8 = np.asarray(G.CCM_Q8, dtype=np.int32)

BIN_SUBSAMPLE = G.BIN_SUBSAMPLE
BIN_BINNING = G.BIN_BINNING


def _cell_planes(raw12: np.ndarray, bw: int, bh: int):
    """The four Bayer sites of every 2x2 cell, as (bh, bw) planes."""
    h, w = raw12.shape
    cx = np.arange(bw)
    cy = np.arange(bh)
    x0 = 2 * cx
    x1 = np.minimum(2 * cx + 1, w - 1)
    y0 = 2 * cy
    y1 = np.minimum(2 * cy + 1, h - 1)
    return (raw12[np.ix_(y0, x0)],   # R  (top-left)
            raw12[np.ix_(y0, x1)],   # G  (top-right)
            raw12[np.ix_(y1, x0)],   # G  (bottom-left)
            raw12[np.ix_(y1, x1)])   # B  (bottom-right)


def _binned_raw(raw12: np.ndarray, bw: int, bh: int, bin_mode: int):
    """Stage (1): binning in the RAW domain, before any correction."""
    r_c, g0_c, g1_c, b_c = _cell_planes(raw12, bw, bh)
    if bin_mode == BIN_SUBSAMPLE:
        return r_c, (g0_c + g1_c) // 2, b_c

    # 2x2 averaging by Bayer color over neighbouring cells, clamped at the edges
    yi0 = np.arange(bh)
    yi1 = np.minimum(yi0 + 1, bh - 1)
    xi0 = np.arange(bw)
    xi1 = np.minimum(xi0 + 1, bw - 1)

    def nb(plane):
        return (plane[np.ix_(yi0, xi0)] + plane[np.ix_(yi0, xi1)] +
                plane[np.ix_(yi1, xi0)] + plane[np.ix_(yi1, xi1)])

    return nb(r_c) // 4, (nb(g0_c) + nb(g1_c)) // 8, nb(b_c) // 4


def _correct_channel(v, wb_q8: int):
    """Stages (2) black level and (3) gain, applied once to the binned value."""
    v = np.where(v > G.BLC_LEVEL12, v - G.BLC_LEVEL12, 0)
    v = np.clip((v * G.BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    gain_q8 = (G.EXPOSURE_GAIN_Q8 * wb_q8) >> 8
    return np.clip((v * gain_q8) >> 8, 0, RAW12_MAX)


def _ccm_channel(row: int, r12, g12, b12):
    acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12
    acc = np.maximum(acc, 0)
    return np.clip(acc >> 8, 0, RAW12_MAX)


def run_lowlight_isp(bayer16, w: int, h: int,
                     bin_mode: int = BIN_BINNING,
                     tone_mode: int = G.TONE_GAMMA) -> np.ndarray:
    """lowlight_ISP over a full frame -> (H/2) x (W/2) x 3 uint8 (Policy A)."""
    raw12 = (np.asarray(bayer16).reshape(h, w).astype(np.int32)) >> 4
    bw, bh = max(1, w // 2), max(1, h // 2)

    r12, g12, b12 = _binned_raw(raw12, bw, bh, bin_mode)
    r12 = _correct_channel(r12, G.WB_R_Q8)
    g12 = _correct_channel(g12, G.WB_G_Q8)
    b12 = _correct_channel(b12, G.WB_B_Q8)

    lut = TONE_LUTS[tone_mode]
    planes = [lut[_ccm_channel(i, r12, g12, b12)] for i in range(3)]

    out = np.empty((bh, bw, 3), dtype=np.uint8)
    for i in range(3):
        out[..., i] = np.asarray(planes[i], dtype=np.uint8)
    return out


def run_arm(bayer16, w: int, h: int, arm: str) -> np.ndarray:
    """eval_map_isp.py dispatch entry. Arm names encode the ablation axes."""
    table = {
        # deployed arm (gamma 2.0 since 2026-08-06)
        "lowlight_isp": (BIN_BINNING, G.TONE_GAMMA),
        # binning ablation, paired with the deployed curve
        "lowlight_isp_subsample": (BIN_SUBSAMPLE, G.TONE_GAMMA),
        # tone-curve ablation: same binning, stage (5) is the only difference
        "lowlight_isp_gat": (BIN_BINNING, G.TONE_GAT),
        "lowlight_isp_linear": (BIN_BINNING, G.TONE_LINEAR),
    }
    if arm not in table:
        raise ValueError(arm)
    bm, tm = table[arm]
    return run_lowlight_isp(bayer16, w, h, bm, tm)
