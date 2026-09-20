#!/usr/bin/env python3
"""NEF/ARW -> flat 12-bit RGGB Bayer .bin for NormalISP/LowlightISP boards,
downsampled to fit a target box while preserving the FULL field of view.

NormalISP's raw_bayer port expects a plain uint16 array (row-major, W*H
elements), 12-bit range, RGGB phase starting at (0,0)=R. This tool extracts
that from a camera RAW file via rawpy/libraw, then downsamples in the Bayer
domain by splitting into the 4 same-color planes (R, Gr, Gb, B), block-
averaging each plane independently by an integer factor K, and
re-interleaving -- this keeps the RGGB phase exact (no aliasing across
colors) and reduces sensor noise as a side effect, unlike a plain crop
(which only shows a small zoomed-in patch) or naive pixel-skipping (which
would corrupt the Bayer pattern for any odd stride).

K is chosen automatically as the smallest integer that makes the output fit
within --max-width x --max-height, so the whole frame stays visible; actual
output size is usually a bit smaller than the box and depends on the
sensor's native resolution, so it's reported and embedded in the filename
rather than fixed. Optionally rescales 14-bit sensors (e.g. Sony ARW,
black_level>0) down to 12-bit before downsampling.

Usage:
    python3 raw_to_bayer_bin.py IN.nef OUT.bin [--max-width 640] [--max-height 480]
                                 [--no-rescale]
Output filename gets the actual WxH inserted before its extension, e.g.
OUT.bin -> OUT_603x401.bin (skip this by passing an OUT path with no
extension change desired -- see --no-rename).
"""
import argparse
import os
import sys

import numpy as np
import rawpy


def block_average_plane(plane, k):
    """Block-average a single-color plane by integer factor k (both axes)."""
    h, w = plane.shape
    oh, ow = h // k, w // k
    if oh == 0 or ow == 0:
        sys.exit(f"downsample factor {k} too large for plane {w}x{h}")
    trimmed = plane[:oh * k, :ow * k].astype(np.float64)
    return trimmed.reshape(oh, k, ow, k).mean(axis=(1, 3))


def downsample_bayer(img, k):
    """Downsample an RGGB Bayer array by k, preserving the pattern."""
    h, w = img.shape
    planes = {}
    for dy in (0, 1):
        for dx in (0, 1):
            planes[(dy, dx)] = block_average_plane(img[dy::2, dx::2], k)
    oh, ow = planes[(0, 0)].shape
    out = np.empty((oh * 2, ow * 2), dtype=np.float64)
    for (dy, dx), p in planes.items():
        out[dy::2, dx::2] = p
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--max-width", type=int, default=640)
    ap.add_argument("--max-height", type=int, default=480)
    ap.add_argument("--no-rescale", action="store_true",
                     help="skip 14-bit->12-bit rescale even if white_level>4095")
    ap.add_argument("--no-rename", action="store_true",
                     help="write exactly to outfile instead of inserting WxH")
    args = ap.parse_args()

    with rawpy.imread(args.infile) as raw:
        pattern = raw.raw_pattern
        desc = raw.color_desc.decode()
        top_left, top_right = desc[pattern[0, 0]], desc[pattern[0, 1]]
        bot_left, bot_right = desc[pattern[1, 0]], desc[pattern[1, 1]]
        pattern_str = f"{top_left}{top_right}/{bot_left}{bot_right}"
        if pattern_str != "RG/GB":
            sys.exit(f"unexpected Bayer pattern {pattern_str} (need RG/GB) "
                      f"in {args.infile} -- NormalISP assumes RGGB from (0,0)")

        img = raw.raw_image_visible  # crops optical-black margins, phase-safe (even margins)
        h, w = img.shape
        black = raw.black_level_per_channel[0]
        white = raw.white_level

        k = max(1, int(np.ceil(max(h / args.max_height, w / args.max_width))))

        data = img.astype(np.int32)
        if not args.no_rescale and white > 4095:
            data = data - black
            data = np.clip(data, 0, white - black)
            data = (data.astype(np.float64) * (4095.0 / (white - black)))
        else:
            data = data.astype(np.float64)

        down = downsample_bayer(data, k)
        down = np.clip(np.round(down), 0, 4095).astype(np.uint16)
        out_h, out_w = down.shape

        outfile = args.outfile
        if not args.no_rename:
            base, ext = os.path.splitext(args.outfile)
            outfile = f"{base}_{out_w}x{out_h}{ext}"

        down.tofile(outfile)
        print(f"{args.infile}: pattern={pattern_str} raw_visible={w}x{h} "
              f"black={black} white={white} downsample_k={k} -> {outfile} "
              f"({out_w}x{out_h}, full FOV, "
              f"rescaled={'no' if args.no_rescale or white <= 4095 else 'yes'})")


if __name__ == "__main__":
    main()
