#!/usr/bin/env python3
"""Generate deterministic DFXISP HLS C-sim golden vectors.

The model mirrors src/dfxisp_accel.cpp intentionally: GRBG Bayer layout,
clamped 3x3 sampling, integer demosaic, RAW12-to-RGB8 by >>4, and optional
low-light gain/lift.  It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


BASE_W = 4
BASE_H = 4
BASE_RAW = [
    220, 360, 260, 520,
    300, 460, 340, 620,
    420, 760, 480, 900,
    540, 860, 620, 1040,
]

DFXISP_MODE_NORMAL = 0
DFXISP_MODE_LOW_LIGHT = 1
DFXISP_MODE_AUTO = 2


def raw12_to_u8(v: int) -> int:
    return (min(v, 4095) >> 4) & 0xFF


def clamp_u8(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def pack_rgb(r: int, g: int, b: int) -> int:
    return (r << 16) | (g << 8) | b


def sample_clamped(raw: list[int], width: int, height: int, x: int, y: int) -> int:
    x = 0 if x < 0 else width - 1 if x >= width else x
    y = 0 if y < 0 else height - 1 if y >= height else y
    return raw[y * width + x]


def demosaic_pixel(raw: list[int], width: int, height: int, x: int, y: int) -> tuple[int, int, int]:
    win = [[sample_clamped(raw, width, height, x + wx - 1, y + wy - 1) for wx in range(3)] for wy in range(3)]
    even_y = (y & 1) == 0
    even_x = (x & 1) == 0
    c = win[1][1]

    if even_y and even_x:          # G on R row
        gg = c
        rr = (win[1][0] + win[1][2]) // 2
        bb = (win[0][1] + win[2][1]) // 2
    elif even_y and not even_x:    # R
        rr = c
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        bb = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    elif (not even_y) and even_x:  # B
        bb = c
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) // 4
        rr = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) // 4
    else:                          # G on B row
        gg = c
        rr = (win[0][1] + win[2][1]) // 2
        bb = (win[1][0] + win[1][2]) // 2

    return raw12_to_u8(rr), raw12_to_u8(gg), raw12_to_u8(bb)


def low_light(r: int, g: int, b: int) -> tuple[int, int, int]:
    return clamp_u8((r * 3) // 2 + 8), clamp_u8((g * 3) // 2 + 8), clamp_u8((b * 3) // 2 + 8)


def frame(raw: list[int], width: int, height: int, mode: int, threshold: int) -> list[int]:
    avg = sum(raw) // len(raw) if raw else 0
    use_low_light = mode == DFXISP_MODE_LOW_LIGHT or (mode == DFXISP_MODE_AUTO and avg < threshold)
    out: list[int] = []
    for y in range(height):
        for x in range(width):
            r, g, b = demosaic_pixel(raw, width, height, x, y)
            if use_low_light:
                r, g, b = low_light(r, g, b)
            out.append(pack_rgb(r, g, b))
    return out


def constant_raw(width: int, height: int, value: int) -> list[int]:
    return [value for _ in range(width * height)]


def grid_raw(width: int, height: int, levels: list[int], cell: int = 2, texture: int = 32) -> list[int]:
    """Generate a visible illumination grid, not a flat black/white patch.

    Each cell has a different base illumination.  A small deterministic texture is
    added inside cells so the demosaic window sees realistic local variation while
    the image still reads visually as a grid.
    """
    raw: list[int] = []
    cells_x = max((width + cell - 1) // cell, 1)
    for y in range(height):
        for x in range(width):
            cell_x = x // cell
            cell_y = y // cell
            base = levels[(cell_y * cells_x + cell_x) % len(levels)]
            ripple = ((x % cell) * texture + (y % cell) * (texture // 2))
            bayer_offset = 18 if ((x + y) & 1) else -10
            raw.append(max(0, min(4095, base + ripple + bayer_offset)))
    return raw


def threshold_grid_raw(width: int, height: int, threshold: int, delta: int) -> list[int]:
    """Visible grid whose integer average is threshold + delta."""
    offsets = [-96, -48, 0, 48, 96, 48, 0, -48]
    vals: list[int] = []
    for y in range(height):
        for x in range(width):
            vals.append(threshold + offsets[((x // 2) + 2 * (y // 2)) % len(offsets)])
    target_sum = (threshold + delta) * width * height
    diff = target_sum - sum(vals)
    vals[-1] += diff
    return [max(0, min(4095, v)) for v in vals]


def golden_cases() -> list[tuple[str, int, int, int, int, list[int]]]:
    # Scenario order: normal x3 -> low-light x3 -> normal x1.
    # These are synthetic illumination-grid frames; 8x8/16x16 are test-frame
    # resolutions, not filter or binning sizes.
    return [
        ("seq1_bright_normal_grid_8x8", 8, 8, DFXISP_MODE_NORMAL, 512, grid_raw(8, 8, [1800, 2300, 2800, 3300, 3800, 3050, 2450, 3600])),
        ("seq2_bright_normal_grid_8x8", 8, 8, DFXISP_MODE_NORMAL, 512, grid_raw(8, 8, [2100, 2550, 3000, 3450, 3900, 3250, 2700, 3650], texture=28)),
        ("seq3_mixed_normal_grid_16x16", 16, 16, DFXISP_MODE_NORMAL, 1400, grid_raw(16, 16, [1450, 1800, 2200, 2600, 3050, 3400, 3750, 2450], cell=4, texture=36)),
        ("seq4_dark_lowlight_grid_8x8", 8, 8, DFXISP_MODE_LOW_LIGHT, 512, grid_raw(8, 8, [180, 260, 380, 520, 700, 920, 620, 300], texture=24)),
        ("seq5_dark_lowlight_grid_8x8", 8, 8, DFXISP_MODE_LOW_LIGHT, 512, grid_raw(8, 8, [240, 360, 500, 680, 860, 1040, 720, 420], texture=26)),
        ("seq6_mixed_dark_lowlight_grid_16x16", 16, 16, DFXISP_MODE_LOW_LIGHT, 1400, grid_raw(16, 16, [220, 420, 760, 1180, 540, 980, 1320, 360], cell=4, texture=38)),
        ("seq7_threshold_boundary_normal_grid_8x8", 8, 8, DFXISP_MODE_AUTO, 512, threshold_grid_raw(8, 8, 512, 0)),
    ]


def write_csv(path: Path) -> int:
    rows = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case", "width", "height", "mode", "threshold", "index", "x", "y", "raw", "expected_rgb_hex"])
        for name, width, height, mode, threshold, raw in golden_cases():
            assert len(raw) == width * height
            rgb = frame(raw, width, height, mode, threshold)
            for idx, (raw_value, rgb_value) in enumerate(zip(raw, rgb)):
                x = idx % width
                y = idx // width
                writer.writerow([name, width, height, mode, threshold, idx, x, y, raw_value, f"0x{rgb_value:06x}"])
                rows += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/golden_vectors.csv", help="output CSV path (default: tests/golden_vectors.csv)")
    args = parser.parse_args()
    out = Path(args.out)
    rows = write_csv(out)
    print(f"wrote {out} ({rows + 1} rows including header; {rows} data rows; {len(golden_cases())} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
