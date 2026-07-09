#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/rm_versions.py
# Date   : 2026-07-05 KST
# Branch : exp/principled-checker-rm-2026-07-05
# Campaign version: principled-v3
# Function: Principled low-light RM ISP variants (numpy reference, HW-mappable,
#           integer-friendly). Built ON TOP of the shared baseline core defined
#           in tools/isp_pipeline_ver1.py (RAW-domain-first ordering, the current
#           HW-aligned canonical). Does NOT edit that module.
#
# Versions (see results/lowlight-feature-principles-2026-07-05.md for the math):
#   R0  baseline (== ver1 'lowlight'):  2x2 bin -> BLC8+WB+gain2.0 -> gamma2.5   H/2 x W/2
#   R1  RM_TONE_LUT_PARAM: full-res -> BLC8+WB+gain2.0(upstream)+soft-knee
#                          -> VST/GAT-form sqrt tone LUT                          H x W
#   R2  RM_LL_BIN_DN:      2x2 bin -> BLC8+WB+gain2.0+soft-knee
#                          -> edge-preserving 3x3 denoise -> VST tone LUT         H/2 x W/2
#   R3  RM_TONE_CLAHE:     full-res -> BLC8+WB+gain2.0+soft-knee
#                          -> CLAHE local tone (clip-limited tile equalization)   H x W
#
# API mirrors newrm_pipeline / isp_pipeline_ver1:
#   run_arm(bayer16, w, h, version) -> uint8 RGB (H,W,3) or (H/2,W/2,3)
#   version in {"R0","R1","R2","R3"}  (aliases: r0.., and the descriptive names)
# =============================================================================
"""Principled low-light RM ISP variants (principled-v3 campaign).

Principle basis (canonical doc lowlight-feature-principles-2026-07-05.md):
  - Low-light = low SNR (Poisson-Gaussian sigma^2(y)=a*y+b, Foi 2008), not darkness.
  - Detector-decisive stages = demosaic + tone(gamma) (Buckler ICCV'17; ISP4ML).
  - VST / Anscombe: 2*sqrt(x+3/8) => sqrt-family tone is a *variance stabilizer*
    for Poisson noise, not cosmetics (Anscombe 1948; Makitalo-Foi TIP'11/13).
  - gain upstream in RAW before quantization loss (Chen'18; RESEARCH s4.2).
  - binning +6 dB in read-limited regime, trades spatial resolution for SNR
    (Jin-Hirakawa 2012) -> resolution cost measured via size-AP.
  - edge-preserving (not blanket) denoise: over-denoise kills CNN high-freq
    features (Diamond'21; WaveCNet).
"""
from __future__ import annotations

import numpy as np

import isp_pipeline_ver1 as V   # shared HW-aligned baseline core (do NOT edit)

SHIFT = V.SHIFT
AWB_R, AWB_G, AWB_B = V.AWB_R, V.AWB_G, V.AWB_B
BLK_RAW_LL = V.BLK_RAW_LOWLIGHT              # relaxed BLC (8) for low-light module
GAIN_LL_NUM, GAIN_LL_DEN = V.GAIN_LOWLIGHT_NUM, V.GAIN_LOWLIGHT_DEN   # 2.0x

# ---- VST / GAT-form tone LUT ------------------------------------------------
# Poisson variance stabilizer. Generalized Anscombe form 2*sqrt(y + c): the
# constant c (read-noise / offset term, GAT: 3/8*a^2 + b) FLATTENS the very
# bottom of the curve so the read-noise floor is NOT over-amplified. Normalized
# to a full [0,255] tone curve => this IS the tone stage (single BRAM LUT in HW).
VST_READ_OFFSET = 4.0            # read-floor offset c, in 8-bit code^2 units


def vst_tone_lut(read_offset: float = VST_READ_OFFSET) -> np.ndarray:
    v = np.arange(256, dtype=np.float64)
    f = np.sqrt(v + read_offset)                      # GAT-form sqrt with offset
    out = (f - f[0]) / (f[255] - f[0])                # normalize to [0,1]
    return np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8)


_VST_LUT = vst_tone_lut()


# ---- upstream gain + highlight soft-knee (RAW domain, before 8-bit clip) -----
# gain is applied in the wide RAW domain (before >>SHIFT precision loss). The
# *upper soft-knee* replaces the hard clip at 255 with a smooth Reinhard-style
# roll-off  y' = k + (255-k)*e/((255-k)+e),  e=y-k  -> asymptotic to 255. This
# preserves highlight STRUCTURE (bright-object contours the detector uses)
# instead of flattening it to a saturated plateau.
SOFT_KNEE_8 = 200               # knee point in 8-bit code units


def _blc_wb_gain_knee(rgb16, gnum, gden, blk_raw, knee8=SOFT_KNEE_8):
    """RAW-domain BLC -> WB(Q8) -> exposure gain -> highlight soft-knee -> 8-bit."""
    x = np.clip(rgb16.astype(np.int64) - blk_raw, 0, None)
    x[..., 0] = x[..., 0] * AWB_R // 256
    x[..., 1] = x[..., 1] * AWB_G // 256
    x[..., 2] = x[..., 2] * AWB_B // 256
    x = x * gnum // gden
    y = (x >> SHIFT).astype(np.float64)               # to ~8-bit scale (may exceed 255)
    head = 255.0 - knee8
    over = y > knee8
    e = y[over] - knee8
    y[over] = knee8 + head * e / (head + e)           # smooth roll-off, ->255
    return np.clip(np.round(y), 0, 255).astype(np.uint8)


# ---- edge-preserving 3x3 denoise (integer sigma-filter) ---------------------
# Range-thresholded neighbourhood average (Lee sigma filter / integer bilateral
# approximation): a neighbour contributes only if its luma differs from the
# centre by <= thr. Flat regions -> noise averaged out; edges -> cross-edge
# neighbours excluded, so high-frequency structure is preserved (avoids the
# CNN-feature loss of blanket smoothing, Diamond'21). HW: 3x3 => 2 line buffers;
# after binning the width is halved, so the buffer is half-length (survey B.2.1).
DENOISE_THR = 12


def edge_preserve_3x3(rgb8, thr=DENOISE_THR):
    x = rgb8.astype(np.int32)
    lum = (x[..., 0] + 2 * x[..., 1] + x[..., 2]) // 4
    acc = np.zeros_like(x)
    cnt = np.zeros(x.shape[:2], np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ln = np.roll(np.roll(lum, dy, 0), dx, 1)
            xn = np.roll(np.roll(x, dy, 0), dx, 1)
            m = (np.abs(ln - lum) <= thr)
            acc += xn * m[..., None]
            cnt += m.astype(np.int32)
    out = acc // np.maximum(cnt, 1)[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


# ---- CLAHE local tone (R3) --------------------------------------------------
# Clip-limited adaptive histogram equalization on luma; RGB scaled by the luma
# gain map. Clip limit bounds per-tile contrast gain => bounds noise
# amplification (the built-in safety vs plain HE / retinex, survey B.2.7).
# HW note: tile histograms need frame-level stats -> use previous-frame stats
# (frame-lag) to stay streaming; here (SW reference) computed within-frame.
def clahe_local_tone(rgb8, clip=2.0, tiles=8):
    import cv2
    x = rgb8.astype(np.uint8)
    ycrcb = cv2.cvtColor(x, cv2.COLOR_RGB2YCrCb)
    y = ycrcb[..., 0]
    cl = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles))
    y2 = cl.apply(y)
    # scale chroma-bearing RGB by the per-pixel luma gain (keeps hue, lifts local
    # contrast). integer-friendly gain map in Q8.
    yg = np.maximum(y.astype(np.int32), 1)
    gain_q8 = (y2.astype(np.int32) * 256) // yg
    out = (x.astype(np.int32) * gain_q8[..., None]) // 256
    return np.clip(out, 0, 255).astype(np.uint8)


# ---- versions ---------------------------------------------------------------
def _r0_baseline(bayer16, w, h):
    """R0 == current HW-aligned low-light RM (ver1 'lowlight'): 2x2 bin +
    BLC8+WB+gain2.0 + gamma2.5. H/2 x W/2. Controlled baseline."""
    return V.run_arm(bayer16, w, h, "lowlight")


def _r1_tone_lut_param(bayer16, w, h):
    """R1 RM_TONE_LUT_PARAM: full-res (NO binning) + upstream gain + soft-knee
    + VST/GAT sqrt tone LUT. Preserves resolution (small objects); tone is the
    variance-stabilizing decisive stage."""
    rgb16 = V._demosaic_rggb16(bayer16, w, h)                     # full-res RAW planes
    rgb8 = _blc_wb_gain_knee(rgb16, GAIN_LL_NUM, GAIN_LL_DEN, BLK_RAW_LL)
    return _VST_LUT[rgb8]


def _r2_ll_bin_dn(bayer16, w, h):
    """R2 RM_LL_BIN_DN: 2x2 bin (+6 dB SNR) + edge-preserving denoise + VST tone.
    Raises SNR then stabilizes variance; denoise is edge-preserving to keep
    CNN high-freq features."""
    rgb16 = V._bin_demosaic_rggb16(bayer16, w, h)                # H/2 x W/2 RAW planes
    rgb8 = _blc_wb_gain_knee(rgb16, GAIN_LL_NUM, GAIN_LL_DEN, BLK_RAW_LL)
    rgb8 = edge_preserve_3x3(rgb8)
    return _VST_LUT[rgb8]


def _r3_tone_clahe(bayer16, w, h):
    """R3 RM_TONE_CLAHE: full-res + upstream gain + soft-knee + CLAHE local
    tone. Local contrast compensation for non-uniform low light."""
    rgb16 = V._demosaic_rggb16(bayer16, w, h)
    rgb8 = _blc_wb_gain_knee(rgb16, GAIN_LL_NUM, GAIN_LL_DEN, BLK_RAW_LL)
    return clahe_local_tone(rgb8)


_VERSIONS = {
    "R0": _r0_baseline,           "r0": _r0_baseline,
    "R1": _r1_tone_lut_param,     "r1": _r1_tone_lut_param,
    "R2": _r2_ll_bin_dn,          "r2": _r2_ll_bin_dn,
    "R3": _r3_tone_clahe,         "r3": _r3_tone_clahe,
    "baseline": _r0_baseline,
    "RM_TONE_LUT_PARAM": _r1_tone_lut_param,
    "RM_LL_BIN_DN": _r2_ll_bin_dn,
    "RM_TONE_CLAHE": _r3_tone_clahe,
}

VERSION_NAMES = {
    "R0": "R0_baseline (bin+gain+gamma2.5)",
    "R1": "R1_RM_TONE_LUT_PARAM (fullres+VST)",
    "R2": "R2_RM_LL_BIN_DN (bin+denoise+VST)",
    "R3": "R3_RM_TONE_CLAHE (fullres+CLAHE)",
}


def run_arm(bayer16, w, h, version):
    """Return uint8 RGB for the requested RM version."""
    fn = _VERSIONS.get(version) or _VERSIONS.get(str(version).upper())
    if fn is None:
        raise ValueError(f"unknown RM version {version!r}; known: {sorted(set(VERSION_NAMES))}")
    return fn(bayer16, w, h)


if __name__ == "__main__":
    # smoke test on a synthetic RGGB frame
    w, h = 64, 48
    rng = np.random.default_rng(0)
    bayer = (rng.random((h, w)) * 4000).astype("<u2")
    for ver in ("R0", "R1", "R2", "R3"):
        out = run_arm(bayer, w, h, ver)
        print(f"{ver:3s} -> {out.shape} dtype={out.dtype} mean={out.mean():.1f} "
              f"min={out.min()} max={out.max()}")
