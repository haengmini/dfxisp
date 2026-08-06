#!/usr/bin/env python3
"""Deterministic golden vectors for default_ISP (Vitis-Vision-ordered ISP arm).

Canonical status: **canonical golden** for src/default_isp.cpp -- a bit-exact
mirror, in the same role gen_golden_vectors.py plays for dfxisp_accel.cpp (see
isppipeline/hls/README.md "tools/ file status").

Stage order mirrors the AMD Vitis Vision L3 `isppipeline` example:
  blackLevelCorrection (Bayer) -> gaincontrol (Bayer) -> demosaicing
  -> AWB (RGB, per-frame, bypassable) -> colorcorrectionmatrix (RGB)
  -> quantization 12->8 -> gammacorrection -> packed RGB888.

stdlib only, integer only. All divisions operate on non-negative values so
Python's floor division and C++'s truncating division agree bit-for-bit.
"""
from __future__ import annotations

import argparse
from math import isqrt
from pathlib import Path

RAW12_MAX = 4095

BLC_LEVEL12 = 2 << 4          # 32
BLC_MUL_Q8 = 258              # round(256 * 4095 / (4095 - 32))

GAIN_R_Q8 = 286
GAIN_B_Q8 = 307

AWB_GAIN_MIN_Q8 = 64
AWB_GAIN_MAX_Q8 = 1024

CCM_Q8 = (
    (288, -24, -8),
    (-24, 296, -16),
    (-16, -32, 304),
)

AWB_OFF = 0
AWB_ON = 1

GAMMA2_LUT = [isqrt(255 * v) for v in range(256)]


def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


def bayer_gain_q8(x: int, y: int) -> int:
    even_y = (y & 1) == 0
    even_x = (x & 1) == 0
    if even_y and even_x:
        return GAIN_R_Q8          # R site
    if not even_y and not even_x:
        return GAIN_B_Q8          # B site
    return 256                    # G sites


def corrected_bayer(raw, width: int, height: int, x: int, y: int) -> int:
    """Stages (1) blackLevelCorrection + (2) gaincontrol, Bayer domain."""
    cx = 0 if x < 0 else (width - 1 if x >= width else x)
    cy = 0 if y < 0 else (height - 1 if y >= height else y)
    v = raw[cy * width + cx]
    v = v - BLC_LEVEL12 if v > BLC_LEVEL12 else 0
    v = clamp((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    v = clamp((v * bayer_gain_q8(cx, cy)) >> 8, 0, RAW12_MAX)
    return v


def demosaic_rggb12(raw, width: int, height: int, x: int, y: int):
    """Stage (3): RGGB bilinear demosaic on the corrected Bayer plane."""
    win = [[corrected_bayer(raw, width, height, x + wx - 1, y + wy - 1)
            for wx in range(3)] for wy in range(3)]
    even_y = (y & 1) == 0
    even_x = (x & 1) == 0
    c = win[1][1]
    if even_y and even_x:            # R site
        r = c
        g = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        b = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    elif even_y and not even_x:      # G on R row
        g = c
        r = (win[1][0] + win[1][2]) // 2
        b = (win[0][1] + win[2][1]) // 2
    elif not even_y and even_x:      # G on B row
        g = c
        r = (win[0][1] + win[2][1]) // 2
        b = (win[1][0] + win[1][2]) // 2
    else:                            # B site
        b = c
        g = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        r = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    return r, g, b


def awb_gains_q8(raw, width: int, height: int):
    """Stage (4) statistics: gray-world means over corrected Bayer sites."""
    sum_r = sum_g = sum_b = 0
    cnt_r = cnt_g = cnt_b = 0
    for y in range(height):
        for x in range(width):
            v = corrected_bayer(raw, width, height, x, y)
            even_y = (y & 1) == 0
            even_x = (x & 1) == 0
            if even_y and even_x:
                sum_r += v
                cnt_r += 1
            elif not even_y and not even_x:
                sum_b += v
                cnt_b += 1
            else:
                sum_g += v
                cnt_g += 1
    mean_r = sum_r // cnt_r if cnt_r else 0
    mean_g = sum_g // cnt_g if cnt_g else 0
    mean_b = sum_b // cnt_b if cnt_b else 0
    gain_r = clamp((mean_g * 256) // mean_r, AWB_GAIN_MIN_Q8, AWB_GAIN_MAX_Q8) \
        if (mean_r > 0 and mean_g > 0) else 256
    gain_b = clamp((mean_g * 256) // mean_b, AWB_GAIN_MIN_Q8, AWB_GAIN_MAX_Q8) \
        if (mean_b > 0 and mean_g > 0) else 256
    return gain_r, 256, gain_b


def ccm_channel(row: int, r12: int, g12: int, b12: int) -> int:
    """Stage (5): real 3x3 Q8 matrix; accumulator floored before the shift."""
    acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12
    if acc < 0:
        acc = 0
    return clamp(acc >> 8, 0, RAW12_MAX)


def quantize_gamma(v12: int) -> int:
    """Stages (6) quantization 12->8 and (7) gammacorrection."""
    return GAMMA2_LUT[clamp(v12, 0, RAW12_MAX) >> 4]


def default_isp(raw, width: int, height: int, awb_mode: int):
    awb_r, awb_g, awb_b = (256, 256, 256)
    if awb_mode == AWB_ON:
        awb_r, awb_g, awb_b = awb_gains_q8(raw, width, height)
    out = []
    for y in range(height):
        for x in range(width):
            r12, g12, b12 = demosaic_rggb12(raw, width, height, x, y)
            r12 = clamp((r12 * awb_r) >> 8, 0, RAW12_MAX)
            g12 = clamp((g12 * awb_g) >> 8, 0, RAW12_MAX)
            b12 = clamp((b12 * awb_b) >> 8, 0, RAW12_MAX)
            rc = quantize_gamma(ccm_channel(0, r12, g12, b12))
            gc = quantize_gamma(ccm_channel(1, r12, g12, b12))
            bc = quantize_gamma(ccm_channel(2, r12, g12, b12))
            out.append((rc << 16) | (gc << 8) | bc)
    return out


def make_cases():
    """Coverage: flat levels, gradient, color cast (exercises AWB+CCM),
    saturation, odd dimensions, and AWB off/on on identical input."""
    cases = []

    w = h = 8
    mid = [1600] * (w * h)
    cases.append(("flat_mid_awb_off", w, h, AWB_OFF, mid))
    cases.append(("flat_mid_awb_on", w, h, AWB_ON, mid))

    dark = [200] * (w * h)
    cases.append(("flat_dark_awb_on", w, h, AWB_ON, dark))

    grad = [((x + y) * 4095) // (w + h - 2) for y in range(h) for x in range(w)]
    cases.append(("gradient_awb_off", w, h, AWB_OFF, grad))
    cases.append(("gradient_awb_on", w, h, AWB_ON, grad))

    # Strong blue cast: B sites bright, R sites dim -> AWB must pull them back.
    cast = []
    for y in range(h):
        for x in range(w):
            even_y, even_x = (y & 1) == 0, (x & 1) == 0
            if even_y and even_x:
                cast.append(400)     # R
            elif not even_y and not even_x:
                cast.append(3200)    # B
            else:
                cast.append(1800)    # G
    cases.append(("blue_cast_awb_off", w, h, AWB_OFF, cast))
    cases.append(("blue_cast_awb_on", w, h, AWB_ON, cast))

    sat = [4095] * (w * h)
    cases.append(("saturated_awb_on", w, h, AWB_ON, sat))

    ow, oh = 5, 3
    odd = [((x * 7 + y * 13) * 97) % 4096 for y in range(oh) for x in range(ow)]
    cases.append(("odd_dims_awb_on", ow, oh, AWB_ON, odd))

    tiny = [123]
    cases.append(("one_pixel_awb_on", 1, 1, AWB_ON, tiny))

    return cases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="tests/default_isp_golden_vectors.csv")
    args = ap.parse_args()

    rows = ["case,in_w,in_h,awb_mode,out_w,out_h,kind,idx,val"]
    ncases = 0
    for name, w, h, awb, raw in make_cases():
        expected = default_isp(raw, w, h, awb)
        for i, v in enumerate(raw):
            rows.append(f"{name},{w},{h},{awb},{w},{h},raw,{i},{v}")
        for i, v in enumerate(expected):
            rows.append(f"{name},{w},{h},{awb},{w},{h},rgb,{i},0x{v:06X}")
        ncases += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n")
    print(f"wrote {out} ({len(rows)} rows including header; "
          f"{len(rows) - 1} data rows; {ncases} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
