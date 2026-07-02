#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/gen_golden_vectors.py
# Updated: 2026-07-02 12:40 KST
# Function: deterministic DFXISP HLS C-sim golden vectors (bit-exact mirror of
#           src/dfxisp_accel.cpp)
# Goal   : Reflect ver1 RAW-domain-first ordering into HW/C-sim golden:
#             baseline core = demosaic -> BLC -> WB -> CCM (12-bit, no gain/gamma)
#             RM_NORMAL_TONE    = gain 1.25x + gamma2.0
#             RM_LOW_LIGHT_TONE = 2x2 bin(front) + gain 2.0x + gamma2.0 (back)
#           Corrections in 12-bit before final >>4; gamma via integer sqrt (gamma
#           2.0) for bit-exactness. Bayer pattern RGGB (unified with SW dataset).
# =============================================================================
"""Generate deterministic DFXISP HLS C-sim golden vectors.

Bit-exact mirror of src/dfxisp_accel.cpp: shared baseline ISP core + mutually
exclusive tone RM slot. tone RM wraps the core; gain/gamma live only in the tone
RMs (no duplication).

  NORMAL:     raw -> baseline_core12 -> RM_NORMAL_TONE(gain 1.25x + gamma2)  (H x W)
  LOW_LIGHT:  raw -> 2x2 RAW bin -> baseline_core12 -> RM_LOW_LIGHT_TONE
                     (gain 2.0x + gamma2)                        (H/2 x W/2, Policy A)

baseline_core12 = demosaic(RGGB) + BLC + WB + CCM(identity), all in 12-bit. No gain/gamma.

Standard library only. CSV carries per-case metadata (mode, selected RM, output
shape) plus input RAW rows (kind=raw) and expected output rows (kind=rgb).
"""

from __future__ import annotations

import argparse
import csv
from math import isqrt
from pathlib import Path

DFXISP_MODE_NORMAL = 0
DFXISP_MODE_LOW_LIGHT = 1
DFXISP_MODE_AUTO = 2

DFXISP_RM_NORMAL_TONE = 0
DFXISP_RM_LOW_LIGHT_TONE = 1

# shared baseline-core params (mode independent, 12-bit RAW domain)
BLC_OFFSET12 = 16 << 4          # black level 16 (8-bit) -> 256 (12-bit)
RAW12_MAX = 4095
AWB_R, AWB_G, AWB_B = 286, 256, 307
# tone RM params
GAIN_NORMAL_NUM, GAIN_NORMAL_DEN = 5, 4        # normal 1.25x
GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN = 2, 1    # low-light 2.0x
DARK_RATIO_PCT = 40                            # AUTO -> LOW_LIGHT when dark pixels > 40%


def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def clamp_u8(v: int) -> int:
    return clamp(v, 0, 255)


def pack_rgb(r: int, g: int, b: int) -> int:
    return (r << 16) | (g << 8) | b


def gamma2(v: int) -> int:
    # gamma 2.0: out = floor(sqrt(255 * v)); isqrt is exact & matches C++ isqrt_u64
    return clamp_u8(isqrt(255 * v))


def sample_clamped(raw: list[int], w: int, h: int, x: int, y: int) -> int:
    x = 0 if x < 0 else w - 1 if x >= w else x
    y = 0 if y < 0 else h - 1 if y >= h else y
    return raw[y * w + x]


def demosaic_rggb12(raw: list[int], w: int, h: int, x: int, y: int) -> tuple[int, int, int]:
    # RGGB Bayer: (0,0)=R (0,1)=G (1,0)=G (1,1)=B ; keep 12-bit (no >>4 here)
    win = [[sample_clamped(raw, w, h, x + wx - 1, y + wy - 1) for wx in range(3)] for wy in range(3)]
    ey, ex, c = (y & 1) == 0, (x & 1) == 0, win[1][1]
    if ey and ex:                    # R
        rr = c; gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        bb = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    elif ey and not ex:              # G on R row (R horizontal, B vertical)
        gg = c; rr = (win[1][0] + win[1][2]) // 2; bb = (win[0][1] + win[2][1]) // 2
    elif (not ey) and ex:            # G on B row (R vertical, B horizontal)
        gg = c; rr = (win[0][1] + win[2][1]) // 2; bb = (win[1][0] + win[1][2]) // 2
    else:                            # B
        bb = c; gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        rr = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    return min(rr, RAW12_MAX), min(gg, RAW12_MAX), min(bb, RAW12_MAX)


def baseline_core12(raw: list[int], w: int, h: int, x: int, y: int) -> tuple[int, int, int]:
    """Shared baseline ISP core (ver1): demosaic + BLC + WB + CCM in 12-bit. No gain/gamma."""
    dr, dg, db = demosaic_rggb12(raw, w, h, x, y)
    dr = clamp(dr - BLC_OFFSET12, 0, RAW12_MAX)          # BLC (subtract first)
    dg = clamp(dg - BLC_OFFSET12, 0, RAW12_MAX)
    db = clamp(db - BLC_OFFSET12, 0, RAW12_MAX)
    r = clamp(dr * AWB_R // 256, 0, RAW12_MAX)           # WB per channel (Q8)
    g = clamp(dg * AWB_G // 256, 0, RAW12_MAX)
    b = clamp(db * AWB_B // 256, 0, RAW12_MAX)           # CCM identity
    return r, g, b


def tone(v12: int, gnum: int, gden: int) -> int:
    """tone RM: exposure gain (12-bit) -> >>4 to 8-bit -> gamma 2.0."""
    gained = clamp(v12 * gnum // gden, 0, RAW12_MAX)
    return gamma2(clamp_u8(gained >> 4))


def bin_dim(d: int) -> int:
    return max(1, d // 2)


def checker_select_mode(raw: list[int], w: int, h: int, mode: int, dark_threshold: int) -> int:
    if mode == DFXISP_MODE_NORMAL:
        return DFXISP_MODE_NORMAL
    if mode == DFXISP_MODE_LOW_LIGHT:
        return DFXISP_MODE_LOW_LIGHT
    dark = sum(1 for v in raw if v < dark_threshold)
    return DFXISP_MODE_LOW_LIGHT if dark * 100 > DARK_RATIO_PCT * (w * h) else DFXISP_MODE_NORMAL


def run_frame(raw: list[int], w: int, h: int, mode: int, dark_threshold: int):
    """Return (selected_mode, selected_rm, out_w, out_h, packed_rgb_list)."""
    selected = checker_select_mode(raw, w, h, mode, dark_threshold)

    if selected == DFXISP_MODE_NORMAL:
        out = []
        for y in range(h):
            for x in range(w):
                r12, g12, b12 = baseline_core12(raw, w, h, x, y)     # core (no gain/gamma)
                out.append(pack_rgb(tone(r12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN),
                                    tone(g12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN),
                                    tone(b12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN)))
        return selected, DFXISP_RM_NORMAL_TONE, w, h, out

    # LOW_LIGHT: 2x2 RAW binning (front) -> baseline core -> gain 2.0x + gamma (back)
    bw, bh = bin_dim(w), bin_dim(h)
    binned = [0] * (bw * bh)
    for by in range(bh):
        for bx in range(bw):
            x0, x1 = 2 * bx, min(2 * bx + 1, w - 1)
            y0, y1 = 2 * by, min(2 * by + 1, h - 1)
            s = raw[y0 * w + x0] + raw[y0 * w + x1] + raw[y1 * w + x0] + raw[y1 * w + x1]
            binned[by * bw + bx] = s // 4
    out = []
    for y in range(bh):
        for x in range(bw):
            r12, g12, b12 = baseline_core12(binned, bw, bh, x, y)
            out.append(pack_rgb(tone(r12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN),
                                tone(g12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN),
                                tone(b12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN)))
    return selected, DFXISP_RM_LOW_LIGHT_TONE, bw, bh, out


# --------------------------------------------------------------------------
# Deterministic fixtures (RESEARCH.md §10.1 / §12 Task 3).
# --------------------------------------------------------------------------
def grid_raw(w: int, h: int, levels: list[int], cell: int = 2, texture: int = 32) -> list[int]:
    raw: list[int] = []
    cells_x = max((w + cell - 1) // cell, 1)
    for y in range(h):
        for x in range(w):
            base = levels[((y // cell) * cells_x + (x // cell)) % len(levels)]
            ripple = (x % cell) * texture + (y % cell) * (texture // 2)
            bayer_offset = 18 if ((x + y) & 1) else -10
            raw.append(max(0, min(4095, base + ripple + bayer_offset)))
    return raw


def golden_cases():
    # bright normal x3 -> dark low-light x3 -> bright recovery x1, + threshold + odd-dim.
    return [
        ("seq1_bright_normal_grid_8x8", 8, 8, DFXISP_MODE_NORMAL, 512,
         grid_raw(8, 8, [1800, 2300, 2800, 3300, 3800, 3050, 2450, 3600])),
        ("seq2_bright_normal_grid_8x8", 8, 8, DFXISP_MODE_NORMAL, 512,
         grid_raw(8, 8, [2100, 2550, 3000, 3450, 3900, 3250, 2700, 3650], texture=28)),
        ("seq3_mixed_normal_grid_16x16", 16, 16, DFXISP_MODE_NORMAL, 1400,
         grid_raw(16, 16, [1450, 1800, 2200, 2600, 3050, 3400, 3750, 2450], cell=4, texture=36)),
        ("seq4_dark_lowlight_grid_8x8", 8, 8, DFXISP_MODE_LOW_LIGHT, 512,
         grid_raw(8, 8, [180, 260, 380, 520, 700, 920, 620, 300], texture=24)),
        ("seq5_dark_lowlight_grid_8x8", 8, 8, DFXISP_MODE_LOW_LIGHT, 512,
         grid_raw(8, 8, [240, 360, 500, 680, 860, 1040, 720, 420], texture=26)),
        ("seq6_mixed_dark_lowlight_grid_16x16", 16, 16, DFXISP_MODE_LOW_LIGHT, 1400,
         grid_raw(16, 16, [220, 420, 760, 1180, 540, 980, 1320, 360], cell=4, texture=38)),
        ("seq7_bright_recovery_auto_8x8", 8, 8, DFXISP_MODE_AUTO, 512,
         grid_raw(8, 8, [1800, 2300, 2800, 3300, 3800, 3050, 2450, 3600])),
        ("auto_dark_trigger_8x8", 8, 8, DFXISP_MODE_AUTO, 512,
         grid_raw(8, 8, [120, 180, 240, 300, 360, 300, 240, 180], texture=16)),
        ("odd_dimension_lowlight_7x5", 7, 5, DFXISP_MODE_LOW_LIGHT, 512,
         grid_raw(7, 5, [200, 320, 480, 660, 900, 620, 380, 260], texture=22)),
    ]


def write_csv(path: Path) -> int:
    rows = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case", "in_w", "in_h", "mode", "threshold",
                         "out_w", "out_h", "sel_mode", "sel_rm", "kind", "idx", "val"])
        for name, w, h, mode, threshold, raw in golden_cases():
            assert len(raw) == w * h, name
            sel_mode, sel_rm, ow, oh, rgb = run_frame(raw, w, h, mode, threshold)
            meta = [name, w, h, mode, threshold, ow, oh, sel_mode, sel_rm]
            for idx, v in enumerate(raw):
                writer.writerow(meta + ["raw", idx, v]); rows += 1
            for idx, v in enumerate(rgb):
                writer.writerow(meta + ["rgb", idx, f"0x{v:06x}"]); rows += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/golden_vectors.csv",
                        help="output CSV path (default: tests/golden_vectors.csv)")
    args = parser.parse_args()
    out = Path(args.out)
    rows = write_csv(out)
    print(f"wrote {out} ({rows + 1} rows including header; {rows} data rows; "
          f"{len(golden_cases())} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
