#!/usr/bin/env python3
"""Convert NormalISP's packed 0x00RRGGBB uint32 output (from
board_test/normalisp_uio_test.py) into viewable PNGs.

Each input file is named ..._<W>x<H>_rgb888.bin (run_all_bayer.py derives
this from the source Bayer file's own _<W>x<H>.bin suffix, since every
image downsamples to a different actual size). Width/height are parsed
from the filename; pass --width/--height to override for files that don't
follow this convention.

Usage: python3 rgb888_to_png.py IN_DIR OUT_DIR [--width W --height H]
Converts every *_rgb888.bin found (recursively) under IN_DIR.
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

DIMS_RE = re.compile(r'_(\d+)x(\d+)_rgb888\.bin$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    args = ap.parse_args()

    n = 0
    for root, _, files in os.walk(args.in_dir):
        for fn in files:
            if not fn.endswith("_rgb888.bin"):
                continue
            in_path = os.path.join(root, fn)
            rel = os.path.relpath(in_path, args.in_dir)

            if args.width and args.height:
                width, height = args.width, args.height
            else:
                m = DIMS_RE.search(fn)
                if not m:
                    print(f"SKIP {rel}: can't parse WxH from filename "
                          f"(pass --width/--height to override)")
                    continue
                width, height = int(m.group(1)), int(m.group(2))

            out_path = os.path.join(args.out_dir, os.path.splitext(rel)[0] + ".png")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            words = np.fromfile(in_path, dtype="<u4")
            expected = width * height
            if words.size != expected:
                print(f"SKIP {rel}: {words.size} pixels, expected {expected} "
                      f"for {width}x{height}")
                continue

            r = ((words >> 16) & 0xFF).astype(np.uint8)
            g = ((words >> 8) & 0xFF).astype(np.uint8)
            b = (words & 0xFF).astype(np.uint8)
            rgb = np.stack([r, g, b], axis=-1).reshape(height, width, 3)

            Image.fromarray(rgb, mode="RGB").save(out_path)
            print(f"{rel} ({width}x{height}) -> {out_path}")
            n += 1

    print(f"\n{n} PNG(s) written to {args.out_dir}")


if __name__ == "__main__":
    main()
