#!/usr/bin/env python3
"""Stage 1 sweep — DFX-aware scheduler trade-off across parameter cases.

Reuses tools/scheduler_sim.py (build_sequence/run_policy/metrics) and sweeps the
full `plus_min_dwell` policy over:
  * hysteresis band (TH_LO, TH_HI)   : narrow / medium / wide
  * temporal N (consecutive votes)   : 3 / 5 / 8
  * min dwell frames                 : 15 / 30 / 60
and reports skipped/invalid frames for reconfiguration-delay cases
PR_INVALID in {2, 4, 8} (the "reconfig-delay sensitivity", RESEARCH §5 / Stage 1).

Deterministic (fixed seed), numpy only. Output: results/scheduler_sweep.csv.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import scheduler_sim as S  # module-level constants are monkeypatched per case

BANDS = {"narrow": (490, 534), "medium": (464, 560), "wide": (430, 594)}
TEMPORAL = [3, 5, 8]
MIN_DWELL = [15, 30, 60]
PR_CASES = [2, 4, 8]


def run_case(band, temporal_n, min_dwell):
    lo, hi = BANDS[band]
    S.TH_LO, S.TH_HI = lo, hi
    S.TEMPORAL_N, S.MIN_DWELL = temporal_n, min_dwell
    luma, truth = S.build_sequence()
    decided, switches = S.run_policy(luma, "plus_min_dwell")
    S.PR_INVALID = 1  # skipped computed as switches*PR later; keep base 1 here
    mismatch, switch_per_1k, thrash, _ = S.metrics(decided, truth, switches, "plus_min_dwell")
    nsw = len(switches)
    return mismatch, switch_per_1k, thrash, nsw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/scheduler_sweep.csv")
    args = ap.parse_args()

    rows = []
    best = None
    for band in BANDS:
        for tn in TEMPORAL:
            for md in MIN_DWELL:
                mismatch, sw1k, thrash, nsw = run_case(band, tn, md)
                skipped = {pr: nsw * pr for pr in PR_CASES}
                rows.append((band, tn, md, mismatch, sw1k, thrash, nsw, skipped))
                # rank: no thrashing, then low mismatch, then few switches
                key = (thrash, mismatch, sw1k)
                if best is None or key < best[0]:
                    best = (key, (band, tn, md, mismatch, sw1k, thrash, nsw))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["band", "temporal_n", "min_dwell", "mode_mismatch",
                     "switch_per_1k", "thrashing", "switches",
                     "skipped@PR2", "skipped@PR4", "skipped@PR8"])
        for band, tn, md, mismatch, sw1k, thrash, nsw, sk in rows:
            wr.writerow([band, tn, md, f"{mismatch:.3f}", f"{sw1k:.1f}",
                         f"{thrash:.3f}", nsw, sk[2], sk[4], sk[8]])
    print(f"wrote {out} ({len(rows)} cases)")
    print("\ntop cases (no thrashing, low mismatch, few switches):")
    ranked = sorted(rows, key=lambda r: (r[5], r[3], r[4]))[:6]
    print(f"{'band':7s} {'N':>2s} {'dwell':>5s} {'mism':>6s} {'sw/1k':>6s} {'thrash':>6s} {'skip@PR4':>8s}")
    for band, tn, md, mm, sw1k, th, nsw, sk in ranked:
        print(f"{band:7s} {tn:2d} {md:5d} {mm:6.3f} {sw1k:6.1f} {th:6.3f} {sk[4]:8d}")
    b = best[1]
    print(f"\nrecommended: band={b[0]} temporal_n={b[1]} min_dwell={b[2]} "
          f"(mismatch={b[3]:.3f}, switch/1k={b[4]:.1f}, thrash={b[5]:.3f}, switches={b[6]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
