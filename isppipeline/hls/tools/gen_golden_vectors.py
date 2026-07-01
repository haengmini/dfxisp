#!/usr/bin/env python3
"""Generate deterministic DFXISP HLS C-sim golden vectors (reset 2026-07-01).

Bit-exact mirror of src/dfxisp_accel.cpp: shared baseline ISP core + mutually
exclusive tone RM slot. The tone RM slot wraps the shared baseline core.

  NORMAL:     raw -> RM_NORMAL_TONE(identity) -> baseline_core -> RGB32 (H x W)
  LOW_LIGHT:  raw -> 2x2 RAW binning -> baseline_core -> gain + gamma-4.0
                  -> RGB32 (H/2 x W/2, Policy A shape-changing)

baseline_core = demosaic(GRBG) + BLC + AWB + CCM(identity). No gain/gamma.
gain/gamma exist only in the low-light tone RM (no duplication).

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

# shared baseline-core params (mode independent)
BLC_OFFSET = 16
AWB_R, AWB_G, AWB_B = 286, 256, 307
# low-light tone RM params
LL_GAIN_NUM, LL_GAIN_DEN = 5, 4          # 1.25x exposure gain
GAMMA4_SCALE = 16581375                  # 255**3, gamma 4.0 via exact 4th root
DARK_RATIO_PCT = 40                      # AUTO -> LOW_LIGHT when dark pixels > 40%


def clamp_u8(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def raw12_to_u8(v: int) -> int:
    return (min(v, 4095) >> 4) & 0xFF


def pack_rgb(r: int, g: int, b: int) -> int:
    return (r << 16) | (g << 8) | b


def gamma4(v: int) -> int:
    # out = floor((255^3 * v)^(1/4)); isqrt(isqrt(n)) == floor(n^(1/4))
    return clamp_u8(isqrt(isqrt(GAMMA4_SCALE * v)))


def sample_clamped(raw: list[int], w: int, h: int, x: int, y: int) -> int:
    x = 0 if x < 0 else w - 1 if x >= w else x
    y = 0 if y < 0 else h - 1 if y >= h else y
    return raw[y * w + x]


def demosaic_grbg(raw: list[int], w: int, h: int, x: int, y: int) -> tuple[int, int, int]:
    win = [[sample_clamped(raw, w, h, x + wx - 1, y + wy - 1) for wx in range(3)] for wy in range(3)]
    ey, ex, c = (y & 1) == 0, (x & 1) == 0, win[1][1]
    if ey and ex:                    # G on R row
        gg = c; rr = (win[1][0] + win[1][2]) // 2; bb = (win[0][1] + win[2][1]) // 2
    elif ey and not ex:              # R
        rr = c; gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        bb = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    elif (not ey) and ex:            # B
        bb = c; gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        rr = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    else:                            # G on B row
        gg = c; rr = (win[0][1] + win[2][1]) // 2; bb = (win[1][0] + win[1][2]) // 2
    return raw12_to_u8(rr), raw12_to_u8(gg), raw12_to_u8(bb)


def baseline_core_pixel(raw: list[int], w: int, h: int, x: int, y: int) -> tuple[int, int, int]:
    """Shared baseline ISP core: demosaic + BLC + AWB + CCM(identity). No gain/gamma."""
    dr, dg, db = demosaic_grbg(raw, w, h, x, y)
    r = (clamp_u8(dr - BLC_OFFSET) * AWB_R) // 256
    g = (clamp_u8(dg - BLC_OFFSET) * AWB_G) // 256
    b = (clamp_u8(db - BLC_OFFSET) * AWB_B) // 256
    return clamp_u8(r), clamp_u8(g), clamp_u8(b)


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
        out = [pack_rgb(*baseline_core_pixel(raw, w, h, x, y)) for y in range(h) for x in range(w)]
        return selected, DFXISP_RM_NORMAL_TONE, w, h, out

    # LOW_LIGHT: 2x2 RAW binning -> baseline core -> gain + gamma-4.0 tone
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
            r, g, b = baseline_core_pixel(binned, bw, bh, x, y)
            r = gamma4(clamp_u8((r * LL_GAIN_NUM) // LL_GAIN_DEN))
            g = gamma4(clamp_u8((g * LL_GAIN_NUM) // LL_GAIN_DEN))
            b = gamma4(clamp_u8((b * LL_GAIN_NUM) // LL_GAIN_DEN))
            out.append(pack_rgb(r, g, b))
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


def const_raw(w: int, h: int, value: int) -> list[int]:
    return [value] * (w * h)


def golden_cases():
    # Scenario: bright normal x3 -> dark low-light x3 -> bright recovery x1,
    # plus a threshold-boundary AUTO frame and an odd-dimension low-light frame.
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
