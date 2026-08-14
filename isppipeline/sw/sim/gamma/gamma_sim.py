#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/gamma/gamma_sim.py
# Date   : 2026-08-13
# Function: Implements the two parts of gamma.md's methodology that are
#           reproducible without external mAP/detector infrastructure:
#             (A) gamma.md Sec.3.2 bit-exact gate -- scalar canonical golden
#                 (gen_lowlight_isp_golden.lowlight_isp) vs the vectorised
#                 numpy proxy (lowlight_isp_pipeline.run_lowlight_isp), fuzzed
#                 across shapes/content modes/binning modes/tone modes.
#             (B) gamma.md Sec.2.1's DESIGN-INTENT claim itself -- that GAT is
#                 linear at the origin and so amplifies the read-noise floor
#                 less than gamma 2.0's steep near-origin slope -- measured
#                 directly by propagating the calibrated Poisson-Gaussian
#                 noise model through the real pipeline (binning -> BLC/gain
#                 -> CCM) up to the tone stage, swapping only the LUT.
#           The mAP ablation (gamma.md Sec.3.3/3.4) is NOT reproduced here: it
#           needs real detector inference over a real dataset, already run
#           and documented in gamma_report.md via the worktree-only
#           eval_map_isp*.py tools (gamma.md Sec.5 explicitly recommends reuse
#           over reimplementation there). This script covers the piece gamma.md
#           itself says the live tree can already reproduce (Sec.2.4 table's
#           two live-tree rows) plus the one methodological claim (Sec.2.1)
#           the existing gamma_report.md never actually measured -- it only
#           measured the end-task (mAP) outcome, not the noise-floor
#           mechanism the design intent is about.
# Sources: isppipeline/sw/sim/gamma/gamma.md Sec.2.1/Sec.3.2,
#          isppipeline/sw/gen_lowlight_isp_golden.py,
#          isppipeline/sw/lowlight_isp_pipeline.py,
#          isppipeline/sw/sim/binning/binning_sim.py (noise model + frame gen
#          reuse, same convention as blc_sim.py).
# =============================================================================
"""gamma_sim: bit-exact gate + read-noise-floor amplification measurement for
stage (5) tone curve (gamma.md Sec.3.2 and Sec.2.1).

Part A (bit-exact gate) mirrors verify_new_arm_pipelines.py's fuzz scheme
(7 shapes incl. 1x1/odd dims, 4 content modes, trials default 40) but is
reimplemented locally against this branch's own gen_lowlight_isp_golden.py /
lowlight_isp_pipeline.py (the worktree-only script is not copied into this
repo -- gamma.md Sec.2.4/Sec.5), scoped to lowlight_isp only (default_isp's
gate is out of gamma.md's scope).

Part B (noise-floor amplification) generates a flat true-scene signal at each
of several near-floor levels, adds the calibrated Poisson-Gaussian noise
(A_Q8/B_DN2, reused from binning_sim.py exactly as blc_sim.py does), and
carries the *same* noisy sample through the *same* binning -> BLC/gain -> CCM
stages used by the real pipeline (all imported unmodified from
gen_lowlight_isp_golden.py -- gamma.md Sec.3.2's "no algorithm
reimplementation" rule). Only the stage-(5) LUT is swapped between GAT/gamma
2.0/linear, so any difference in output std at the same input is attributable
to the LUT alone -- a direct test of Sec.2.1's claim, not a mAP proxy for it.

Usage:
    python3 gamma_sim.py [--seed N] [--trials N] [--repeats N]
                          [--out-dir PATH] [--no-plot]
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "binning"))  # sim/binning

from gen_lowlight_isp_golden import (  # noqa: E402
    BIN_BINNING, BIN_SUBSAMPLE, BLC_LEVEL12, RAW12_MAX, TONE_GAT, TONE_GAMMA,
    TONE_LINEAR, WB_B_Q8, WB_G_Q8, WB_R_Q8, binned_raw, ccm_channel,
    correct_channel, lowlight_isp, tone_lut,
)
import lowlight_isp_pipeline as LP  # noqa: E402
from binning_sim import (  # noqa: E402
    BW, BH, BX, BY, FRAME_H, FRAME_W, add_noise_model_args, gen_frame,
    set_noise_model,
)

TONE_LABEL = {TONE_GAT: "GAT", TONE_GAMMA: "GAMMA2.0", TONE_LINEAR: "LINEAR"}
TONE_COLOR = {TONE_GAT: "#2a78d6", TONE_GAMMA: "#e34948", TONE_LINEAR: "#8a8a86"}
CHANNEL_WB = {"R": WB_R_Q8, "G": WB_G_Q8, "B": WB_B_Q8}
CHANNEL_CCM_ROW = {"R": 0, "G": 1, "B": 2}

N_TRIALS_DEFAULT = 40             # gamma.md Sec.3.2 / Sec.2.4
N_REPEATS_DEFAULT = 4000          # noise-floor amplification, per signal level

# gamma.md Sec.3.2: "7 shapes (1x1, odd dims 포함)"
SHAPES = [(8, 8), (6, 4), (5, 3), (2, 2), (1, 1), (12, 10), (7, 9)]
# gamma.md Sec.3.2: "4 content modes (uniform random/near-floor/extremes/flat+noise)"
CONTENT_MODES = ("uniform_random", "near_floor", "extremes", "flat_noise")

# Near-floor true-scene levels either side of BLC_LEVEL12 (32) -- gamma.md
# Sec.2.1's claim is specifically about behaviour near the read-noise floor.
NOISE_FLOOR_LEVELS = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512]


# --- Part A: bit-exact gate (gamma.md Sec.3.2) -------------------------------

def _gen_raw12(rng: random.Random, w: int, h: int, mode: str) -> list[int]:
    if mode == "uniform_random":
        return [rng.randrange(0, 4096) for _ in range(w * h)]
    if mode == "near_floor":
        return [rng.randrange(0, 64) for _ in range(w * h)]
    if mode == "extremes":
        return [rng.choice([0, 32, 4095]) for _ in range(w * h)]
    base = rng.randrange(0, 4096)
    return [min(4095, max(0, base + rng.randrange(-40, 41))) for _ in range(w * h)]


def _scalar_lowlight(raw12: list[int], w: int, h: int, bin_mode: int,
                      tone_mode: int) -> np.ndarray:
    packed, bw, bh = lowlight_isp(raw12, w, h, bin_mode, tone_mode)
    out = np.empty((bh, bw, 3), dtype=np.uint8)
    for i, v in enumerate(packed):
        out[i // bw, i % bw] = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
    return out


def run_bitexact_gate(trials: int, seed: int) -> tuple[list[dict], int, int]:
    rng = random.Random(seed)
    rows: list[dict] = []
    checked_px = 0
    n_fail = 0

    for t in range(trials):
        w, h = SHAPES[t % len(SHAPES)]
        mode = CONTENT_MODES[t % len(CONTENT_MODES)]
        raw12 = _gen_raw12(rng, w, h, mode)
        raw16 = np.array([v << 4 for v in raw12], dtype=np.uint16)

        for bm in (BIN_BINNING, BIN_SUBSAMPLE):
            for tm in (TONE_GAT, TONE_GAMMA, TONE_LINEAR):
                got = LP.run_lowlight_isp(raw16, w, h, bm, tm)
                exp = _scalar_lowlight(raw12, w, h, bm, tm)
                match = bool(np.array_equal(got, exp))
                checked_px += int(got.size)
                n_fail += 0 if match else 1
                rows.append({
                    "trial": t, "w": w, "h": h, "content_mode": mode,
                    "bin_mode": "BINNING" if bm == BIN_BINNING else "SUBSAMPLE",
                    "tone_mode": TONE_LABEL[tm],
                    "n_channel_samples": int(got.size), "match": match,
                })
                if not match:
                    bad = np.argwhere(got != exp)[0]
                    print(f"  MISMATCH trial={t} {w}x{h} mode={mode} bin={bm} "
                          f"tone={TONE_LABEL[tm]} at {tuple(bad)}: "
                          f"got {got[tuple(bad)]} expected {exp[tuple(bad)]}")
    return rows, checked_px, n_fail


# --- Part B: read-noise-floor amplification (gamma.md Sec.2.1) --------------

def run_noise_floor(seed: int, n_repeats: int,
                     signal_levels: list[int]) -> list[dict]:
    rng = np.random.default_rng(seed)
    tone_luts = {tm: np.asarray(tone_lut(tm), dtype=np.float64)
                 for tm in (TONE_GAT, TONE_GAMMA, TONE_LINEAR)}
    rows: list[dict] = []

    for signal in signal_levels:
        ccm_vals = {"R": [], "G": [], "B": []}
        for _ in range(n_repeats):
            raw = gen_frame(float(signal), rng)
            r, g, b = binned_raw(raw, FRAME_W, FRAME_H, BW, BH, BX, BY, BIN_BINNING)
            r12 = correct_channel(r, WB_R_Q8)
            g12 = correct_channel(g, WB_G_Q8)
            b12 = correct_channel(b, WB_B_Q8)
            ccm_vals["R"].append(ccm_channel(0, r12, g12, b12))
            ccm_vals["G"].append(ccm_channel(1, r12, g12, b12))
            ccm_vals["B"].append(ccm_channel(2, r12, g12, b12))

        for ch in ("R", "G", "B"):
            cv = np.array(ccm_vals[ch], dtype=np.int64)
            for tm in (TONE_GAT, TONE_GAMMA, TONE_LINEAR):
                out = tone_luts[tm][cv]
                rows.append({
                    "signal_level": signal,
                    "channel": ch,
                    "tone_mode": TONE_LABEL[tm],
                    "n": n_repeats,
                    "ccm_input_mean": float(cv.mean()),
                    "output_mean": float(out.mean()),
                    "output_std": float(out.std(ddof=1)),
                })
    return rows


def evaluate_noise_floor(rows: list[dict]) -> None:
    """Informational only (gamma.md Sec.2.1 states a design claim, not a
    numeric pass/fail criterion like Sec.3.3's noise-band test) -- reports
    whether GAT's output std is actually lower than gamma 2.0's near the
    floor, per channel, at the levels below BLC_LEVEL12."""
    by_key = {(r["signal_level"], r["channel"], r["tone_mode"]): r for r in rows}
    channels = sorted({r["channel"] for r in rows})
    below_pedestal = sorted({r["signal_level"] for r in rows if r["signal_level"] <= BLC_LEVEL12})

    print(f"\n--- Sec.2.1 design-intent check: GAT output_std < GAMMA2.0 "
          f"output_std for signal <= BLC_LEVEL12 ({BLC_LEVEL12}) ---")
    n_holds = n_total = 0
    for s in below_pedestal:
        for ch in channels:
            gat = by_key[(s, ch, "GAT")]["output_std"]
            gamma = by_key[(s, ch, "GAMMA2.0")]["output_std"]
            holds = gat < gamma
            n_total += 1
            n_holds += holds
            print(f"  {'HOLDS' if holds else 'FAILS'}  s={s:4d} ch={ch}  "
                  f"std_GAT={gat:6.3f}  std_GAMMA2.0={gamma:6.3f}  "
                  f"ratio(GAT/GAMMA)={gat / gamma if gamma else float('nan'):5.2f}")
    print(f"  design intent holds at {n_holds}/{n_total} (signal,channel) "
          f"points at/below the pedestal.")


# --- output ------------------------------------------------------------------

def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_noise_floor(rows: list[dict], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=150, sharey=False)
    signals = sorted({r["signal_level"] for r in rows})

    for ax, ch in zip(axes, ("R", "G", "B")):
        for tm in (TONE_GAT, TONE_GAMMA, TONE_LINEAR):
            label = TONE_LABEL[tm]
            ch_rows = sorted(
                (r for r in rows if r["channel"] == ch and r["tone_mode"] == label),
                key=lambda r: r["signal_level"])
            x = [r["signal_level"] for r in ch_rows]
            y = [r["output_std"] for r in ch_rows]
            ax.plot(x, y, color=TONE_COLOR[tm], marker="o", markersize=4,
                     linewidth=1.8, label=label, zorder=3)
        ax.axvline(BLC_LEVEL12, color="#8a8a86", linewidth=1, linestyle=":",
                    zorder=1, label="BLC_LEVEL12 (pedestal)" if ch == "R" else "_nolegend_")
        ax.set_xscale("symlog", linthresh=8)
        ax.set_xlim(left=0)
        ax.set_xticks(signals)
        ax.set_xticklabels([str(s) for s in signals], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("True scene signal level (12-bit DN, pre-BLC)")
        ax.set_title(f"{ch} channel")
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)

    axes[0].set_ylabel("output_std (8-bit DN, post-tone-LUT)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("gamma.md Sec.2.1: read-noise-floor amplification by tone curve\n"
                  "(same noisy signal through binning->BLC/gain->CCM; only the LUT differs)",
                  y=1.03)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_lut_shapes(path: Path) -> None:
    """The mechanism behind Sec.2.1's claim, visualised directly: GAT's slope
    at the origin is finite (linear VST); GAMMA2.0 (sqrt) has infinite slope
    at 0. Inset zooms the near-floor region where that difference lives."""
    fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150)
    x = np.arange(RAW12_MAX + 1)
    for tm in (TONE_GAT, TONE_GAMMA, TONE_LINEAR):
        y = np.asarray(tone_lut(tm), dtype=np.float64)
        for ax in (ax_full, ax_zoom):
            ax.plot(x, y, color=TONE_COLOR[tm], linewidth=1.8, label=TONE_LABEL[tm])
    ax_full.axvline(BLC_LEVEL12, color="#8a8a86", linewidth=1, linestyle=":")
    ax_full.set_xlim(0, RAW12_MAX)
    ax_full.set_ylim(0, 255)
    ax_full.set_xlabel("CCM output (12-bit DN)")
    ax_full.set_ylabel("Tone LUT output (8-bit DN)")
    ax_full.set_title("Full range")
    ax_full.grid(True, color="#e3e2dc", linewidth=0.8)
    ax_full.legend(frameon=False)

    ax_zoom.axvline(BLC_LEVEL12, color="#8a8a86", linewidth=1, linestyle=":",
                     label="BLC_LEVEL12")
    ax_zoom.set_xlim(0, 256)
    ax_zoom.set_ylim(0, 80)
    ax_zoom.set_xlabel("CCM output (12-bit DN)")
    ax_zoom.set_title("Near-floor zoom (0-256)")
    ax_zoom.grid(True, color="#e3e2dc", linewidth=0.8)
    ax_zoom.legend(frameon=False)

    fig.suptitle("gamma.md Sec.2.1: tone LUT shapes -- GAT is linear at the origin, "
                 "GAMMA2.0 (sqrt) has infinite slope there")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trials", type=int, default=N_TRIALS_DEFAULT)
    ap.add_argument("--repeats", type=int, default=N_REPEATS_DEFAULT)
    sim_dir = Path(__file__).resolve().parent
    ap.add_argument("--out-dir", type=Path, default=sim_dir)
    ap.add_argument("--no-plot", action="store_true")
    add_noise_model_args(ap)
    args = ap.parse_args()
    set_noise_model(args.a_q8, args.b_dn2)
    print(f"noise model: A_Q8={args.a_q8:.0f} B_DN2={args.b_dn2:.0f}")

    print(f"\n=== Part A: bit-exact gate (gamma.md Sec.3.2), "
          f"{args.trials} trials x {len(SHAPES)} shapes x {len(CONTENT_MODES)} "
          f"content modes x 2 binning x 3 tone ===")
    gate_rows, checked_px, n_gate_fail = run_bitexact_gate(args.trials, args.seed)
    write_csv(gate_rows, args.out_dir / "gamma_bitexact_results.csv")
    if n_gate_fail == 0:
        print(f"[gamma_sim] PASS: {args.trials} trials, {checked_px} channel "
              f"samples, lowlight_isp_pipeline.run_lowlight_isp bit-exact with "
              f"the scalar gen_lowlight_isp_golden.lowlight_isp "
              f"(binning BINNING/SUBSAMPLE x tone GAT/GAMMA2.0/LINEAR)")
    else:
        print(f"[gamma_sim] FAIL: {n_gate_fail} mismatching (trial, bin, tone) "
              f"combinations out of {len(gate_rows)} -- see mismatches above.")

    print(f"\n=== Part B: read-noise-floor amplification (gamma.md Sec.2.1), "
          f"{len(NOISE_FLOOR_LEVELS)} signal levels x {args.repeats} repeats ===")
    nf_rows = run_noise_floor(args.seed, args.repeats, NOISE_FLOOR_LEVELS)
    write_csv(nf_rows, args.out_dir / "gamma_noise_floor_results.csv")
    evaluate_noise_floor(nf_rows)

    if not args.no_plot:
        plot_noise_floor(nf_rows, args.out_dir / "gamma_noise_floor.png")
        plot_lut_shapes(args.out_dir / "gamma_lut_shapes.png")
        print(f"\nPlots written to {args.out_dir / 'gamma_noise_floor.png'}, "
              f"{args.out_dir / 'gamma_lut_shapes.png'}")

    print(f"\nCSVs written to {args.out_dir / 'gamma_bitexact_results.csv'}, "
          f"{args.out_dir / 'gamma_noise_floor_results.csv'}")
    return 1 if n_gate_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
