#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/blc_sim.py
# Date   : 2026-08-12
# Function: Implements blc.md §3 -- measures whether "average, then subtract
#           the pedestal once" (the deployed order) is actually less biased
#           than "clip each sample to the pedestal, then average" (the
#           opposite order), and by how much, using the pipeline's calibrated
#           Poisson-Gaussian noise model (A_Q8/B_DN2, ISO 6400 domain).
# Sources: isppipeline/sw/sim/blc.md, isppipeline/sw/sim/binning.md,
#          isppipeline/sw/gen_lowlight_isp_golden.py, isppipeline/sw/sim/binning_sim.py.
# =============================================================================
"""blc_sim: reproducible clipping-order bias measurement for stage (2) BLC.

Path (a) (current/deployed order) reuses binned_rgb() -- i.e. binned_raw()
then correct_channel() -- unmodified (blc.md §3.2a: no algorithm
reimplementation). Path (b) (opposite order) has no equivalent in the
deployed pipeline, so it is defined locally here as the control group
(blc.md §3.2b): binned_raw_clip_first() mirrors binned_raw()'s BIN_BINNING
loop exactly, except each site is clipped to max(0, site - BLC_LEVEL12)
before summing (instead of clipping the average once, after summing).
apply_range_and_gain() is the post-average tail of correct_channel() (range
restore + WB/exposure gain) with the pedestal-subtraction line removed,
since path (b) already subtracted+clipped the pedestal per site.

Frame generation is reused from binning_sim.py (same seed/generator, per
blc.md §3.1/§2.2): a flat true signal over the same 64x64 Bayer frame,
evaluated at the same interior cell (BX, BY) so the 2x2 same-color
neighbourhood never touches cell_sites()'s border clamp.

Usage:
    python3 blc_sim.py [--seed N] [--repeats N] [--out PATH]
                        [--plot-out PATH] [--clip-plot-out PATH] [--no-plot]
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

# NOTE (2026-08-12 LOD_test migration): binning.md/blc.md/gain.md's sim
# scripts were originally flat in isppipeline/sw/sim/ (sys.path.insert at
# parents[1] correctly reached isppipeline/sw/ from there); a later reorg
# moved each into its own isppipeline/sw/sim/<module>/ subdirectory, adding
# one level of nesting. Fixed here to parents[2] for gen_lowlight_isp_golden,
# plus an explicit path to the sim/binning/ sibling for binning_sim reuse.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "binning"))  # sim/binning

from gen_lowlight_isp_golden import (  # noqa: E402
    BIN_BINNING, BLC_LEVEL12, BLC_MUL_Q8, EXPOSURE_GAIN_Q8, RAW12_MAX,
    WB_B_Q8, WB_G_Q8, WB_R_Q8, binned_rgb, cell_sites, clamp, correct_channel,
)
from binning_sim import (  # noqa: E402
    BW, BH, BX, BY, CHANNEL_STYLE, FRAME_H, FRAME_W, add_noise_model_args,
    gen_frame, set_noise_model,
)

# blc.md §3.1 -- identical to binning.md §3.1 so the two sims are directly
# comparable at the same signal levels.
SIGNAL_LEVELS = [0, 8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512,
                  768, 1024, 1536, 2048, 3072]
N_REPEATS_DEFAULT = 2000  # blc.md §3.1
CI_Z = 1.96  # 95%
CONVERGENCE_TOP_N = 3  # blc.md §3.3 criterion 3

CHANNEL_WB = {"R": WB_R_Q8, "G": WB_G_Q8, "B": WB_B_Q8}
ORDER_STYLE = {
    "a": {"linestyle": "-", "marker": "o", "label": "order a (avg -> subtract, deployed)"},
    "b": {"linestyle": "--", "marker": "x", "label": "order b (clip -> avg, control)"},
}


def binned_raw_clip_first(raw, width, height, bw, bh, bx, by):
    """blc.md §3.2(b): opposite order -- clip each site to
    max(0, site - BLC_LEVEL12) BEFORE averaging. Local control-group
    reimplementation only (never merged into gen_lowlight_isp_golden.py);
    mirrors binned_raw()'s BIN_BINNING loop so the only behavioural
    difference from path (a) is clip-before-vs-after-average."""
    sum_r = sum_g = sum_b = 0
    for dy in (0, 1):
        cy = clamp(by + dy, 0, bh - 1)
        for dx in (0, 1):
            cx = clamp(bx + dx, 0, bw - 1)
            r, g0, g1, b = cell_sites(raw, width, height, cx, cy)
            sum_r += max(0, r - BLC_LEVEL12)
            sum_g += max(0, g0 - BLC_LEVEL12) + max(0, g1 - BLC_LEVEL12)
            sum_b += max(0, b - BLC_LEVEL12)
    return sum_r // 4, sum_g // 8, sum_b // 4


def apply_range_and_gain(v: int, wb_q8: int) -> int:
    """The post-pedestal tail of correct_channel() (range restore + gain),
    reused verbatim minus the pedestal-subtraction line -- path (b) already
    subtracted+clipped the pedestal per site in binned_raw_clip_first()."""
    v = clamp((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8
    return clamp((v * gain_q8) >> 8, 0, RAW12_MAX)


def path_b(raw, w, h, bw, bh, bx, by):
    r, g, b = binned_raw_clip_first(raw, w, h, bw, bh, bx, by)
    return (apply_range_and_gain(r, WB_R_Q8),
            apply_range_and_gain(g, WB_G_Q8),
            apply_range_and_gain(b, WB_B_Q8))


def run(seed: int, n_repeats: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for signal in SIGNAL_LEVELS:
        outs = {"a": {"R": [], "G": [], "B": []}, "b": {"R": [], "G": [], "B": []}}
        for _ in range(n_repeats):
            raw = gen_frame(signal, rng)
            ra, ga, ba = binned_rgb(raw, FRAME_W, FRAME_H, BW, BH, BX, BY, BIN_BINNING)
            rb, gb, bb = path_b(raw, FRAME_W, FRAME_H, BW, BH, BX, BY)
            outs["a"]["R"].append(ra); outs["a"]["G"].append(ga); outs["a"]["B"].append(ba)
            outs["b"]["R"].append(rb); outs["b"]["G"].append(gb); outs["b"]["B"].append(bb)

        for ch in ("R", "G", "B"):
            reference = correct_channel(signal, CHANNEL_WB[ch])
            for order in ("a", "b"):
                vals = np.array(outs[order][ch], dtype=float)
                mean = float(vals.mean())
                se = float(vals.std(ddof=1)) / math.sqrt(n_repeats)
                bias = mean - reference
                rows.append({
                    "signal_level": signal,
                    "channel": ch,
                    "order": order,
                    "n": n_repeats,
                    "mean_output": mean,
                    "reference_output": reference,
                    "bias": bias,
                    "se": se,
                    "ci95_lo": bias - CI_Z * se,
                    "ci95_hi": bias + CI_Z * se,
                    "ci_includes_zero": (bias - CI_Z * se) <= 0 <= (bias + CI_Z * se),
                    "clip_rate": float((vals == 0).mean()),
                })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def spearman(xs, ys) -> float:
    def rank(a: np.ndarray) -> np.ndarray:
        order = np.argsort(a)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(len(a))
        return ranks
    return float(np.corrcoef(rank(np.array(xs)), rank(np.array(ys)))[0, 1])


def evaluate(rows: list[dict]) -> int:
    """blc.md §3.3 -- prints the three pass/fail criteria; returns fail count."""
    by_key = {(r["signal_level"], r["channel"], r["order"]): r for r in rows}
    channels = sorted({r["channel"] for r in rows})
    signals = sorted({r["signal_level"] for r in rows})
    n_fail = 0

    print(f"\n--- Criterion 1: bias_b > bias_a for s <= BLC_LEVEL12 ({BLC_LEVEL12}) ---")
    for s in (s for s in signals if s <= BLC_LEVEL12):
        for ch in channels:
            a, b = by_key[(s, ch, "a")]["bias"], by_key[(s, ch, "b")]["bias"]
            ok = b > a
            n_fail += not ok
            print(f"  {'PASS' if ok else 'FAIL'}  s={s:5d} ch={ch}  "
                  f"bias_a={a:+8.3f}  bias_b={b:+8.3f}")

    print("\n--- Criterion 2: bias_a statistically indistinguishable from 0 "
          "(order a, all s) ---")
    for s in signals:
        for ch in channels:
            r = by_key[(s, ch, "a")]
            ok = r["ci_includes_zero"]
            n_fail += not ok
            print(f"  {'PASS' if ok else 'FAIL'}  s={s:5d} ch={ch}  "
                  f"bias_a={r['bias']:+8.3f}  95% CI=[{r['ci95_lo']:+.3f}, {r['ci95_hi']:+.3f}]")

    print(f"\n--- Criterion 3: |bias_b - bias_a| trends down with signal and its "
          f"CI includes 0 at the top {CONVERGENCE_TOP_N} signal levels ---")
    top_signals = signals[-CONVERGENCE_TOP_N:]
    for ch in channels:
        diffs = [by_key[(s, ch, "b")]["bias"] - by_key[(s, ch, "a")]["bias"] for s in signals]
        rho = spearman(signals, [abs(d) for d in diffs])
        trend_ok = rho < -0.5
        n_fail += not trend_ok
        print(f"  {'PASS' if trend_ok else 'FAIL'}  ch={ch}  "
              f"spearman(signal, |diff|)={rho:+.3f} (want < -0.5)")
        for s in top_signals:
            ra, rb = by_key[(s, ch, "a")], by_key[(s, ch, "b")]
            diff = rb["bias"] - ra["bias"]
            se_diff = math.sqrt(ra["se"] ** 2 + rb["se"] ** 2)
            lo, hi = diff - CI_Z * se_diff, diff + CI_Z * se_diff
            ok = lo <= 0 <= hi
            n_fail += not ok
            print(f"  {'PASS' if ok else 'FAIL'}  s={s:5d} ch={ch}  "
                  f"diff={diff:+8.3f}  95% CI=[{lo:+.3f}, {hi:+.3f}]")

    return n_fail


def plot_bias(rows: list[dict], path: Path) -> None:
    """blc.md §3.3 criteria 1/2/3: bias vs signal level per channel, both
    orders, with 95% CI bands. Pedestal marked; the a/b gap should collapse
    to ~0 (and its CI should straddle 0) by the top signal levels."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=150, sharey=False)
    signals = sorted({r["signal_level"] for r in rows})

    for ax, ch in zip(axes, ("R", "G", "B")):
        for order in ("a", "b"):
            ch_rows = sorted(
                (r for r in rows if r["channel"] == ch and r["order"] == order),
                key=lambda r: r["signal_level"])
            x = [r["signal_level"] for r in ch_rows]
            y = [r["bias"] for r in ch_rows]
            lo = [r["ci95_lo"] for r in ch_rows]
            hi = [r["ci95_hi"] for r in ch_rows]
            style = ORDER_STYLE[order]
            color = CHANNEL_STYLE[ch]["color"] if order == "a" else "#8a8a86"
            ax.plot(x, y, color=color, linestyle=style["linestyle"],
                     marker=style["marker"], markersize=4, linewidth=1.8,
                     label=style["label"], zorder=3)
            ax.fill_between(x, lo, hi, color=color, alpha=0.15, zorder=2)

        ax.axhline(0, color="#8a8a86", linewidth=1, zorder=1)
        ax.axvline(BLC_LEVEL12, color="#e34948", linewidth=1, linestyle=":",
                    zorder=1, label="pedestal (BLC_LEVEL12)" if ch == "R" else "_nolegend_")
        ax.set_xscale("symlog", linthresh=8)
        ax.set_xlim(left=0)
        ax.set_xticks(signals)
        ax.set_xticklabels([str(s) for s in signals], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("Signal level (12-bit DN)")
        ax.set_title(f"{ch} channel")
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)

    axes[0].set_ylabel("bias = mean(output) - reference (DN, post-gain)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.1))
    fig.suptitle("blc.md §3: clipping-order bias (avg-then-subtract vs "
                  "subtract-then-avg)", y=1.2)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_clip_rate(rows: list[dict], path: Path) -> None:
    """blc.md §3.4: how often BLC floors a channel output to exactly 0,
    per order/channel/signal level."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=150, sharey=True)
    signals = sorted({r["signal_level"] for r in rows})

    for ax, ch in zip(axes, ("R", "G", "B")):
        for order in ("a", "b"):
            ch_rows = sorted(
                (r for r in rows if r["channel"] == ch and r["order"] == order),
                key=lambda r: r["signal_level"])
            x = [r["signal_level"] for r in ch_rows]
            y = [100 * r["clip_rate"] for r in ch_rows]
            style = ORDER_STYLE[order]
            color = CHANNEL_STYLE[ch]["color"] if order == "a" else "#8a8a86"
            ax.plot(x, y, color=color, linestyle=style["linestyle"],
                     marker=style["marker"], markersize=4, linewidth=1.8,
                     label=style["label"], zorder=3)

        ax.axvline(BLC_LEVEL12, color="#e34948", linewidth=1, linestyle=":", zorder=1)
        ax.set_xscale("symlog", linthresh=8)
        ax.set_xlim(left=0)
        ax.set_xticks(signals)
        ax.set_xticklabels([str(s) for s in signals], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("Signal level (12-bit DN)")
        ax.set_title(f"{ch} channel")
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)

    axes[0].set_ylabel("P(output == 0) (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.1))
    fig.suptitle("blc.md §3.4: 0-clipping rate by order", y=1.18)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=N_REPEATS_DEFAULT)
    ap.add_argument("--out", type=Path,
                     default=Path(__file__).resolve().parent / "blc_results.csv")
    ap.add_argument("--plot-out", type=Path,
                     default=Path(__file__).resolve().parent / "blc_results.png")
    ap.add_argument("--clip-plot-out", type=Path,
                     default=Path(__file__).resolve().parent / "blc_clip_rate.png")
    ap.add_argument("--no-plot", action="store_true", help="skip PNG generation")
    add_noise_model_args(ap)
    args = ap.parse_args()
    set_noise_model(args.a_q8, args.b_dn2)
    print(f"noise model: A_Q8={args.a_q8:.0f} B_DN2={args.b_dn2:.0f}")

    rows = run(args.seed, args.repeats)
    write_csv(rows, args.out)
    if not args.no_plot:
        plot_bias(rows, args.plot_out)
        plot_clip_rate(rows, args.clip_plot_out)

    n_fail = evaluate(rows)

    print(f"\nResults written to {args.out}")
    if not args.no_plot:
        print(f"Bias plot written to {args.plot_out}")
        print(f"Clip-rate plot written to {args.clip_plot_out}")
    print(f"{n_fail} check(s) failed across all criteria.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
