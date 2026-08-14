#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/checker/checker_sim.py
# Date   : 2026-08-13
# Function: Implements checker.md Sec.3.1/3.2/3.3/3.5/3.6/3.7 -- everything
#           the checker module's reproduction plan needs that is pure numpy
#           statistics over dark_ratio, no detector inference. Sec.3.4
#           (C_miss/C_FA re-derivation via dual-arm YOLOv8n mAP ablation) is
#           a separate, much slower script (checker_map_ablation.py) whose
#           csv output this script reads for the Bayes-risk calculations in
#           Sec.3.5/3.6 -- if that csv isn't present yet, those two steps are
#           skipped with a warning rather than falling back to the original
#           campaign's C_miss/C_FA (checker.md Sec.1: inherited values are
#           reference only, never a silent substitute).
# Sources: isppipeline/sw/sim/checker/checker.md Sec.3, isppipeline/sw/checker.py,
#          isppipeline/hls/include/checker.hpp (C++, mirrored here in Python --
#          not importable), isppipeline/sw/sim/build_lod_test_eval_root.py,
#          isppipeline/sw/sim/build_pascal_test_eval_root.py.
# =============================================================================
"""checker_sim: dark-ratio statistics for the scene checker (checker.md Sec.3,
minus Sec.3.4's detector-based C_miss/C_FA re-derivation).

Part A (Sec.3.1, bit-exact gate): checker.py's dark_ratio()/selected_mode()
(pseudo-RAW16/shift8 domain, float mean) fuzzed against a local Python mirror
of checker.hpp::checker_select_mode()'s AUTO-mode verdict path (raw12 domain,
integer dark*100 > verdict_pct*n) -- the two use different arithmetic
(float vs integer) so this is a genuine cross-check, not a tautology.

Part B (Sec.3.2): loads dataset/{LOD,PASCAL}_test_eval/raw_bin (built by the
two build_*_test_eval_root.py scripts into isppipeline/sw/sim/checker/_cache/,
NOT dataset/ -- see checker.md Sec.2.8/Sec.4), treats LOD=H1(dark)/
PASCAL=H0(normal) as approximate frame labels, and computes dark16/dark50
per frame via one histogram pass per file (exact, not an approximation --
raw16>>8 < tau is an exact integer identity for raw16 < tau<<8).

Part C (Sec.3.3): the same per-frame histograms answer "what pixel threshold
tau_pixel separates the two sets best" for a whole sweep of tau candidates at
~zero extra cost (histogram built once per frame, sliced per tau).

Part D (Sec.3.5): ratio-cutoff search (Youden's J* and, if
checker_map_ablation.py's csv is present, Bayes-risk R*) at tau=16 (deployed)
and tau=tau_pixel* (Sec.3.3's own finding).

Part E (Sec.3.6): candidate-rule comparison table (C0/C1/C2 reference rows +
the new candidates from Parts C/D), no assumed winner (checker.md Sec.1).

Part F (Sec.3.7): hysteresis flapping simulation, synthetic jitter reused
from checker-principles' reported sigma.

Usage:
    python3 checker_sim.py [--seed N] [--trials N] [--lod-eval-root PATH]
                            [--pascal-eval-root PATH] [--costs-csv PATH]
                            [--out-dir PATH] [--no-plot]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw

import checker as C  # noqa: E402 -- the live SW mirror (checker.md Sec.2.6)

SIM_DIR = Path(__file__).resolve().parent
CACHE_DIR = SIM_DIR / "_cache"

# checker.md Sec.3.3: candidate pixel-level dark cutoffs (8-bit-equivalent).
# 16 (C1) and 50 (C0) are included so the deployed/legacy values sit inside
# the sweep, not as a special case.
CANDIDATE_TAU = [4, 8, 12, 16, 20, 24, 32, 40, 50, 64, 80, 96, 128]
TAU_C1, TAU_C0 = 16, 50

# checker.hpp (C++, live tree) -- mirrored here since Python can't import a
# C++ header. checker.md Sec.2.6.
HYST_ENTER_PCT, HYST_EXIT_PCT = 64, 60
DEPLOYED_RATIO_PCT = 62          # C1
C2_RATIO_PCT = 55.3              # checker-principles Bayes-opt, never deployed
C0_RATIO_PCT = 80.0              # dark50 era

# checker-principles-2026-07-05.md Sec.5.2: measured Schmitt-jitter p95, reused
# here purely as a synthetic-noise sigma for Sec.3.7 (checker.md notes this
# was itself a spatial-sampling-noise proxy, not a true temporal measurement).
JITTER_SIGMA_REF = 0.0055


# --- Part A: bit-exact gate (checker.md Sec.3.1) -----------------------------

def hw_checker_select_mode(raw12: np.ndarray, dark_pixel_threshold: int,
                            verdict_pct: int) -> str:
    """Local mirror of checker.hpp::checker_select_mode()'s AUTO-mode verdict
    path only (forced-mode branches and hyst_flags omitted -- checker.py's
    own mirror, fuzzed against this, doesn't implement them either). Integer
    arithmetic exactly as the HLS core: dark_pct100 = dark*100."""
    n = raw12.size
    dark = int(np.count_nonzero(raw12 < dark_pixel_threshold))
    return "lowlight" if dark * 100 > verdict_pct * n else "normal"


def run_bitexact_gate(trials: int, seed: int) -> tuple[list[dict], int]:
    rng = np.random.default_rng(seed)
    shapes = [(8, 8), (6, 4), (5, 3), (2, 2), (1, 1), (12, 10), (7, 9), (64, 64)]
    modes = ("uniform_random", "near_floor", "extremes", "near_boundary")
    boundary_fracs = [0.55, 0.60, 0.615, 0.62, 0.625, 0.65]
    rows: list[dict] = []
    n_fail = 0

    for t in range(trials):
        w, h = shapes[t % len(shapes)]
        n = w * h
        mode = modes[t % len(modes)]
        if mode == "uniform_random":
            raw12 = rng.integers(0, 4096, size=n)
        elif mode == "near_floor":
            raw12 = rng.integers(0, 64, size=n)
        elif mode == "extremes":
            raw12 = rng.choice([0, 255, 4095], size=n)
        else:  # near_boundary -- deliberately near the 62% verdict edge,
               # mirroring checker-c1-deploy's own 39/64 vs 40/64 smoke case
            frac = rng.choice(boundary_fracs)
            n_dark = int(round(frac * n))
            raw12 = np.concatenate([np.zeros(n_dark, dtype=np.int64),
                                     np.full(n - n_dark, 4095, dtype=np.int64)])
            rng.shuffle(raw12)
        raw12 = raw12.astype(np.int64)
        raw16 = (raw12 << 4).astype(np.uint16)

        exp = hw_checker_select_mode(raw12, dark_pixel_threshold=256, verdict_pct=62)
        got = C.selected_mode(raw16, w, h)
        match = exp == got
        n_fail += 0 if match else 1
        rows.append({"trial": t, "w": w, "h": h, "content_mode": mode,
                      "hw_mirror": exp, "sw_checker_py": got, "match": match})
        if not match:
            print(f"  MISMATCH trial={t} {w}x{h} mode={mode}: "
                  f"hw_mirror={exp} checker.py={got}")
    return rows, n_fail


# --- shared data loading (checker.md Sec.3.2) --------------------------------

def frame_histogram(bin_path: Path) -> tuple[np.ndarray, int]:
    """One pass per file: 256-bucket histogram of the 8-bit-equivalent value
    (raw16>>8). dark_ratio at ANY 8-bit threshold tau is then an exact O(1)
    lookup: mean(raw16 < tau<<8) == mean((raw16>>8) < tau) == cumsum(hist)[tau-1]/n
    (exact integer floor-division identity, not an approximation)."""
    raw16 = np.fromfile(bin_path, dtype="<u2")
    buckets = (raw16 >> 8).astype(np.uint8)
    hist = np.bincount(buckets, minlength=256).astype(np.int64)
    return hist, int(raw16.size)


def load_dataset_hists(eval_root: Path) -> list[tuple[str, np.ndarray, int]]:
    rows = []
    for p in sorted((eval_root / "raw_bin").glob("*.bin")):
        hist, n = frame_histogram(p)
        rows.append((p.stem, hist, n))
    return rows


def dark_ratio_at_tau(hist: np.ndarray, n: int, tau: int) -> float:
    return float(np.cumsum(hist)[tau - 1]) / n


# --- AUC (Mann-Whitney, no scipy dependency) ---------------------------------

def _rank_avg(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="mergesort")
    sorted_a = a[order]
    ranks = np.empty(len(a), dtype=np.float64)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def auc_score(pos: np.ndarray, neg: np.ndarray) -> float:
    """ROC AUC via the Mann-Whitney U statistic -- P(pos score > neg score),
    ties broken at 0.5 (standard AUC tie handling)."""
    all_scores = np.concatenate([pos, neg])
    ranks = _rank_avg(all_scores)
    n_pos, n_neg = len(pos), len(neg)
    sum_ranks_pos = ranks[:n_pos].sum()
    u = sum_ranks_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


# --- Part B/C: dark16/50 discriminability + tau sweep (Sec.3.2/3.3) ---------

def run_dark_discrimination(lod_hists, pascal_hists, taus: list[int]) -> dict:
    """Returns per-tau dark_ratio arrays for LOD/PASCAL plus their AUC --
    Sec.3.2's dark16/dark50 pair is just two entries of this same sweep."""
    per_tau = {}
    for tau in taus:
        lod_vals = np.array([dark_ratio_at_tau(h, n, tau) for _, h, n in lod_hists])
        pas_vals = np.array([dark_ratio_at_tau(h, n, tau) for _, h, n in pascal_hists])
        auc = auc_score(lod_vals, pas_vals)
        per_tau[tau] = {"lod": lod_vals, "pascal": pas_vals, "auc": auc}
    return per_tau


# --- Part D: ratio-cutoff search (Sec.3.5) -----------------------------------

def roc_curve(lod_vals: np.ndarray, pascal_vals: np.ndarray,
              n_points: int = 2001) -> dict:
    grid = np.linspace(0.0, 1.0, n_points)
    recall = np.array([(lod_vals > r).mean() for r in grid])
    ft = np.array([(pascal_vals > r).mean() for r in grid])
    return {"r": grid, "recall": recall, "ft": ft}


def youden_optimum(roc: dict) -> tuple[float, float]:
    j = roc["recall"] - roc["ft"]
    i = int(np.argmax(j))
    return float(roc["r"][i]), float(j[i])


def bayes_optimum(roc: dict, c_miss: float, c_fa: float) -> tuple[float, float]:
    miss = 1.0 - roc["recall"]
    risk = 0.5 * (miss * c_miss + roc["ft"] * c_fa)
    i = int(np.argmin(risk))
    return float(roc["r"][i]), float(risk[i])


def risk_at(lod_vals: np.ndarray, pascal_vals: np.ndarray, tau_pixel: int,
            ratio_pct: float, c_miss: float, c_fa: float) -> dict:
    r = ratio_pct / 100.0
    recall = float((lod_vals > r).mean())
    ft = float((pascal_vals > r).mean())
    miss = 1.0 - recall
    risk = 0.5 * (miss * c_miss + ft * c_fa)
    return {"tau_pixel": tau_pixel, "ratio_pct": ratio_pct, "recall": recall,
            "ft": ft, "j": recall - ft, "r_risk": risk}


# --- Part F: hysteresis flapping (Sec.3.7) -----------------------------------

def simulate_flapping(seed: int, ratio_center_pct: float, enter_pct: float,
                       exit_pct: float, sigma: float, n_frames: int = 100,
                       n_repeats: int = 50) -> dict:
    """Synthetic dark_ratio(t) = center + AR(0) gaussian jitter sigma. Counts
    mode flips for a single threshold (center) vs the Schmitt band
    [exit, enter]. checker.md Sec.3.7: sigma is a spatial-sampling-noise
    proxy inherited from checker-principles, not a fresh temporal measurement
    (kept as a documented limitation, not silently fixed here)."""
    rng = np.random.default_rng(seed)
    center = ratio_center_pct / 100.0
    enter, exit_ = enter_pct / 100.0, exit_pct / 100.0
    single_flaps, hyst_flaps = [], []

    for _ in range(n_repeats):
        series = np.clip(rng.normal(center, sigma, n_frames), 0.0, 1.0)

        single_mode = series[0] > center
        flips = 0
        for v in series[1:]:
            mode = v > center
            flips += mode != single_mode
            single_mode = mode
        single_flaps.append(flips)

        hyst_mode = series[0] > center
        flips = 0
        for v in series[1:]:
            if hyst_mode and v < exit_:
                hyst_mode = False
                flips += 1
            elif not hyst_mode and v > enter:
                hyst_mode = True
                flips += 1
        hyst_flaps.append(flips)

    return {"single_mean": float(np.mean(single_flaps)),
            "hyst_mean": float(np.mean(hyst_flaps)),
            "single_max": int(np.max(single_flaps)),
            "hyst_max": int(np.max(hyst_flaps))}


# --- output helpers -----------------------------------------------------------

def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_costs_csv(path: Path) -> tuple[float, float] | None:
    """Reads checker_map_ablation.py's one-line csv (checker.md Sec.5:
    'C_miss'/C_FA in a format checker_sim.py's Sec.3.5 can read'). Returns
    None if not present -- Sec.3.5/3.6's Bayes-risk parts are then skipped,
    not silently backfilled with the original campaign's inherited values."""
    if not path.exists():
        return None
    with path.open() as f:
        row = next(csv.DictReader(f))
    return float(row["c_miss"]), float(row["c_fa"])


# --- plots ---------------------------------------------------------------------

def plot_tau_sweep(per_tau: dict, path: Path) -> None:
    taus = sorted(per_tau.keys())
    aucs = [per_tau[t]["auc"] for t in taus]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    ax.plot(taus, aucs, color="#2a78d6", marker="o", markersize=5, linewidth=1.8)
    best = taus[int(np.argmax(aucs))]
    ax.axvline(TAU_C1, color="#2e8b57", linestyle=":", linewidth=1.2,
               label=f"tau=16 (C1)")
    ax.axvline(TAU_C0, color="#8a8a86", linestyle=":", linewidth=1.2,
               label=f"tau=50 (C0)")
    ax.axvline(best, color="#e34948", linestyle="--", linewidth=1.2,
               label=f"tau_pixel* = {best} (this data)")
    ax.set_xscale("log")
    ax.set_xticks(taus)
    ax.set_xticklabels([str(t) for t in taus], rotation=60, ha="right", fontsize=8)
    ax.set_xlabel("tau_pixel (8-bit-equivalent dark cutoff)")
    ax.set_ylabel("AUC (dark_ratio_tau separating LOD vs PASCAL)")
    ax.set_title("checker.md Sec.3.3: pixel-threshold sweep\n"
                  "(dotted = original campaign's C0/C1 reference points, dashed = this data's optimum)")
    ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_dark_distributions(per_tau: dict, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150)
    for ax, tau, label in zip(axes, (TAU_C1, TAU_C0), ("dark16 (tau=16)", "dark50 (tau=50)")):
        lod_vals, pas_vals = per_tau[tau]["lod"], per_tau[tau]["pascal"]
        bins = np.linspace(0, 1, 40)
        ax.hist(pas_vals, bins=bins, alpha=0.6, color="#8a8a86", label="PASCAL (H0)")
        ax.hist(lod_vals, bins=bins, alpha=0.6, color="#2a78d6", label="LOD (H1)")
        ax.set_xlabel("dark_ratio")
        ax.set_title(f"{label}, AUC={per_tau[tau]['auc']:.4f}")
        ax.grid(True, color="#e3e2dc", linewidth=0.8)
        ax.legend(frameon=False)
    axes[0].set_ylabel("frame count")
    fig.suptitle("checker.md Sec.3.2: dark_ratio distributions, LOD vs PASCAL")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_roc(rocs: dict[str, dict], optima: dict[str, dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7), dpi=150)
    colors = {"tau16": "#2a78d6", "tau_star": "#e34948"}
    for key, roc in rocs.items():
        ax.plot(roc["ft"], roc["recall"], color=colors[key], linewidth=1.8,
                label=f"ROC ({key})")
        for opt_key, marker in (("r_J", "o"), ("r_R", "^")):
            opt = optima.get(f"{key}_{opt_key}")
            if opt is not None:
                i = int(np.argmin(np.abs(roc["r"] - opt["r"])))
                ax.scatter(roc["ft"][i], roc["recall"][i], color=colors[key],
                           marker=marker, s=80, zorder=5,
                           label=f"{key} {opt_key}* r={opt['r']:.3f}")
    ax.plot([0, 1], [0, 1], color="#8a8a86", linestyle=":", linewidth=1)
    ax.set_xlabel("FT = P(dark_ratio > r | PASCAL)")
    ax.set_ylabel("recall = P(dark_ratio > r | LOD)")
    ax.set_title("checker.md Sec.3.5: ROC + Youden(o)/Bayes-risk(^) optima")
    ax.grid(True, color="#e3e2dc", linewidth=0.8)
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_candidates(rows: list[dict], path: Path) -> None:
    labels = [r["label"] for r in rows]
    recalls = [r["recall"] for r in rows]
    fts = [r["ft"] for r in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    w = 0.35
    ax.bar(x - w / 2, recalls, w, color="#2a78d6", label="recall (LOD)")
    ax.bar(x + w / 2, fts, w, color="#e34948", label="FT (PASCAL)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("proxy rate")
    ax.set_title("checker.md Sec.3.6: candidate rules, recall vs FT proxy\n"
                  "(no assumed winner -- see checker_report.md)")
    ax.grid(True, axis="y", color="#e3e2dc", linewidth=0.8)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --- main ----------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--lod-eval-root", type=Path, default=CACHE_DIR / "LOD_test_eval")
    ap.add_argument("--pascal-eval-root", type=Path, default=CACHE_DIR / "PASCAL_test_eval")
    ap.add_argument("--costs-csv", type=Path, default=SIM_DIR / "checker_costs_derived.csv")
    ap.add_argument("--out-dir", type=Path, default=SIM_DIR)
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    out = args.out_dir

    # Part A
    print("=== Part A: bit-exact gate (checker.md Sec.3.1) ===")
    gate_rows, n_gate_fail = run_bitexact_gate(args.trials, args.seed)
    write_csv(gate_rows, out / "checker_bitexact_results.csv")
    print(f"[checker_sim] {'PASS' if n_gate_fail == 0 else 'FAIL'}: "
          f"{args.trials} trials, {n_gate_fail} mismatch(es)")

    # Part B/C
    print("\n=== Part B/C: dark_ratio discrimination + tau sweep "
          "(checker.md Sec.3.2/3.3) ===")
    if not (args.lod_eval_root / "raw_bin").exists() or not (args.pascal_eval_root / "raw_bin").exists():
        print(f"[checker_sim] FATAL: eval roots not found at "
              f"{args.lod_eval_root} / {args.pascal_eval_root} -- run "
              f"build_lod_test_eval_root.py / build_pascal_test_eval_root.py first.")
        return 1
    lod_hists = load_dataset_hists(args.lod_eval_root)
    pascal_hists = load_dataset_hists(args.pascal_eval_root)
    print(f"loaded {len(lod_hists)} LOD frames, {len(pascal_hists)} PASCAL frames")

    per_tau = run_dark_discrimination(lod_hists, pascal_hists, CANDIDATE_TAU)
    tau_star = max(CANDIDATE_TAU, key=lambda t: per_tau[t]["auc"])
    tau_rows = [{"tau_pixel": t, "auc": per_tau[t]["auc"],
                 "lod_mean": float(per_tau[t]["lod"].mean()),
                 "pascal_mean": float(per_tau[t]["pascal"].mean())}
                for t in CANDIDATE_TAU]
    write_csv(tau_rows, out / "checker_tau_sweep_results.csv")
    for r in tau_rows:
        marker = " <- C1" if r["tau_pixel"] == TAU_C1 else (" <- C0" if r["tau_pixel"] == TAU_C0 else "")
        print(f"  tau={r['tau_pixel']:4d}  AUC={r['auc']:.4f}  "
              f"LOD_mean={r['lod_mean']:.4f}  PASCAL_mean={r['pascal_mean']:.4f}{marker}")
    print(f"tau_pixel* (this data) = {tau_star} (AUC={per_tau[tau_star]['auc']:.4f})")

    dark_rows = []
    for stem, h, n in lod_hists:
        dark_rows.append({"stem": stem, "dataset": "LOD", "label": "H1",
                           "dark16": dark_ratio_at_tau(h, n, TAU_C1),
                           "dark50": dark_ratio_at_tau(h, n, TAU_C0)})
    for stem, h, n in pascal_hists:
        dark_rows.append({"stem": stem, "dataset": "PASCAL", "label": "H0",
                           "dark16": dark_ratio_at_tau(h, n, TAU_C1),
                           "dark50": dark_ratio_at_tau(h, n, TAU_C0)})
    write_csv(dark_rows, out / "checker_dark_discrim_results.csv")

    # Part D (Sec.3.5)
    print("\n=== Part D: ratio-cutoff search (checker.md Sec.3.5) ===")
    roc_tau16 = roc_curve(per_tau[TAU_C1]["lod"], per_tau[TAU_C1]["pascal"])
    roc_taustar = roc_curve(per_tau[tau_star]["lod"], per_tau[tau_star]["pascal"])
    r_J_tau16, j_tau16 = youden_optimum(roc_tau16)
    r_J_taustar, j_taustar = youden_optimum(roc_taustar)
    print(f"  tau=16 (C1's pixel cutoff): r_J* = {r_J_tau16*100:.2f}%  (J={j_tau16:.4f}), "
          f"deployed C1 = {DEPLOYED_RATIO_PCT}%")
    print(f"  tau=tau_pixel*={tau_star}:  r_J* = {r_J_taustar*100:.2f}%  (J={j_taustar:.4f})")

    costs = load_costs_csv(args.costs_csv)
    optima = {"tau16_r_J": {"r": r_J_tau16}, "tau_star_r_J": {"r": r_J_taustar}}
    cutoff_rows = [
        {"tau_pixel": TAU_C1, "criterion": "youden_J", "r_pct": r_J_tau16 * 100, "score": j_tau16},
        {"tau_pixel": tau_star, "criterion": "youden_J", "r_pct": r_J_taustar * 100, "score": j_taustar},
    ]
    if costs is None:
        print(f"  [checker_sim] costs csv not found at {args.costs_csv} -- "
              f"Bayes-risk optima (r_R*) skipped. Run checker_map_ablation.py "
              f"first for the full Sec.3.5/3.6 result (checker.md Sec.1: not "
              f"backfilled with the original campaign's C_miss/C_FA).")
        r_R_tau16 = r_R_taustar = None
    else:
        c_miss, c_fa = costs
        r_R_tau16, risk_tau16 = bayes_optimum(roc_tau16, c_miss, c_fa)
        r_R_taustar, risk_taustar = bayes_optimum(roc_taustar, c_miss, c_fa)
        print(f"  [re-derived costs] C_miss={c_miss:.4f} C_FA={c_fa:.4f} "
              f"(ratio {c_miss / c_fa:.2f}:1)")
        print(f"  tau=16:            r_R* = {r_R_tau16*100:.2f}%  (R={risk_tau16:.5f}), "
              f"reference C2 = {C2_RATIO_PCT}%")
        print(f"  tau=tau_pixel*={tau_star}: r_R* = {r_R_taustar*100:.2f}%  (R={risk_taustar:.5f})")
        optima["tau16_r_R"] = {"r": r_R_tau16}
        optima["tau_star_r_R"] = {"r": r_R_taustar}
        cutoff_rows += [
            {"tau_pixel": TAU_C1, "criterion": "bayes_risk", "r_pct": r_R_tau16 * 100, "score": risk_tau16},
            {"tau_pixel": tau_star, "criterion": "bayes_risk", "r_pct": r_R_taustar * 100, "score": risk_taustar},
        ]
    write_csv(cutoff_rows, out / "checker_cutoff_search_results.csv")

    # Part E (Sec.3.6): candidate comparison table
    print("\n=== Part E: candidate rule comparison (checker.md Sec.3.6) ===")
    candidates = [
        ("C0 (50, 80%)", TAU_C0, C0_RATIO_PCT),
        ("C1 (16, 62%)", TAU_C1, DEPLOYED_RATIO_PCT),
        ("C2 (16, 55.3%)", TAU_C1, C2_RATIO_PCT),
        (f"(16, r_J*={r_J_tau16*100:.1f}%)", TAU_C1, r_J_tau16 * 100),
        (f"(tau*={tau_star}, r_J*={r_J_taustar*100:.1f}%)", tau_star, r_J_taustar * 100),
    ]
    if costs is not None:
        candidates += [
            (f"(16, r_R*={r_R_tau16*100:.1f}%)", TAU_C1, r_R_tau16 * 100),
            (f"(tau*={tau_star}, r_R*={r_R_taustar*100:.1f}%)", tau_star, r_R_taustar * 100),
        ]
    candidate_rows = []
    for label, tau, ratio_pct in candidates:
        lod_vals, pas_vals = per_tau[tau]["lod"], per_tau[tau]["pascal"]
        if costs is not None:
            c_miss, c_fa = costs
        else:
            c_miss, c_fa = float("nan"), float("nan")
        stats = risk_at(lod_vals, pas_vals, tau, ratio_pct, c_miss, c_fa)
        row = {"label": label, **stats}
        candidate_rows.append(row)
        print(f"  {label:32s} recall={stats['recall']:.4f} FT={stats['ft']:.4f} "
              f"J={stats['j']:.4f} R={stats['r_risk']:.5f}")
    write_csv(candidate_rows, out / "checker_candidates_results.csv")
    if candidate_rows:
        best_j = max(candidate_rows, key=lambda r: r["j"])
        print(f"  best J in this data: {best_j['label']} (J={best_j['j']:.4f})")
        if costs is not None:
            best_r = min(candidate_rows, key=lambda r: r["r_risk"])
            print(f"  best R in this data: {best_r['label']} (R={best_r['r_risk']:.5f})")

    # Part F (Sec.3.7)
    print("\n=== Part F: hysteresis flapping (checker.md Sec.3.7) ===")
    flap_rows = []
    for name, enter, exit_, center in (
        ("C0_single", C0_RATIO_PCT, C0_RATIO_PCT, C0_RATIO_PCT),
        ("C1_single", DEPLOYED_RATIO_PCT, DEPLOYED_RATIO_PCT, DEPLOYED_RATIO_PCT),
        ("C1_schmitt", HYST_ENTER_PCT, HYST_EXIT_PCT, DEPLOYED_RATIO_PCT),
    ):
        res = simulate_flapping(args.seed, center, enter, exit_, JITTER_SIGMA_REF)
        flap_rows.append({"policy": name, "enter_pct": enter, "exit_pct": exit_, **res})
        print(f"  {name:12s} mean_flaps={res['hyst_mean']:.2f} max_flaps={res['hyst_max']}")
    write_csv(flap_rows, out / "checker_flapping_results.csv")

    # Plots
    if not args.no_plot:
        plot_tau_sweep(per_tau, out / "checker_tau_sweep.png")
        plot_dark_distributions(per_tau, out / "checker_dark_distributions.png")
        rocs = {"tau16": roc_tau16, "tau_star": roc_taustar}
        plot_roc(rocs, optima, out / "checker_roc.png")
        if candidate_rows:
            plot_candidates(candidate_rows, out / "checker_candidates.png")
        print(f"\nPlots written to {out}")

    print(f"\nCSVs written to {out}")
    return 1 if n_gate_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
