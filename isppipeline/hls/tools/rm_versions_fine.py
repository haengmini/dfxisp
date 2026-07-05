#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/rm_versions_fine.py
# Date   : 2026-07-05 KST
# Branch : exp/principled-checker-rm-2026-07-05
# Campaign version: principled-v3
# Function: FINER-GRAINED low-light RM versions that DISENTANGLE the two factors
#           the first pass confounded, plus a VST-offset sensitivity sweep.
#
# WHY (self-review + Codex-review gap G-RM-1, the key confound):
#   The first pass compared R0 (isp_pipeline_ver1 'lowlight' = 2x2 bin + gamma
#   2.5) against R1 (full-res + VST/sqrt tone). That single step changes TWO
#   things at once -- resolution (bin->full) AND tone curve (gamma2.5 -> sqrt
#   VST). Worse, the DEPLOYED canonical HLS (src/dfxisp_accel.cpp gamma2() =
#   floor(sqrt(255*v)) = gamma 2.0) already uses a sqrt tone, so "R1's VST tone"
#   is barely new vs what ships; the real lever is resolution. To attribute the
#   gain correctly we run the full 2 x 3 factorial:
#
#        tone \ resolution |   full-res (HxW)   |   2x2 binned (H/2xW/2)
#        ------------------+--------------------+-----------------------
#        gamma2.5 (ver1)   |   F_g25            |   B_g25  (== old R0)
#        sqrt/gamma2.0     |   F_g20            |   B_g20  (== DEPLOYED tone)
#        VST/GAT (+offset) |   F_vst (== R1)    |   B_vst
#
#   Clean contrasts this enables:
#     binning effect at fixed tone  = F_g20 vs B_g20  (and F_vst vs B_vst)
#     tone effect at fixed res      = B_g25 vs B_g20 vs B_vst (deployed grid)
#     the deployed baseline itself  = B_g20 (bin + sqrt) -- the honest control
#     denoise effect                = B_vst vs B_vst_dn
#
# All arms reuse the shared HW-aligned baseline core (isp_pipeline_ver1 BLC/WB/
# gain, relaxed low-light BLC) and the primitives in rm_versions.py. Integer,
# HW-mappable. Does NOT edit canonical files.
#
# API: run_arm(bayer16, w, h, version) -> uint8 RGB. Versions listed in FACTORIAL
#      and VST_SWEEP below (also exposed via VERSION_NAMES).
# =============================================================================
from __future__ import annotations

import numpy as np

import isp_pipeline_ver1 as V
import rm_versions as RM

SHIFT = V.SHIFT
GNUM, GDEN = V.GAIN_LOWLIGHT_NUM, V.GAIN_LOWLIGHT_DEN     # 2.0x
BLK_LL = V.BLK_RAW_LOWLIGHT

# ---- tone LUTs -------------------------------------------------------------
_LUT_G25 = V._gamma_lut(2.5)          # ver1 low-light tone (exponent 0.40)
_LUT_G20 = V._gamma_lut(2.0)          # SW sqrt tone (np.round; ~deployed, differs +-1 LSB)


def _gamma2_floor_lut() -> np.ndarray:
    """BIT-EXACT deployed HLS low-light tone: gamma2()=floor(sqrt(255*v)),
    v in [0,255] (src/dfxisp_accel.cpp GAMMA2_LUT). Codex-review finding 1:
    V._gamma_lut(2.0) uses np.round and differs from this in 136/256 entries by
    +1 LSB, so use THIS for the honest 'deployed tone' control (B_g20f/F_g20f)."""
    v = np.arange(256, dtype=np.float64)
    return np.clip(np.floor(np.sqrt(255.0 * v)), 0, 255).astype(np.uint8)


_LUT_G20F = _gamma2_floor_lut()       # == deployed HLS gamma2(), bit-exact
def _lut_vst(offset: float) -> np.ndarray:
    return RM.vst_tone_lut(offset)    # GAT-form sqrt(v+offset), normalized


# ---- tone application (with vs without highlight soft-knee) -----------------
def _tone8_plain(rgb16):
    """BLC(relaxed) -> WB(Q8) -> gain2.0 -> hard >>SHIFT clip to 8-bit. Matches
    the deployed pipeline's pre-tone path (no soft-knee), so B_g20 is a faithful
    control for the shipped low-light RM tone stage."""
    return V._blc_wb_gain(rgb16, GNUM, GDEN, BLK_LL)


def _tone8_knee(rgb16):
    """Same, but with the R1 highlight soft-knee (isolates the knee's effect)."""
    return RM._blc_wb_gain_knee(rgb16, GNUM, GDEN, BLK_LL)


# ---- factorial cells -------------------------------------------------------
def _cell(bayer16, w, h, *, binned: bool, lut: np.ndarray, knee: bool, denoise: bool):
    rgb16 = (V._bin_demosaic_rggb16 if binned else V._demosaic_rggb16)(bayer16, w, h)
    rgb8 = (_tone8_knee if knee else _tone8_plain)(rgb16)
    if denoise:
        rgb8 = RM.edge_preserve_3x3(rgb8)
    return lut[rgb8]


_VST_DEFAULT = 4.0
_LUT_VST = _lut_vst(_VST_DEFAULT)

# 2x3 factorial (knee OFF so tone/resolution are the only varying factors; the
# knee is studied separately as F_vst_knee == R1). Denoise OFF here.
FACTORIAL = {
    "F_g25": dict(binned=False, lut=_LUT_G25, knee=False, denoise=False),
    "F_g20": dict(binned=False, lut=_LUT_G20, knee=False, denoise=False),
    "F_vst": dict(binned=False, lut=_LUT_VST, knee=False, denoise=False),
    "B_g25": dict(binned=True,  lut=_LUT_G25, knee=False, denoise=False),  # ~old R0 (no knee)
    "B_g20": dict(binned=True,  lut=_LUT_G20, knee=False, denoise=False),  # DEPLOYED tone (honest control)
    "B_vst": dict(binned=True,  lut=_LUT_VST, knee=False, denoise=False),
    # knee / denoise probes
    "F_vst_knee": dict(binned=False, lut=_LUT_VST, knee=True, denoise=False),  # == first-pass R1
    "B_vst_dn":   dict(binned=True,  lut=_LUT_VST, knee=False, denoise=True),  # == first-pass R2 (no knee)
    # bit-exact deployed-tone controls (Codex finding 1): floor(sqrt(255*v)) LUT
    "B_g20f": dict(binned=True,  lut=_LUT_G20F, knee=False, denoise=False),   # bit-exact DEPLOYED
    "F_g20f": dict(binned=False, lut=_LUT_G20F, knee=False, denoise=False),   # deployed tone, full-res
}

VERSION_NAMES = {
    "F_g25": "full-res + gamma2.5",
    "F_g20": "full-res + sqrt(gamma2.0)",
    "F_vst": "full-res + VST(offset4)",
    "B_g25": "binned + gamma2.5 (~old R0)",
    "B_g20": "binned + sqrt (DEPLOYED tone, honest control)",
    "B_vst": "binned + VST(offset4)",
    "F_vst_knee": "full-res + VST + soft-knee (== R1)",
    "B_vst_dn": "binned + VST + edge-denoise (== R2)",
    "B_g20f": "binned + floor-sqrt (BIT-EXACT deployed HLS tone)",
    "F_g20f": "full-res + floor-sqrt (deployed tone, binning removed)",
}

# VST read-offset sensitivity sweep (full-res, no knee): principle 4.2 says the
# offset flattens the read-noise floor; find where detection likes it.
VST_SWEEP_OFFSETS = [0.0, 1.0, 2.0, 4.0, 8.0, 16.0]
for _o in VST_SWEEP_OFFSETS:
    _name = f"F_vst_o{int(_o)}"
    FACTORIAL[_name] = dict(binned=False, lut=_lut_vst(_o), knee=False, denoise=False)
    VERSION_NAMES[_name] = f"full-res + VST(offset{int(_o)})"


def run_arm(bayer16, w, h, version):
    spec = FACTORIAL.get(version)
    if spec is None:
        raise ValueError(f"unknown fine RM version {version!r}; known: {sorted(FACTORIAL)}")
    return _cell(bayer16, w, h, **spec)


if __name__ == "__main__":
    w, h = 64, 48
    rng = np.random.default_rng(0)
    bayer = (rng.random((h, w)) * 4000).astype("<u2")
    for ver in FACTORIAL:
        out = run_arm(bayer, w, h, ver)
        print(f"{ver:12s} -> {out.shape} mean={out.mean():6.1f} "
              f"[{VERSION_NAMES[ver]}]")
