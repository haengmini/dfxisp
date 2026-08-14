#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/gain_sim.py
# Date   : 2026-08-12
# Function: Implements gain.md §3 goals A/B/C -- (A) does applying gain in the
#           wide 12-bit domain (deployed) really lose less to quantization
#           than applying it after an early 8-bit truncation (control); (B)
#           does SNR stay invariant under the integer gain path (multiply ->
#           >>8 -> clamp) across gain multipliers, and where does the clamp
#           break that invariance; (C) is the fused Q8 gain*WB multiply
#           numerically identical to applying the two gains separately.
#           Goal D (WB re-tuning) is out of scope -- gain.md §3.4 delegates
#           it to AWB.md, already implemented.
# Sources: isppipeline/sw/sim/gain.md, isppipeline/sw/sim/binning.md,
#          isppipeline/sw/gen_lowlight_isp_golden.py, isppipeline/sw/sim/binning_sim.py.
# =============================================================================
"""gain_sim: reproducible measurements for stage (3) gain/WB (gain.md §3).

Goal A path (a) (upstream, deployed) reuses correct_channel() unmodified
(gain.md §5: no algorithm reimplementation) -- BLC and gain both computed in
the wide 12-bit domain, with a plain >>4 standing in for the eventual
12->8bit drop the real pipeline does via the tone LUT (isolating stage (3)
from gamma.md's concern, same spirit as binning.md/blc.md isolating one
stage at a time). Path (b) (downstream, control) has no equivalent in the
deployed pipeline: BLC lines are mirrored locally (correct_channel() has no
BLC-only entry point since gain is unconditionally fused in), then >>4
truncates to 8-bit BEFORE gain, then gain is applied and clamped again in
the narrow 8-bit domain.

Goal B reuses the same multiply->>8->clamp shape as correct_channel()'s
final line, generalized to arbitrary Q8 gains.

Goal C reuses EXPOSURE_GAIN_Q8/WB_*_Q8 and clamp() directly; "separate" is a
local control with no deployed equivalent (two multiply->>8->clamp steps
instead of one fused step).

Frame/noise generation is reused from binning_sim.py (variance(), same A_Q8/
B_DN2 calibration, same SIGNAL_LEVELS sweep, per gain.md §3.1 step 1) but
applied to a scalar already-binned signal rather than a full Bayer frame --
stage (3) has no spatial structure to isolate, unlike binning.md/blc.md.

Usage:
    python3 gain_sim.py [--seed N] [--repeats N] [--no-plot]
                         [--out-a PATH] [--out-b PATH] [--out-c PATH]
                         [--plot-a PATH] [--plot-b PATH] [--plot-c PATH]
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

# NOTE (2026-08-12 LOD_test migration): see blc_sim.py's identical note --
# the flat isppipeline/sw/sim/ -> per-module isppipeline/sw/sim/<module>/
# reorg added one level of nesting; fixed to parents[2] plus an explicit
# path to the sim/binning/ sibling for binning_sim reuse.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "binning"))  # sim/binning

from gen_lowlight_isp_golden import (  # noqa: E402
    BLC_LEVEL12, BLC_MUL_Q8, EXPOSURE_GAIN_Q8, RAW12_MAX,
    WB_B_Q8, WB_G_Q8, WB_R_Q8, clamp, correct_channel,
)
from binning_sim import (  # noqa: E402
    CHANNEL_STYLE, SIGNAL_LEVELS, add_noise_model_args, set_noise_model, variance,
)

CI_Z = 1.96  # 95%
CHANNEL_WB = {"R": WB_R_Q8, "G": WB_G_Q8, "B": WB_B_Q8}

# gain.md §3.1: "각 점 500회 반복". §3.2 doesn't state its own count --
# reused here for the same statistical power.
GOAL_A_REPEATS_DEFAULT = 500
GOAL_B_REPEATS_DEFAULT = 500

GOAL_B_MULTIPLIERS = [0.5, 1.0, 2.0, 4.0]  # gain.md §3.2
# gain.md §3.2 has no explicit tolerance for "invariant" -- reused from
# binning.md §3.3's dB tolerance convention (same repo-wide noise band idea).
GOAL_B_TOLERANCE_DB = 1.5

PATH_STYLE = {
    "upstream": {"linestyle": "-", "marker": "o",
                 "label": "path A: upstream (gain in 12-bit domain, deployed)"},
    "downstream": {"linestyle": "--", "marker": "x",
                   "label": "path B: downstream (gain after 8-bit truncation, control)"},
}
MULT_COLOR = {0.5: "#8a8a86", 1.0: "#2a78d6", 2.0: "#eb6834", 4.0: "#e34948"}


def gen_binned_samples(true_signal: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """binning.md §2.2/§2.3's noise recipe (reused, not re-derived), applied
    directly to a scalar already-binned 12-bit signal -- gain.md §3.1 step 1.
    binning_sim.py's frame/cell machinery measures binning's own spatial SNR
    and isn't needed for a stage-(3) experiment with no spatial structure."""
    sigma = math.sqrt(variance(true_signal))
    noisy = rng.normal(true_signal, sigma, size=n)
    return np.clip(np.round(noisy), 0, RAW12_MAX).astype(int)


# --- Goal A: does upstream placement reduce quantization loss? --------------

def path_upstream(v_raw12: int, wb_q8: int) -> int:
    """Path A: correct_channel() as deployed, then >>4 (stand-in for the
    tone LUT's eventual 12->8bit drop)."""
    return correct_channel(v_raw12, wb_q8) >> 4


def path_downstream(v_raw12: int, wb_q8: int) -> int:
    """Path B (control, gain.md §3.1 step 3): BLC (mirrors correct_channel()'s
    first two lines -- no BLC-only entry point exists to call instead), then
    >>4 to 8-bit BEFORE gain, then gain applied/clamped in the narrow domain."""
    v = v_raw12 - BLC_LEVEL12 if v_raw12 > BLC_LEVEL12 else 0
    v = clamp((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX)
    v8 = v >> 4
    gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8
    return clamp((v8 * gain_q8) >> 8, 0, 255)


def ideal_reference(v_raw12: float, wb_q8: int) -> float:
    """Real-valued equivalent of correct_channel() + the final >>4, with no
    intermediate rounding -- the best-case answer both integer paths are
    compared against to isolate quantization loss due to placement alone."""
    v = max(0.0, v_raw12 - BLC_LEVEL12)
    v = min(v * (BLC_MUL_Q8 / 256.0), float(RAW12_MAX))
    gain = (EXPOSURE_GAIN_Q8 / 256.0) * (wb_q8 / 256.0)
    v = min(v * gain, float(RAW12_MAX))
    return v / 16.0


def run_goal_a(seed: int, n_repeats: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for signal in SIGNAL_LEVELS:
        v_samples = gen_binned_samples(signal, n_repeats, rng)
        for ch, wb_q8 in CHANNEL_WB.items():
            refs = np.array([ideal_reference(float(v), wb_q8) for v in v_samples])
            out_a = np.array([path_upstream(int(v), wb_q8) for v in v_samples], dtype=float)
            out_b = np.array([path_downstream(int(v), wb_q8) for v in v_samples], dtype=float)
            err_a = out_a - refs
            err_b = out_b - refs
            std_a = float(err_a.std(ddof=1))
            std_b = float(err_b.std(ddof=1))
            half_a = CI_Z * std_a / math.sqrt(2 * (n_repeats - 1))
            half_b = CI_Z * std_b / math.sqrt(2 * (n_repeats - 1))
            rows.append({
                "signal_level": signal,
                "channel": ch,
                "n": n_repeats,
                "qerror_std_upstream": std_a,
                "qerror_std_upstream_ci95_lo": std_a - half_a,
                "qerror_std_upstream_ci95_hi": std_a + half_a,
                "qerror_std_downstream": std_b,
                "qerror_std_downstream_ci95_lo": std_b - half_b,
                "qerror_std_downstream_ci95_hi": std_b + half_b,
                "upstream_significantly_better": (std_a + half_a) < (std_b - half_b),
            })
    return rows


# --- Goal B: is SNR invariant under the integer gain path? ------------------

def integer_gain_path(v: int, gain_q8: int) -> int:
    """Same shape as correct_channel()'s final line (multiply -> >>8 ->
    clamp), generalized to an arbitrary Q8 gain (gain.md §3.2)."""
    return clamp((v * gain_q8) >> 8, 0, RAW12_MAX)


def run_goal_b(seed: int, n_repeats: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for mult in GOAL_B_MULTIPLIERS:
        gain_q8 = round(mult * 256)
        for signal in SIGNAL_LEVELS:
            v_samples = gen_binned_samples(signal, n_repeats, rng)
            out_samples = np.array(
                [integer_gain_path(int(v), gain_q8) for v in v_samples], dtype=float)
            std_in = float(v_samples.std(ddof=1))
            std_out = float(out_samples.std(ddof=1))
            mean_out = float(out_samples.mean())
            snr_in_db = 20 * math.log10(signal / std_in) if std_in > 0 else float("inf")
            snr_out_db = (20 * math.log10(mean_out / std_out)
                           if std_out > 0 and mean_out > 0 else float("-inf"))
            delta_db = snr_out_db - snr_in_db
            rows.append({
                "gain_mult": mult,
                "gain_q8": gain_q8,
                "signal_level": signal,
                "snr_in_db": snr_in_db,
                "snr_out_db": snr_out_db,
                "delta_db": delta_db,
                "clip_rate": float((out_samples == RAW12_MAX).mean()),
                "invariant": abs(delta_db) <= GOAL_B_TOLERANCE_DB,
            })
    return rows


# --- Goal C: is the fused gain numerically identical to separate application? --

def gain_fused(v12: int, wb_q8: int) -> int:
    """gain.md §3.3 fused version = correct_channel()'s gain step alone
    (BLC excluded -- v12 swept directly across the full raw range)."""
    gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8
    return clamp((v12 * gain_q8) >> 8, 0, RAW12_MAX)


def gain_separate(v12: int, wb_q8: int) -> int:
    """gain.md §3.3 separate version: exposure gain rounded+clamped first,
    then WB rounded+clamped again -- no deployed equivalent, local control."""
    v = clamp((v12 * EXPOSURE_GAIN_Q8) >> 8, 0, RAW12_MAX)
    return clamp((v * wb_q8) >> 8, 0, RAW12_MAX)


def run_goal_c() -> list[dict]:
    rows = []
    for ch, wb_q8 in CHANNEL_WB.items():
        for v12 in range(RAW12_MAX + 1):
            fused = gain_fused(v12, wb_q8)
            separate = gain_separate(v12, wb_q8)
            rows.append({
                "channel": ch,
                "v12": v12,
                "fused_12bit": fused,
                "separate_12bit": separate,
                "diff_12bit_lsb": fused - separate,
                "fused_8bit": fused >> 4,
                "separate_8bit": separate >> 4,
                "diff_8bit_lsb": (fused >> 4) - (separate >> 4),
            })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# --- evaluation (prints PASS/FAIL-style summaries per gain.md §3) -----------

def evaluate_goal_a(rows: list[dict]) -> int:
    """gain.md §3.1: path A's quantization-error std must be significantly
    (non-overlapping 95% CIs) smaller than path B's."""
    print("\n--- Goal A: does upstream gain placement reduce quantization loss? ---")
    n_fail = 0
    for r in rows:
        ok = r["upstream_significantly_better"]
        n_fail += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  s={r['signal_level']:5d} ch={r['channel']}  "
              f"std_upstream={r['qerror_std_upstream']:.3f}  "
              f"std_downstream={r['qerror_std_downstream']:.3f}")
    print(f"  {len(rows) - n_fail}/{len(rows)} PASS.")
    return n_fail


def evaluate_goal_b(rows: list[dict]) -> None:
    """gain.md §3.2: not a pass/fail claim -- reports where SNR invariance
    breaks (expected near the RAW12_MAX clamp at high signal x high gain)."""
    print(f"\n--- Goal B: SNR invariance under integer gain (tolerance "
          f"+/-{GOAL_B_TOLERANCE_DB}dB) ---")
    broken = [r for r in rows if not r["invariant"]]
    print(f"  {len(rows) - len(broken)}/{len(rows)} points within tolerance.")
    if broken:
        print("  Broken invariance (clamp saturation region):")
        for r in sorted(broken, key=lambda r: (r["gain_mult"], r["signal_level"])):
            print(f"    mult={r['gain_mult']:.1f}x  s={r['signal_level']:5d}  "
                  f"delta={r['delta_db']:+6.2f}dB  clip_rate={100*r['clip_rate']:5.1f}%")


def evaluate_goal_c(rows: list[dict]) -> None:
    """gain.md §3.3: exhaustive comparison, no repeats -- reports counts and
    max deviation in both the 12-bit and (post >>4) 8-bit domain."""
    print("\n--- Goal C: fused vs separate gain, exhaustive 0..4095 ---")
    for ch in CHANNEL_WB:
        ch_rows = [r for r in rows if r["channel"] == ch]
        diffs12 = [r["diff_12bit_lsb"] for r in ch_rows]
        diffs8 = [r["diff_8bit_lsb"] for r in ch_rows]
        n_diff12 = sum(1 for d in diffs12 if d != 0)
        n_diff8 = sum(1 for d in diffs8 if d != 0)
        print(f"  ch={ch}  12-bit: {n_diff12}/{len(ch_rows)} differ, "
              f"max |diff|={max(abs(d) for d in diffs12)} LSB  |  "
              f"8-bit (post tone-curve stand-in): {n_diff8}/{len(ch_rows)} differ, "
              f"max |diff|={max(abs(d) for d in diffs8)} LSB")


# --- plots --------------------------------------------------------------

def plot_goal_a(rows: list[dict], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=150, sharey=False)

    for ax, ch in zip(axes, ("R", "G", "B")):
        ch_rows = sorted((r for r in rows if r["channel"] == ch),
                          key=lambda r: r["signal_level"])
        x = [r["signal_level"] for r in ch_rows]
        for key, style in (("upstream", PATH_STYLE["upstream"]),
                            ("downstream", PATH_STYLE["downstream"])):
            y = [r[f"qerror_std_{key}"] for r in ch_rows]
            lo = [r[f"qerror_std_{key}_ci95_lo"] for r in ch_rows]
            hi = [r[f"qerror_std_{key}_ci95_hi"] for r in ch_rows]
            color = CHANNEL_STYLE[ch]["color"] if key == "upstream" else "#8a8a86"
            ax.plot(x, y, color=color, linestyle=style["linestyle"],
                     marker=style["marker"], markersize=4, linewidth=1.8,
                     label=style["label"], zorder=3)
            ax.fill_between(x, lo, hi, color=color, alpha=0.15, zorder=2)
        ax.set_xscale("log")
        ax.set_xticks(SIGNAL_LEVELS)
        ax.set_xticklabels([str(s) for s in SIGNAL_LEVELS], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("Signal level (12-bit DN)")
        ax.set_title(f"{ch} channel")
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)

    axes[0].set_ylabel("quantization error std (8-bit LSB, vs ideal real-valued result)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=1, frameon=False,
               bbox_to_anchor=(0.5, 1.14))
    fig.suptitle("gain.md §3.1 Goal A: quantization loss, upstream vs downstream gain", y=1.24)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_goal_b(rows: list[dict], path: Path) -> None:
    """delta_db hits -inf where the gain path fully saturates (std_out == 0,
    e.g. mult=4.0x at s>=1536) -- matplotlib would just drop those points and
    the line would vanish with no explanation, so they're floored to a
    visible sentinel and marked with a distinct 'saturated' marker instead."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)

    finite = [r["delta_db"] for r in rows if math.isfinite(r["delta_db"])]
    floor_y = min(finite) - 1.5

    ax.axhspan(-GOAL_B_TOLERANCE_DB, GOAL_B_TOLERANCE_DB, color="#8a8a86", alpha=0.12, zorder=0)
    ax.axhline(0, color="#8a8a86", linewidth=1, linestyle="--", zorder=1)

    for mult in GOAL_B_MULTIPLIERS:
        m_rows = sorted((r for r in rows if r["gain_mult"] == mult),
                         key=lambda r: r["signal_level"])
        x = [r["signal_level"] for r in m_rows]
        y = [r["delta_db"] if math.isfinite(r["delta_db"]) else floor_y for r in m_rows]
        sat_x = [r["signal_level"] for r in m_rows if not math.isfinite(r["delta_db"])]
        ax.plot(x, y, color=MULT_COLOR[mult], marker="o", markersize=4,
                 linewidth=2, label=f"{mult:.1f}x (Q8={round(mult*256)})", zorder=3)
        if sat_x:
            ax.scatter(sat_x, [floor_y] * len(sat_x), color=MULT_COLOR[mult],
                       marker="v", s=70, zorder=4, edgecolors="black", linewidths=0.8)

    ax.text(SIGNAL_LEVELS[-1], floor_y + 0.35, "fully saturated (std_out=0, SNR undefined) ▼",
            fontsize=8, color="#52514e", va="bottom", ha="right")
    ax.set_xscale("log")
    ax.set_xticks(SIGNAL_LEVELS)
    ax.set_xticklabels([str(s) for s in SIGNAL_LEVELS], rotation=45, ha="right")
    ax.set_xlabel("Signal level (12-bit DN)")
    ax.set_ylabel("SNR delta after gain (dB, out - in)")
    ax.set_title("gain.md §3.2 Goal B: SNR invariance under integer gain")
    ax.grid(True, which="both", axis="y", color="#e3e2dc", linewidth=0.8, zorder=0)
    ax.legend(loc="lower left", frameon=False, title="gain multiplier")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_goal_c(rows: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    for ch in ("R", "G", "B"):
        ch_rows = sorted((r for r in rows if r["channel"] == ch), key=lambda r: r["v12"])
        x = [r["v12"] for r in ch_rows]
        y = [r["diff_8bit_lsb"] for r in ch_rows]
        ax.plot(x, y, color=CHANNEL_STYLE[ch]["color"], linewidth=1.2,
                 label=f"{ch} channel", zorder=3)
    ax.axhline(0, color="#8a8a86", linewidth=1, zorder=1)
    ax.set_xlabel("v12 (raw 12-bit input, 0..4095)")
    ax.set_ylabel("diff_8bit_lsb (fused - separate, post >>4)")
    ax.set_title("gain.md §3.3 Goal C: fused vs separate gain, exhaustive sweep")
    ax.grid(True, color="#e3e2dc", linewidth=0.8, zorder=0)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=GOAL_A_REPEATS_DEFAULT,
                     help="applies to Goal A and Goal B (Goal C is exhaustive, no repeats)")
    sim_dir = Path(__file__).resolve().parent
    ap.add_argument("--out-a", type=Path, default=sim_dir / "gain_goalA_results.csv")
    ap.add_argument("--out-b", type=Path, default=sim_dir / "gain_goalB_results.csv")
    ap.add_argument("--out-c", type=Path, default=sim_dir / "gain_goalC_results.csv")
    ap.add_argument("--plot-a", type=Path, default=sim_dir / "gain_goalA_qerror.png")
    ap.add_argument("--plot-b", type=Path, default=sim_dir / "gain_goalB_snr_invariance.png")
    ap.add_argument("--plot-c", type=Path, default=sim_dir / "gain_goalC_fusion_diff.png")
    ap.add_argument("--no-plot", action="store_true")
    add_noise_model_args(ap)
    args = ap.parse_args()
    set_noise_model(args.a_q8, args.b_dn2)
    print(f"noise model: A_Q8={args.a_q8:.0f} B_DN2={args.b_dn2:.0f}")

    rows_a = run_goal_a(args.seed, args.repeats)
    rows_b = run_goal_b(args.seed, args.repeats)
    rows_c = run_goal_c()

    write_csv(rows_a, args.out_a)
    write_csv(rows_b, args.out_b)
    write_csv(rows_c, args.out_c)

    if not args.no_plot:
        plot_goal_a(rows_a, args.plot_a)
        plot_goal_b(rows_b, args.plot_b)
        plot_goal_c(rows_c, args.plot_c)

    n_fail_a = evaluate_goal_a(rows_a)
    evaluate_goal_b(rows_b)
    evaluate_goal_c(rows_c)

    print(f"\nResults written to {args.out_a}, {args.out_b}, {args.out_c}")
    if not args.no_plot:
        print(f"Plots written to {args.plot_a}, {args.plot_b}, {args.plot_c}")

    return 1 if n_fail_a else 0


if __name__ == "__main__":
    raise SystemExit(main())
