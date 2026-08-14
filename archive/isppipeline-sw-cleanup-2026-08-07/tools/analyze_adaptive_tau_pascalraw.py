#!/usr/bin/env python3
"""analyze_adaptive_tau_pascalraw.py -- false-trigger rate check on PASCALRAW
(100% daylight) using checker_adaptive_tau.py's C0/C1/adaptive dark-ratio
logic, run directly against the already-adapted raw_bin/*.bin shift8 files
(no rawpy re-decode needed -- pascalraw_adapter.py already did that once,
2026-07-14, converted=4259 skipped=0 no_gt=0).

Complements analyze_adaptive_tau_sonynod.py: SonyNOD is 100% low-light so it
can only measure RECALL (results/checker-adaptive-tau-realdata-2026-07-13.md).
PASCALRAW is 100% daylight (illum_label=0 for every frame by dataset
construction, see pascalraw_adapter.py) so every C0/C1/adaptive LOW_LIGHT
verdict here is, by definition, a FALSE TRIGGER -- the measurement
results/pascalraw-adapter-2026-07-13.md SS1 and checker-status-2026-07-10.md
SS4 both flagged as the missing half of the checker validation.

frames_meta.csv's iso/exposure_s columns came back null for all 4259 frames:
the 2026-07-14 conversion ran without the exiftool CLI binary installed on
this machine (confirmed missing, 2026-07-15). Fixed going forward via an
exifread (pure-python) fallback added to aodraw_adapter.py:extract_exif the
same day. Re-running the ~2.5h/221GB full adapter just to refresh two
metadata columns would be wasteful, so this script re-derives EXIF directly
from the original .NEF files (path from meta.json's raw_dir) via that same
now-fixed extract_exif -- fast (EXIF-only read, no raw decode), independent
of raw_bin/.

PASCALRAW's raw_bin is already black-subtracted per-pixel by the adapter
(to_shift8_bin: lin=(visible-black_per_ch)/(white-median(black))) -- and for
every one of the 4259 frames black_level==0, white_level==4095 (Nikon D3200,
single body, verified 2026-07-15), so the register domain here is anchored
at black=0 by construction; tau_for_frame is called with black_level=0 to
stay on that same zero-based axis (see PASCALRAW_BLACK/PASCALRAW_WHITE
below), not the frame's nominal sensor black level.

Usage (run from isppipeline/hls/tools/):
  python3 analyze_adaptive_tau_pascalraw.py \\
      --data-dir ../../../data/pascalraw_test [--limit N] [--out results.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aodraw_adapter import extract_exif  # noqa: E402
from checker_adaptive_tau import SensorParams, tau_for_frame  # noqa: E402

DARK_RATIO_PCT = 80  # deployed C0 constant, src/dfxisp_accel.cpp:94
C1_DARK16_THR = 0.62  # recommended-but-undeployed C1, checker-status-2026-07-10.md
ISO_BINS = [0, 400, 800, 1600, 3200, 6400, 12800, 1_000_000]


def dark_ratio_at(v8: np.ndarray, thr8: int) -> float:
    """Fraction of 8-bit pixels strictly below thr8 (same definition as
    analyze_adaptive_tau_sonynod.dark_ratio_at / checker_stat_sweep.hist_stats)."""
    return float((v8 < thr8).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True,
                     help="pascalraw_adapter.py output dir (has frames_meta.csv, raw_bin/)")
    ap.add_argument("--raw-dir", type=Path, default=None,
                     help="dir of original .NEF, for EXIF re-read (default: meta.json's raw_dir)")
    ap.add_argument("--exiftool", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path,
                     default=Path("adaptive_tau_pascalraw_results.csv"))
    args = ap.parse_args()

    meta = json.loads((args.data_dir / "meta.json").read_text())
    raw_dir = args.raw_dir or Path(meta["raw_dir"])

    with (args.data_dir / "frames_meta.csv").open() as f:
        frames = list(csv.DictReader(f))
    if args.limit:
        frames = frames[: args.limit]

    sp = SensorParams()
    rows = []
    for i, fr in enumerate(frames):
        stem = fr["stem"]
        w, h = int(fr["w"]), int(fr["h"])
        white_level = float(fr["white_level"])
        bin_path = args.data_dir / "raw_bin" / f"{stem}.bin"
        arr = np.fromfile(bin_path, dtype="<u2").reshape(h, w)
        v8 = (arr >> 8).astype(np.uint8)

        nef = raw_dir / f"{stem}.nef"
        if not nef.exists():
            nef = raw_dir / f"{stem}.NEF"
        exif = extract_exif(nef, args.exiftool) if nef.exists() else \
            {"iso": None, "exposure_s": None, "f_number": None}

        d50 = dark_ratio_at(v8, 50)  # C0-domain proxy
        d16 = dark_ratio_at(v8, 16)  # C1

        frame = tau_for_frame(exif, 0.0, white_level, sp, k=5.0)
        thr8_adaptive = frame["register"] >> 8
        d_adaptive = dark_ratio_at(v8, thr8_adaptive)

        rows.append({
            "stem": stem,
            "iso": exif.get("iso"),
            "exposure_s": exif.get("exposure_s"),
            "dark50": d50,
            "dark16": d16,
            "adaptive_thr8": thr8_adaptive,
            "dark_adaptive": d_adaptive,
            "c0_false_trigger": d50 * 100 > DARK_RATIO_PCT,
            "c1_false_trigger": d16 > C1_DARK16_THR,
            "adaptive_false_trigger": d_adaptive > C1_DARK16_THR,
        })
        if (i + 1) % 200 == 0:
            print(f"...{i + 1}/{len(frames)}", file=sys.stderr)

    if not rows:
        print("no frames processed -- check --data-dir", file=sys.stderr)
        return 1

    with args.out.open("w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)

    n = len(rows)
    print(f"\nwrote {args.out} ({n} frames)\n")
    print("overall false-trigger rate (ground truth: 100% NORMAL/daylight)")
    print(f"  C0 (dark_ratio@50 > {DARK_RATIO_PCT}%):        "
          f"{sum(r['c0_false_trigger'] for r in rows) / n:.4f}")
    print(f"  C1 (dark_ratio@16 > {C1_DARK16_THR}):          "
          f"{sum(r['c1_false_trigger'] for r in rows) / n:.4f}")
    print(f"  adaptive (dark_ratio@thr8 > {C1_DARK16_THR}):  "
          f"{sum(r['adaptive_false_trigger'] for r in rows) / n:.4f}")

    n_no_iso = sum(1 for r in rows if r["iso"] is None)
    print(f"\n{n_no_iso}/{n} frames had no ISO from EXIF")
    if n_no_iso < n:
        print(f"\n{'ISO bucket':<16}{'n':>5}{'C0 FT':>10}{'C1 FT':>10}{'adaptive FT':>14}")
        for lo, hi in zip(ISO_BINS[:-1], ISO_BINS[1:]):
            bucket = [r for r in rows if r["iso"] is not None and lo <= r["iso"] < hi]
            if not bucket:
                continue
            bn = len(bucket)
            print(f"[{lo:>5},{hi:>6}){bn:>5}"
                  f"{sum(r['c0_false_trigger'] for r in bucket) / bn:>10.3f}"
                  f"{sum(r['c1_false_trigger'] for r in bucket) / bn:>10.3f}"
                  f"{sum(r['adaptive_false_trigger'] for r in bucket) / bn:>14.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
