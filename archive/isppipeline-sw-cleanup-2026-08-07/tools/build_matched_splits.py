#!/usr/bin/env python3
"""build_matched_splits.py -- size-matched LOD/PASCAL splits + a shuffled
combined split, for a joint checker LOW_LIGHT-verdict confusion matrix
(recall from LOD + false-trigger from PASCAL in one balanced-N table
instead of two separately-sized reports).

Reads the two existing full-dataset analysis CSVs (already has dark50/
dark16/adaptive_thr8/verdict columns per frame -- no raw_bin re-decode
needed):
  LOD    = adaptive_tau_sonynod_2026-07-13.csv    (321 frames, 100% real
           low-light, SonyNOD/RAW-NOD Sony subset)
  PASCAL = adaptive_tau_pascalraw_results.csv     (4259 frames, 100%
           daylight, PASCALRAW)

LOD_split uses all 321 LOD frames -- it's the smaller dataset (real
low-light captures are scarce) and 321 already fits any reasonable N, so
there's no reason to subsample it. PASCAL_split is an ISO-stratified
random sample of the same size from PASCAL's 4259, preserving PASCAL's
own ISO shape (largest-remainder apportionment, fixed seed, no
minimum-per-bucket floor -- see NOTE below). Shuffle_split is the
concatenation of both, shuffled with a separate fixed seed.

NOTE -- LOD and PASCAL ISO distributions barely overlap: LOD is 88% in
[6400,12800) (real low-light needs high ISO), PASCAL is 90% in [400,800)
(daylight rarely needs high ISO). Matching frame COUNT does not create
ISO-balanced coverage between the two classes -- that would require
discarding almost all of LOD's high-ISO frames or almost all of PASCAL's
low-ISO frames to force overlap, which defeats the purpose of using real
captures. Any per-ISO-bucket confusion-matrix cell built from
Shuffle_split will in practice be dominated by one class per bucket; only
the pooled (non-stratified) confusion matrix is class-balanced by design.

Usage (run from isppipeline/hls/tools/):
  python3 build_matched_splits.py [--n N] [--seed N] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

ISO_BINS = [0, 400, 800, 1600, 3200, 6400, 12800, 1_000_000]


def bucket(iso: float) -> tuple[int, int] | None:
    for lo, hi in zip(ISO_BINS[:-1], ISO_BINS[1:]):
        if lo <= iso < hi:
            return (lo, hi)
    return None


def load(path: Path, verdict_cols: tuple[str, str, str], gt_lowlight: bool,
         source: str, data_dir: str) -> list[dict]:
    rows = []
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append({
                "source": source,
                "stem": r["stem"],
                "iso": float(r["iso"]),
                "exposure_s": r["exposure_s"],
                "dark50": r["dark50"],
                "dark16": r["dark16"],
                "adaptive_thr8": r["adaptive_thr8"],
                "dark_adaptive": r["dark_adaptive"],
                "c0_verdict_lowlight": r[verdict_cols[0]],
                "c1_verdict_lowlight": r[verdict_cols[1]],
                "adaptive_verdict_lowlight": r[verdict_cols[2]],
                "gt_lowlight": gt_lowlight,
                "data_dir": data_dir,
            })
    return rows


def stratified_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Largest-remainder apportionment across ISO buckets, proportional to
    the input rows' own ISO shape, then random.sample within each bucket."""
    buckets: dict = defaultdict(list)
    for r in rows:
        buckets[bucket(r["iso"])].append(r)
    total = len(rows)
    raw = {b: len(v) / total * n for b, v in buckets.items()}
    target = {b: int(x) for b, x in raw.items()}
    remainder = n - sum(target.values())
    order = sorted(raw, key=lambda b: raw[b] - target[b], reverse=True)
    for b in order[:remainder]:
        target[b] += 1

    rng = random.Random(seed)
    out = []
    for b, k in target.items():
        pool = buckets[b]
        k = min(k, len(pool))
        out.extend(rng.sample(pool, k))
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def bucket_report(rows: list[dict], label: str) -> None:
    c: dict = defaultdict(int)
    for r in rows:
        c[bucket(r["iso"])] += 1
    print(f"{label}: n={len(rows)}")
    for b in sorted(c, key=lambda x: x[0] if x else -1):
        lo, hi = b
        print(f"  [{lo:>5},{hi:>7}) {c[b]:>4}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lod-csv", type=Path,
                     default=Path("../results/adaptive_tau_sonynod_2026-07-13.csv"))
    ap.add_argument("--pascal-csv", type=Path,
                     default=Path("../results/adaptive_tau_pascalraw_results.csv"))
    ap.add_argument("--n", type=int, default=None,
                     help="target frames per split (default: full LOD count)")
    ap.add_argument("--seed", type=int, default=20260715)
    ap.add_argument("--out-dir", type=Path, default=Path("../results"))
    args = ap.parse_args()

    lod_rows = load(args.lod_csv,
                     ("c0_lowlight", "c1_lowlight", "adaptive_lowlight"),
                     gt_lowlight=True, source="lod",
                     data_dir="data/sonynod_test/raw_bin")
    pascal_rows = load(args.pascal_csv,
                        ("c0_false_trigger", "c1_false_trigger", "adaptive_false_trigger"),
                        gt_lowlight=False, source="pascal",
                        data_dir="data/pascalraw_test/raw_bin")

    n = args.n or len(lod_rows)
    if n > len(lod_rows):
        raise SystemExit(f"--n {n} exceeds LOD total {len(lod_rows)}")

    lod_split = lod_rows if n == len(lod_rows) else \
        stratified_sample(lod_rows, n, args.seed)
    pascal_split = stratified_sample(pascal_rows, n, args.seed + 1)

    shuffle_split = list(lod_split) + list(pascal_split)
    random.Random(args.seed + 2).shuffle(shuffle_split)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "lod_split_2026-07-15.csv", lod_split)
    write_csv(args.out_dir / "pascal_split_2026-07-15.csv", pascal_split)
    write_csv(args.out_dir / "shuffle_split_2026-07-15.csv", shuffle_split)

    bucket_report(lod_split, "LOD_split")
    bucket_report(pascal_split, "PASCAL_split")
    n_lod = sum(1 for r in shuffle_split if r["source"] == "lod")
    n_pascal = sum(1 for r in shuffle_split if r["source"] == "pascal")
    print(f"Shuffle_split: n={len(shuffle_split)} (lod={n_lod}, pascal={n_pascal})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
