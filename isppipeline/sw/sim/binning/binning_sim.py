#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/binning/binning_sim.py
# Date   : 2026-08-12 (LOD_test migration re-run; see binning_report.md)
# Function: Implements binning.md §3 -- measures whether same-color 2x2
#           binning (BIN_BINNING) actually delivers the claimed +6dB (R/B)
#           / +9dB (G) SNR gain over a no-binning (n=1) baseline, using the
#           pipeline's calibrated Poisson-Gaussian noise model (A_Q8/B_DN2).
# Sources: isppipeline/sw/sim/binning.md, isppipeline/sw/gen_lowlight_isp_golden.py.
# =============================================================================
"""binning_sim: reproducible same-color-binning SNR gain measurement
(binning.md §3).

`binned_raw(..., bin_mode=BIN_BINNING)` is imported unmodified from
gen_lowlight_isp_golden.py (binning.md §3.2: no algorithm reimplementation).
`unbinned_raw()` has no equivalent in the golden generator (there is no
"skip binning" mode), so it is defined locally exactly per binning.md §3.2's
docstring.

Measurement uses a single interior binned cell (BX, BY), not the whole 32x32
grid: binned_raw()'s BIN_BINNING neighbourhood clamps at the frame edge
(clamp(bx+dx, 0, bw-1)), so a border cell effectively averages fewer than 4/8
independent samples and would understate/distort the gain. A fixed interior
cell measured across N_REPEATS independent frames avoids that without
changing the frame size (binning.md §3.1's stated 64x64/200-repeat budget).

blc_sim.py and gain_sim.py both import from this module (BW/BH/BX/BY/
CHANNEL_STYLE/FRAME_W/FRAME_H/gen_frame for blc_sim.py's frame generator
reuse; CHANNEL_STYLE/SIGNAL_LEVELS/variance for gain_sim.py) -- the names and
signatures below are a shared contract, not just this script's internals.

Usage:
    python3 binning_sim.py [--seed N] [--repeats N] [--out PATH]
                            [--plot-out PATH] [--snr-plot-out PATH] [--no-plot]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw

from gen_lowlight_isp_golden import (  # noqa: E402
    A_Q8, B_DN2, BIN_BINNING, RAW12_MAX, bin_dim, binned_raw, cell_sites,
)

# Deployed calibration (SonyNOD ISO 6400) is the default; --a-q8/--b-dn2 point
# the sim at a different one. blc_sim.py and gain_sim.py reuse gen_frame()/
# variance() from this module, so setting these reaches them too. The values
# imported from the canonical golden above are never mutated.
NOISE_A_Q8: float = float(A_Q8)
NOISE_B_DN2: float = float(B_DN2)


def set_noise_model(a_q8: float, b_dn2: float) -> None:
    """Repoint variance()/gen_frame() at another calibration of the same model."""
    global NOISE_A_Q8, NOISE_B_DN2
    NOISE_A_Q8, NOISE_B_DN2 = float(a_q8), float(b_dn2)


def add_noise_model_args(ap: argparse.ArgumentParser) -> None:
    """Shared by binning/blc/gain sims so all three can use one calibration."""
    ap.add_argument("--a-q8", type=float, default=float(A_Q8),
                    help="shot-noise slope a in Q8 (default: deployed A_Q8)")
    ap.add_argument("--b-dn2", type=float, default=float(B_DN2),
                    help="read-noise variance b in DN^2 (default: deployed B_DN2)")

# binning.md §3.1's 18-value list has 0 and 8 DN at the bottom; the doc's own
# prose says "16점" (16 points) -- this script follows the prose and keeps
# the 16 points from 16 DN up, matching binning_report.md's table (16..3072).
SIGNAL_LEVELS = [16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512,
                 768, 1024, 1536, 2048, 3072]

FRAME_W = FRAME_H = 64            # binning.md §3.1: 64x64 Bayer grid
BW, BH = bin_dim(FRAME_W), bin_dim(FRAME_H)   # 32x32 binned cells
BX, BY = BW // 2, BH // 2         # interior cell -- no edge-clamp truncation

N_REPEATS_DEFAULT = 200           # binning.md §3.1
CI_Z = 1.96
EXPECT_DB = {"R": 6.0, "G": 9.0, "B": 6.0}
TOLERANCE_DB = 1.5                # binning.md §3.3

CHANNEL_STYLE = {
    "R": {"color": "#e34948"},
    "G": {"color": "#2e8b57"},
    "B": {"color": "#2a78d6"},
}


def variance(y: float) -> float:
    """binning.md §2.2: variance(y) = (A_Q8/256)*y + B_DN2."""
    return (NOISE_A_Q8 / 256.0) * y + NOISE_B_DN2


def gen_frame(true_signal: float, rng: np.random.Generator) -> np.ndarray:
    """binning.md §3.1: every Bayer site in a flat FRAME_W x FRAME_H frame
    draws independently from N(true_signal, sqrt(variance(true_signal))),
    clipped at 0 and rounded to integer DN."""
    sigma = math.sqrt(variance(true_signal))
    noisy = rng.normal(true_signal, sigma, size=FRAME_W * FRAME_H)
    return np.maximum(0, np.round(noisy)).astype(np.int64)


def unbinned_raw(raw, width, height, bx, by):
    """No binning at all: one raw Bayer sample per channel, n=1. Baseline for
    measuring binning's SNR gain directly.
    G: two raw sub-pixel sites g0/g1 exist per cell; the true n=1 baseline
    uses only one (g0) -- averaging both would already be a 2-sample bin and
    defeat the purpose of a no-binning baseline. (binning.md §3.2, verbatim)
    """
    r, g0, g1, b = cell_sites(raw, width, height, bx, by)
    return r, g0, b


def run(seed: int, n_repeats: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for signal in SIGNAL_LEVELS:
        samples = {"R": {"none": [], "same": []},
                   "G": {"none": [], "same": []},
                   "B": {"none": [], "same": []}}
        for _ in range(n_repeats):
            raw = gen_frame(float(signal), rng)
            r_n, g_n, b_n = unbinned_raw(raw, FRAME_W, FRAME_H, BX, BY)
            r_s, g_s, b_s = binned_raw(raw, FRAME_W, FRAME_H, BW, BH, BX, BY, BIN_BINNING)
            samples["R"]["none"].append(r_n); samples["R"]["same"].append(r_s)
            samples["G"]["none"].append(g_n); samples["G"]["same"].append(g_s)
            samples["B"]["none"].append(b_n); samples["B"]["same"].append(b_s)

        for ch in ("R", "G", "B"):
            sigma_none = float(np.std(samples[ch]["none"], ddof=1))
            sigma_same = float(np.std(samples[ch]["same"], ddof=1))
            gain_db = 20.0 * math.log10(sigma_none / sigma_same) if sigma_same > 0 else float("inf")
            expected = EXPECT_DB[ch]
            rows.append({
                "signal_level": signal,
                "channel": ch,
                "sigma_none": sigma_none,
                "sigma_samecolor": sigma_same,
                "gain_db": gain_db,
                "expected_gain_db": expected,
                "pass": abs(gain_db - expected) <= TOLERANCE_DB,
            })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_gain(rows: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    for ch in ("R", "G", "B"):
        ch_rows = sorted((r for r in rows if r["channel"] == ch), key=lambda r: r["signal_level"])
        x = [r["signal_level"] for r in ch_rows]
        y = [r["gain_db"] for r in ch_rows]
        fails = [(r["signal_level"], r["gain_db"]) for r in ch_rows if not r["pass"]]
        color = CHANNEL_STYLE[ch]["color"]
        ax.plot(x, y, color=color, marker="o", markersize=4, linewidth=1.8, label=f"{ch} measured", zorder=3)
        expected = EXPECT_DB[ch]
        ax.axhline(expected, color=color, linewidth=1, linestyle=":", alpha=0.6, zorder=1)
        ax.fill_between(x, expected - TOLERANCE_DB, expected + TOLERANCE_DB, color=color, alpha=0.08, zorder=0)
        if fails:
            fx, fy = zip(*fails)
            ax.scatter(fx, fy, color=color, marker="x", s=90, zorder=4, linewidths=2.2)
    ax.set_xscale("log")
    ax.set_xticks(SIGNAL_LEVELS)
    ax.set_xticklabels([str(s) for s in SIGNAL_LEVELS], rotation=60, ha="right", fontsize=7)
    ax.set_xlabel("Signal level (12-bit DN)")
    ax.set_ylabel("gain_dB = 20*log10(sigma_none / sigma_samecolor)")
    ax.set_title("binning.md §3: same-color 2x2 binning SNR gain vs signal level\n"
                 "(dotted = expected +6/+9dB, band = +/-1.5dB tolerance, x = FAIL)")
    ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_snr_comparison(rows: list[dict], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=150, sharey=False)
    for ax, ch in zip(axes, ("R", "G", "B")):
        ch_rows = sorted((r for r in rows if r["channel"] == ch), key=lambda r: r["signal_level"])
        x = [r["signal_level"] for r in ch_rows]
        snr_none = [20 * math.log10(r["signal_level"] / r["sigma_none"]) if r["sigma_none"] > 0 else float("nan") for r in ch_rows]
        snr_same = [20 * math.log10(r["signal_level"] / r["sigma_samecolor"]) if r["sigma_samecolor"] > 0 else float("nan") for r in ch_rows]
        color = CHANNEL_STYLE[ch]["color"]
        ax.plot(x, snr_none, color="#8a8a86", linestyle="--", marker="x", markersize=4, label="none (n=1)", zorder=3)
        ax.plot(x, snr_same, color=color, linestyle="-", marker="o", markersize=4, label="samecolor (binned)", zorder=3)
        ax.set_xscale("log")
        ax.set_xticks(SIGNAL_LEVELS)
        ax.set_xticklabels([str(s) for s in SIGNAL_LEVELS], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("Signal level (12-bit DN)")
        ax.set_title(f"{ch} channel")
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)
    axes[0].set_ylabel("SNR = 20*log10(signal/sigma) (dB)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.08))
    fig.suptitle("binning.md §3: absolute SNR, none vs same-color binning", y=1.16)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=N_REPEATS_DEFAULT)
    sim_dir = Path(__file__).resolve().parent
    ap.add_argument("--out", type=Path, default=sim_dir / "binning_results.csv")
    ap.add_argument("--plot-out", type=Path, default=sim_dir / "binning_results.png")
    ap.add_argument("--snr-plot-out", type=Path, default=sim_dir / "binning_snr_comparison.png")
    ap.add_argument("--no-plot", action="store_true")
    add_noise_model_args(ap)
    args = ap.parse_args()
    set_noise_model(args.a_q8, args.b_dn2)
    print(f"noise model: A_Q8={NOISE_A_Q8:.0f} B_DN2={NOISE_B_DN2:.0f}")

    rows = run(args.seed, args.repeats)
    write_csv(rows, args.out)
    if not args.no_plot:
        plot_gain(rows, args.plot_out)
        plot_snr_comparison(rows, args.snr_plot_out)

    n_fail = sum(1 for r in rows if not r["pass"])
    for r in rows:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"s={r['signal_level']:5d} ch={r['channel']} sigma_none={r['sigma_none']:7.3f} "
              f"sigma_same={r['sigma_samecolor']:7.3f} gain={r['gain_db']:6.2f}dB "
              f"expect={r['expected_gain_db']:.1f}dB [{status}]")
    print(f"\nResults written to {args.out}")
    if not args.no_plot:
        print(f"Plots written to {args.plot_out}, {args.snr_plot_out}")
    print(f"{n_fail}/{len(rows)} FAIL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
