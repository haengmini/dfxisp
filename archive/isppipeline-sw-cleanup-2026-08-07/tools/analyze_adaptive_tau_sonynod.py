#!/usr/bin/env python3
"""analyze_adaptive_tau_sonynod.py -- ISO-stratified fixed-vs-adaptive tau
recall check on the SonyNOD (RAW-NOD Sony RX100 VII) test split.

Answers checker-strengthening-2026-07-10.md item #1's still-PENDING
real-data validation: does using checker_adaptive_tau.py's per-frame,
ISO-adaptive threshold change the checker's low-light recall relative to
the current FIXED dark_pixel_threshold, across the real ISO range present
in this dataset?

Caveat (read before trusting the numbers): RAW-NOD's Sony subset is 100%
evening/night captures (see results/realraw-sonynod-benchmark-2026-07-06.md
Sec.7) -- there is no "should stay NORMAL" ground truth in this dataset, so
this script can only measure RECALL (did we correctly call it LOW_LIGHT),
never false-trigger rate. The false-trigger side needs PASCALRAW once it
finishes downloading.

Usage (run from isppipeline/hls/tools/):
  python3 analyze_adaptive_tau_sonynod.py \\
    --ann <RAW-NOD>/annotations/Sony/raw_str_labeled_new_Sony_RX100m7_test.json \\
    --arw-dir <dir containing the .ARW files, e.g. .../Sony-ARW> \\
    [--exiftool /usr/bin/exiftool] [--limit N] [--out results.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import rawpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checker_adaptive_tau import SensorParams, tau_for_frame, extract_exif  # noqa: E402

CROP_TOP, CROP_LEFT = 12, 12
CROP_W, CROP_H = 5472, 3648
BLACK_LEVEL = 800  # build_sonynod_dataset.py -- measured 2026-07-06
WHITE_LEVEL = 16380
DARK_RATIO_PCT = 80  # deployed C0 constant, src/dfxisp_accel.cpp:94
C1_DARK16_THR = 0.62  # recommended-but-undeployed C1, checker-status-2026-07-10.md
# NOTE: also reused below as the judgement cutoff for the *adaptive* dark
# ratio (adaptive_lowlight). That's a known-open methodological gap -- see
# checker_adaptive_tau.py's "KNOWN OPEN ISSUE" docstring and
# results/checker-adaptive-tau-realdata-2026-07-13.md Sec.4.

ISO_BINS = [0, 400, 800, 1600, 3200, 6400, 12800, 1_000_000]


def dark_ratio_at(v8: np.ndarray, thr8: int) -> float:
    """Fraction of 8-bit pixels strictly below thr8 (same definition as
    checker_stat_sweep.hist_stats's dark{T})."""
    return float((v8 < thr8).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ann", type=Path, required=True)
    ap.add_argument("--arw-dir", type=Path, required=True)
    ap.add_argument("--exiftool", default="exiftool")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path,
                     default=Path("adaptive_tau_sonynod_results.csv"))
    args = ap.parse_args()

    coco = json.loads(args.ann.read_text())
    images = sorted(coco["images"], key=lambda im: im["id"])
    if args.limit:
        images = images[: args.limit]

    sp = SensorParams()
    rows = []
    for i, im in enumerate(images):
        arw_path = args.arw_dir / im["file_name"]
        if not arw_path.exists():
            print(f"skip (missing): {im['file_name']}", file=sys.stderr)
            continue
        exif = extract_exif(arw_path, args.exiftool)
        with rawpy.imread(str(arw_path)) as raw:
            bayer = raw.raw_image_visible.astype(np.float64)
            bayer = bayer[CROP_TOP:CROP_TOP + CROP_H, CROP_LEFT:CROP_LEFT + CROP_W]
            lin = np.clip((bayer - BLACK_LEVEL) / (WHITE_LEVEL - BLACK_LEVEL), 0.0, 1.0)
            v8 = np.round(lin * 255).astype(np.uint8)

        d50 = dark_ratio_at(v8, 50)  # C0-domain proxy
        d16 = dark_ratio_at(v8, 16)  # C1

        frame = tau_for_frame(exif, BLACK_LEVEL, WHITE_LEVEL, sp, k=5.0)
        thr8_adaptive = frame["register"] >> 8
        d_adaptive = dark_ratio_at(v8, thr8_adaptive)

        rows.append({
            "stem": Path(im["file_name"]).stem,
            "iso": exif.get("iso"),
            "exposure_s": exif.get("exposure_s"),
            "dark50": d50,
            "dark16": d16,
            "adaptive_thr8": thr8_adaptive,
            "dark_adaptive": d_adaptive,
            "c0_lowlight": d50 * 100 > DARK_RATIO_PCT,
            "c1_lowlight": d16 > C1_DARK16_THR,
            "adaptive_lowlight": d_adaptive > C1_DARK16_THR,
        })
        if (i + 1) % 20 == 0:
            print(f"...{i + 1}/{len(images)}", file=sys.stderr)

    if not rows:
        print("no frames processed -- check --arw-dir path", file=sys.stderr)
        return 1

    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {args.out} ({len(rows)} frames)\n")
    print(f"{'ISO bucket':<16}{'n':>5}{'C0 recall':>12}{'C1 recall':>12}"
          f"{'adaptive recall':>18}")
    for lo, hi in zip(ISO_BINS[:-1], ISO_BINS[1:]):
        bucket = [r for r in rows if r["iso"] is not None and lo <= r["iso"] < hi]
        if not bucket:
            continue
        n = len(bucket)
        r_c0 = sum(r["c0_lowlight"] for r in bucket) / n
        r_c1 = sum(r["c1_lowlight"] for r in bucket) / n
        r_ad = sum(r["adaptive_lowlight"] for r in bucket) / n
        print(f"[{lo:>5},{hi:>6}){n:>5}{r_c0:>12.3f}{r_c1:>12.3f}{r_ad:>18.3f}")

    n_no_iso = sum(1 for r in rows if r["iso"] is None)
    if n_no_iso:
        print(f"\n{n_no_iso}/{len(rows)} frames had no ISO from exiftool -- "
              f"check exiftool is installed and can read Sony .ARW ISO tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
