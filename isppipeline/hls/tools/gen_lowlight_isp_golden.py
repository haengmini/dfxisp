#!/usr/bin/env python3
"""Deterministic golden vectors for lowlight_ISP (proposal low-light arm, v2).

Canonical status: **canonical golden** for src/lowlight_isp.cpp -- a bit-exact
mirror, the same role gen_golden_vectors.py plays for dfxisp_accel.cpp.

Pipeline (see src/lowlight_isp.md for the derivation of every stage):
  (1) binning               [RAW]    same-colour 2x2 average -> +6 dB (R/B, 4
                                     samples) and +9 dB (G, 8 samples). Placed
                                     BEFORE black level so the pedestal is
                                     subtracted once from the average instead of
                                     rectifying each noisy sample at zero.
  (2) blackLevelCorrection  [binned] subtract pedestal + restore range
  (3) gain                  [binned] exposure gain x per-channel WB, folded,
                                     upstream of quantisation (principle P3 4.3)
  (4) CCM                   [RGB12]  same matrix as default_isp (shared backbone)
  (5) GAT/Anscombe VST tone [12->8]  variance-stabilising LUT, replaces gamma2.0
  (6) edge-preserving denoise[VST]   sigma-clipped 3x3, constant threshold
  (7) pack RGB888

stdlib only, integer only; every division/shift operates on non-negative values
so Python floor division and C++ truncating division agree bit-for-bit.

Use --emit-lut to print the GAT table as a C array (the table committed in
src/lowlight_isp.cpp is produced by exactly this code path).
"""
from __future__ import annotations

import argparse
from math import isqrt
from pathlib import Path

RAW12_MAX = 4095

# --- (2) black level ---------------------------------------------------------
BLC_LEVEL12 = 2 << 4        # 32; deployed real-RAW recalibration (2026-07-20)
BLC_MUL_Q8 = 258            # round(256 * 4095 / (4095 - 32))

# --- (3) gain (binned domain) ---------------------------------------------------
EXPOSURE_GAIN_Q8 = 512      # 2.0x low-light exposure gain
# Binning already separated the channels, so WB is a plain per-channel gain
# here rather than the per-Bayer-site variant default_isp uses.
WB_R_Q8, WB_G_Q8, WB_B_Q8 = 286, 256, 307   # fixed WB (measured: not a lever)

# --- (4) CCM (shared with default_isp) ---------------------------------------
CCM_Q8 = (
    (288, -24, -8),
    (-24, 296, -16),
    (-16, -32, 304),
)

# --- (5) GAT / Anscombe VST --------------------------------------------------
# Generalised Anscombe Transform f(z) = (2/a) * sqrt(a*z + 3a^2/8 + b) for the
# Poisson-Gaussian sensor model sigma^2 = a*y + b. Normalised to [0,255] with
# f(0) subtracted, so the curve is LINEAR at the origin instead of sqrt's
# infinite slope -- that is the whole point: the read-noise floor is no longer
# over-amplified. With b = 0 the curve degenerates to the repo's existing
# gamma-2.0 (= exact Poisson VST), so this is a strict generalisation.
#
# MEASURED 2026-08-06 on the target sensor at the target condition: 16 Sony
# RX100 VII night frames (RAW-NOD originals, ISO 6400, 1/100 s) via
# tools/calibrate_noise_model.py. Fitted in the 14-bit sensor domain
# (a = 17.92 DN, b = 734 DN^2, R^2 = 0.94) and converted to this 12-bit
# pipeline domain by the shift8 scale s = 4080/15580: a = s*a14, b = s^2*b14.
# `b` carries real uncertainty (per-site fits span 6..85 here); its effect on
# the curve is +-7 LSB at the very bottom and negligible above mid-grey
# (src/lowlight_isp.md §4.1).
A_Q8 = 1202                 # a = 4.694 DN  (shot-noise slope), MEASURED
B_DN2 = 50                  # b = 50 DN^2   (sigma_read = 7.1 DN), MEASURED

# Soft-knee highlight roll-off is deliberately NOT implemented: the measured
# saturation rate is at most 2.13%, so no evidence justifies the extra shaping
# yet. It would be a change to this table only (src/lowlight_isp.md).

# --- (6) denoise -------------------------------------------------------------
# In the VST domain the noise std-dev is signal-independent by construction:
#   sigma_out = sigma_z * |d(out8)/dz| = 255*A_Q8 / (32*DENOM) = 4.56 LSB
# (verified empirically at signal levels 100..2500: 4.6 everywhere -- the
# stabilisation holds). So a single constant threshold is valid everywhere,
# which is what variance stabilisation buys. 11 ~= 2.4 sigma, deliberately
# conservative because the literature is consistent that over-denoising removes
# the high-frequency features detectors rely on.
# NOTE: this scales with the calibration. Under the pre-2026-08-06 estimated
# a/b, sigma_VST was 2.1 and the threshold was 5; the measured parameters more
# than doubled it, so keeping 5 would have run the sigma-clip at ~1.1 sigma and
# denoised almost nothing.
DENOISE_SIGMA = 11

# Binning modes (stage 1)
BIN_SUBSAMPLE = 0   # legacy: one sample per cell for R/B (0 dB), 2 for G (+3 dB)
BIN_SAMECOLOR = 1   # true same-colour 2x2 binning: +6 dB (R/B), +9 dB (G)


def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


def n256(z: int) -> int:
    """Scaled GAT argument: 256 * (a*z + 3a^2/8 + b), all integer."""
    return A_Q8 * z + (3 * A_Q8 * A_Q8) // (8 * 256) + B_DN2 * 256


GAT_N0 = isqrt(n256(0))
GAT_DENOM = isqrt(n256(RAW12_MAX)) - GAT_N0


def gat_lut() -> list[int]:
    return [clamp((255 * (isqrt(n256(z)) - GAT_N0)) // GAT_DENOM, 0, 255)
            for z in range(RAW12_MAX + 1)]


GAT_LUT = gat_lut()


def bin_dim(d: int) -> int:
    return max(1, d // 2)


def cell_sites(raw, width: int, height: int, cx: int, cy: int):
    """The four Bayer sites of cell (cx, cy): (R, G_topright, G_bottomleft, B)."""
    x0 = 2 * cx
    x1 = 2 * cx + 1 if 2 * cx + 1 < width else width - 1
    y0 = 2 * cy
    y1 = 2 * cy + 1 if 2 * cy + 1 < height else height - 1
    return (raw[y0 * width + x0], raw[y0 * width + x1],
            raw[y1 * width + x0], raw[y1 * width + x1])


def binned_raw(raw, width, height, bw, bh, bx, by, bin_mode):
    """Stage (1), RAW domain, no correction applied yet.

    SAMECOLOR: true same-colour 2x2 binning -- averages the R sites of a 2x2
    neighbourhood of Bayer cells (4 samples -> sigma/2 -> +6 dB), the B sites
    likewise, and all 8 G sites (+9 dB). Output stays H/2 x W/2 because the
    windows overlap; adjacent outputs are therefore correlated.
    SUBSAMPLE: the legacy path -- one R and one B sample from the cell itself
    (0 dB) and the cell's 2 G samples (+3 dB). Kept as the ablation baseline
    so binning's SNR contribution can be measured directly.
    """
    if bin_mode == BIN_SUBSAMPLE:
        r, g0, g1, b = cell_sites(raw, width, height, bx, by)
        return r, (g0 + g1) // 2, b
    sum_r = sum_g = sum_b = 0
    for dy in (0, 1):
        cy = clamp(by + dy, 0, bh - 1)
        for dx in (0, 1):
            cx = clamp(bx + dx, 0, bw - 1)
            r, g0, g1, b = cell_sites(raw, width, height, cx, cy)
            sum_r += r
            sum_g += g0 + g1
            sum_b += b
    return sum_r // 4, sum_g // 8, sum_b // 4


def correct_channel(v: int, wb_q8: int) -> int:
    """Stages (2) black level and (3) gain, applied ONCE to the binned value.

    Subtracting the pedestal after averaging is the unbiased order: clipping
    each noisy sample at zero first would rectify the noise and add a positive
    bias -- exactly the "noise floor lifted into visible grey" failure mode.
    """
    v = v - BLC_LEVEL12 if v > BLC_LEVEL12 else 0
    v = clamp((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8      # folded into one multiply
    return clamp((v * gain_q8) >> 8, 0, RAW12_MAX)


def binned_rgb(raw, width, height, bw, bh, bx, by, bin_mode):
    """Stages (1)-(3)."""
    r, g, b = binned_raw(raw, width, height, bw, bh, bx, by, bin_mode)
    return (correct_channel(r, WB_R_Q8),
            correct_channel(g, WB_G_Q8),
            correct_channel(b, WB_B_Q8))


def ccm_channel(row: int, r12: int, g12: int, b12: int) -> int:
    """Stage (4); accumulator floored before the shift for bit-exactness."""
    acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12
    if acc < 0:
        acc = 0
    return clamp(acc >> 8, 0, RAW12_MAX)


def sigma_clip(planes, bw: int, bh: int, x: int, y: int) -> int:
    """Stage (6): 3x3 sigma-clipped mean -- neighbours further than
    DENOISE_SIGMA from the centre are excluded, so edges survive."""
    center = planes[y][x]
    total = 0
    count = 0
    for dy in (-1, 0, 1):
        yy = clamp(y + dy, 0, bh - 1)
        for dx in (-1, 0, 1):
            xx = clamp(x + dx, 0, bw - 1)
            v = planes[yy][xx]
            if abs(v - center) <= DENOISE_SIGMA:
                total += v
                count += 1
    return total // count


def lowlight_isp(raw, width: int, height: int, denoise_on: int = 1,
                 bin_mode: int = BIN_SAMECOLOR):
    bw, bh = bin_dim(width), bin_dim(height)
    # stages (1)-(5): build the VST-domain planes
    pr = [[0] * bw for _ in range(bh)]
    pg = [[0] * bw for _ in range(bh)]
    pb = [[0] * bw for _ in range(bh)]
    for by in range(bh):
        for bx in range(bw):
            r12, g12, b12 = binned_rgb(raw, width, height, bw, bh, bx, by, bin_mode)
            rc = ccm_channel(0, r12, g12, b12)
            gc = ccm_channel(1, r12, g12, b12)
            bc = ccm_channel(2, r12, g12, b12)
            pr[by][bx] = GAT_LUT[rc]
            pg[by][bx] = GAT_LUT[gc]
            pb[by][bx] = GAT_LUT[bc]
    # stages (6)-(7)
    out = []
    for by in range(bh):
        for bx in range(bw):
            if denoise_on:
                r = sigma_clip(pr, bw, bh, bx, by)
                g = sigma_clip(pg, bw, bh, bx, by)
                b = sigma_clip(pb, bw, bh, bx, by)
            else:
                r, g, b = pr[by][bx], pg[by][bx], pb[by][bx]
            out.append((r << 16) | (g << 8) | b)
    return out, bw, bh


def make_cases():
    """Coverage: flat levels incl. the noise floor, gradient, a noisy dark
    patch (both binning modes -- the SNR ablation), a hard edge (denoise must
    preserve it), saturation, odd dimensions and the 1x1 degenerate case."""
    cases = []
    w = h = 8

    cases.append(("flat_mid", w, h, 1, BIN_SAMECOLOR, [1600] * (w * h)))
    cases.append(("flat_dark", w, h, 1, BIN_SAMECOLOR, [200] * (w * h)))
    cases.append(("flat_near_floor", w, h, 1, BIN_SAMECOLOR, [40] * (w * h)))

    grad = [((x + y) * 4095) // (w + h - 2) for y in range(h) for x in range(w)]
    cases.append(("gradient", w, h, 1, BIN_SAMECOLOR, grad))
    cases.append(("gradient_subsample", w, h, 1, BIN_SUBSAMPLE, grad))

    # Deterministic pseudo-noise on a dark background: denoise must smooth it.
    noisy = []
    seed = 12345
    for i in range(w * h):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        noisy.append(300 + (seed % 120))
    cases.append(("noisy_dark_denoise_on", w, h, 1, BIN_SAMECOLOR, noisy))
    cases.append(("noisy_dark_denoise_off", w, h, 0, BIN_SAMECOLOR, noisy))
    # Same frame through the legacy path: the SNR ablation pair.
    cases.append(("noisy_dark_subsample_dn_off", w, h, 0, BIN_SUBSAMPLE, noisy))

    # Hard vertical edge: dark left half, bright right half.
    edge = [(200 if x < w // 2 else 2600) for y in range(h) for x in range(w)]
    cases.append(("hard_edge", w, h, 1, BIN_SAMECOLOR, edge))

    cases.append(("saturated", w, h, 1, BIN_SAMECOLOR, [4095] * (w * h)))

    ow, oh = 5, 3
    odd = [((x * 7 + y * 13) * 97) % 4096 for y in range(oh) for x in range(ow)]
    cases.append(("odd_dims", ow, oh, 1, BIN_SAMECOLOR, odd))

    cases.append(("one_pixel", 1, 1, 1, BIN_SAMECOLOR, [900]))

    return cases


def emit_c_lut() -> str:
    lines = []
    for i in range(0, len(GAT_LUT), 16):
        chunk = ",".join(f"{v:3d}" for v in GAT_LUT[i:i + 16])
        lines.append("    " + chunk + ",")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="tests/lowlight_isp_golden_vectors.csv")
    ap.add_argument("--emit-lut", action="store_true",
                    help="print the GAT table as a C array body and exit")
    args = ap.parse_args()

    if args.emit_lut:
        print(emit_c_lut())
        return 0

    rows = ["case,in_w,in_h,denoise,bin_mode,out_w,out_h,kind,idx,val"]
    ncases = 0
    for name, w, h, dn, bm, raw in make_cases():
        expected, bw, bh = lowlight_isp(raw, w, h, dn, bm)
        for i, v in enumerate(raw):
            rows.append(f"{name},{w},{h},{dn},{bm},{bw},{bh},raw,{i},{v}")
        for i, v in enumerate(expected):
            rows.append(f"{name},{w},{h},{dn},{bm},{bw},{bh},rgb,{i},0x{v:06X}")
        ncases += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n")
    print(f"wrote {out} ({len(rows)} rows including header; "
          f"{len(rows) - 1} data rows; {ncases} cases)")
    print(f"GAT: n0={GAT_N0} denom={GAT_DENOM} "
          f"lut[0]={GAT_LUT[0]} lut[16]={GAT_LUT[16]} lut[32]={GAT_LUT[32]} "
          f"lut[4095]={GAT_LUT[4095]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
