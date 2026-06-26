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


W = 4
H = 4
RAW = [
    64, 128, 80, 160,
    96, 64, 120, 80,
    70, 140, 90, 180,
    100, 75, 130, 95,
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


def write_csv(path: Path) -> None:
    cases = [
        ("normal_4x4", DFXISP_MODE_NORMAL, 90),
        ("lowlight_4x4", DFXISP_MODE_LOW_LIGHT, 90),
        ("auto_lowlight_4x4", DFXISP_MODE_AUTO, 120),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case", "width", "height", "mode", "threshold", "index", "x", "y", "raw", "expected_rgb_hex"])
        for name, mode, threshold in cases:
            rgb = frame(RAW, W, H, mode, threshold)
            for idx, (raw_value, rgb_value) in enumerate(zip(RAW, rgb)):
                x = idx % W
                y = idx // W
                writer.writerow([name, W, H, mode, threshold, idx, x, y, raw_value, f"0x{rgb_value:06x}"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/golden_vectors.csv", help="output CSV path (default: tests/golden_vectors.csv)")
    args = parser.parse_args()
    out = Path(args.out)
    write_csv(out)
    rows = 1 + 3 * W * H
    print(f"wrote {out} ({rows} rows including header)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
