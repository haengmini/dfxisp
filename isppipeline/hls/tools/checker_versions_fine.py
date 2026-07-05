#!/usr/bin/env python3
"""checker_versions_fine.py -- finer-grained checker sweep + honest held-out CV.

Campaign : principled-v3 (2026-07-05), branch exp/principled-checker-rm-2026-07-05.
Track    : CHK refinement (goal command 2: 세분화 버전 + 실험 + 분석).

Motivation (self-review + Codex-review gaps folded in):
  G-CHK-1  The first pass evaluated dark-ratio only at the coarse grid
           {16,24,32,48,50,64}; whether the optimum sits BELOW 16 (nearer the
           black level / read-noise floor, as principle 3 argues) was untested.
           This module sweeps a FINE grid {8,10,12,14,16,18,20,24,28,32}.
  G-CHK-2  C1..C4 J/threshold were reported IN-SAMPLE (threshold fit on the same
           1150 frames it was scored on) -> optimistic. Every number here is
           ALSO reported as 5-fold cross-validated HELD-OUT recall/FT/J via
           checker_stat_sweep.kfold_cv (threshold chosen on train folds, scored
           on the held-out fold). This is the honest comparison.

All statistics are single-pass integer-derivable (dark-ratio = 256-bin histogram
CDF read-out; logmean = LOG2 LUT dot; entropy = -sum p log p), i.e. HW-friendly.

Usage:
  python3 tools/checker_versions_fine.py            # recompute from raw_bin
  python3 tools/checker_versions_fine.py --out results/checker_fine_2026-07-05.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

import checker_stat_sweep as S

DARK_FINE = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32]

# Mis-decision costs (ablation, analysis-2026-07-04 s4): mAP@0.5:0.95 loss.
C_MISS, C_FA = 0.1118, 0.0387


def risk(recall: float, ft: float) -> float:
    return 0.5 * ((1.0 - recall) * C_MISS + ft * C_FA)


def build_scores() -> dict[str, np.ndarray]:
    """One pass over raw_bin -> per-frame dark-ratio(fine grid), logmean, entropy,
    label. Same frame iteration order as checker_stat_sweep.compute()."""
    labels, logm, ent = [], [], []
    dark = {t: [] for t in DARK_FINE}
    for name, (d, label) in S.DATASETS.items():
        raw_dir = S.REPO / "data" / d / "raw_bin"
        img_dir = S.REPO / "data" / d / "images"
        for bp in sorted(raw_dir.glob("*.bin")):
            w, hgt = S.img_dims(img_dir, bp.stem)
            a = np.fromfile(bp, dtype="<u2")
            if a.size != w * hgt:
                w, hgt = w - w % 2, hgt - hgt % 2
            if a.size != w * hgt:
                continue
            v8 = (a.reshape(hgt, w) >> 8).astype(np.uint8)
            hist = np.bincount(v8.ravel(), minlength=256).astype(np.float64)
            n = hist.sum()
            cdf = np.cumsum(hist)
            for t in DARK_FINE:
                dark[t].append(cdf[t - 1] / n)
            logm.append(float(hist @ S.LOG2_LUT) / n)
            pi = hist[hist > 0] / n
            ent.append(float(-(pi * np.log2(pi)).sum()))
            labels.append(label)
    out = {f"dark{t}": np.asarray(dark[t]) for t in DARK_FINE}
    out["label"] = np.asarray(labels, float)
    out["logmean"] = np.asarray(logm)
    out["entropy"] = np.asarray(ent)
    return out


def row_for(score: np.ndarray, y: np.ndarray, name: str, rule: str) -> dict:
    """In-sample AUC/J + 5-fold held-out recall/FT/J + risk (both operating pts)."""
    op = S.op_points(score, y)
    ins_r, ins_f = S.eval_at(score, y, op["J_thr"])
    cv_r, cv_rs, cv_f, cv_fs, cv_t, cv_ts = S.kfold_cv(score, y, k=5, seed=0)
    return dict(name=name, rule=rule, auc=op["auc"],
                ins_thr=op["J_thr"], ins_recall=ins_r, ins_ft=ins_f,
                ins_j=ins_r - ins_f, ins_risk=risk(ins_r, ins_f),
                cv_recall=cv_r, cv_recall_sd=cv_rs, cv_ft=cv_f, cv_ft_sd=cv_fs,
                cv_j=cv_r - cv_f, cv_thr=cv_t, cv_thr_sd=cv_ts,
                cv_risk=risk(cv_r, cv_f))


def fixed_row(score: np.ndarray, y: np.ndarray, thr: float, name: str, rule: str) -> dict:
    """Fixed-threshold version (C0/C1/C2): no fitting, so in-sample == honest."""
    op = S.op_points(score, y)
    r, f = S.eval_at(score, y, thr)
    return dict(name=name, rule=rule, auc=op["auc"], ins_thr=thr,
                ins_recall=r, ins_ft=f, ins_j=r - f, ins_risk=risk(r, f),
                cv_recall=r, cv_recall_sd=0.0, cv_ft=f, cv_ft_sd=0.0,
                cv_j=r - f, cv_thr=thr, cv_thr_sd=0.0, cv_risk=risk(r, f))


def _fit_c4(d16, ent, y):
    """Grid-fit the C4 AND rule dark16>a AND entropy<b for max Youden J on the
    GIVEN (train) split. Returns (a, b)."""
    best, best_j = (0.62, 5.3), -1.0
    for a in np.round(np.arange(0.40, 0.85, 0.01), 3):
        pa = d16 > a
        for b in np.round(np.arange(4.0, 6.0, 0.05), 3):
            pred = pa & (ent < b)
            j = pred[y == 1].mean() - pred[y == 0].mean()
            if j > best_j:
                best_j, best = j, (a, b)
    return best


def nested_cv_c4(D, k=5, seed=0):
    """Honest nested CV for the C4 two-feature grid rule (Codex finding 6): fit
    (a,b) on train folds, evaluate on the held-out fold. Prevents the in-sample
    optimism of the original checker_versions.py C4 report."""
    y = D["label"]; d16 = D["dark16"]; ent = D["entropy"]
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    rec, ft = [], []
    for f in folds:
        tr = np.ones(len(y), bool); tr[f] = False
        a, b = _fit_c4(d16[tr], ent[tr], y[tr])
        pred = (d16[~tr] > a) & (ent[~tr] < b)
        rec.append(float(pred[y[~tr] == 1].mean()))
        ft.append(float(pred[y[~tr] == 0].mean()))
    r, f = float(np.mean(rec)), float(np.mean(ft))
    return r, f, r - f, risk(r, f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/checker_fine_2026-07-05.csv")
    args = ap.parse_args()

    D = build_scores()
    y = D["label"]
    npos, nneg = int((y == 1).sum()), int((y == 0).sum())
    print(f"# checker_versions_fine -- {npos} LOW_LIGHT + {nneg} NORMAL = {len(y)} frames\n")

    rows = []
    # (1) fine dark-threshold sweep: J-fit threshold, honest 5-fold CV.
    for t in DARK_FINE:
        rows.append(row_for(D[f"dark{t}"], y, f"dark{t}", f"dark{t} ratio (J-fit/CV)"))
    # (2) log-domain + entropy statistics, honest CV.
    rows.append(row_for(-D["logmean"], y, "logmean", "logmean (J-fit/CV)"))
    rows.append(row_for(-D["entropy"], y, "entropy", "entropy (J-fit/CV)"))
    # (3) the previously-recommended fixed operating points (honest by construction).
    fixed = [
        fixed_row(D["dark16"], y, 0.62, "C1_fixed", "dark16>0.62 (Youden J*, deployed)"),
        fixed_row(D["dark16"], y, 0.553, "C2_fixed", "dark16>0.553 (Bayes-opt)"),
    ]

    print("## Fine dark-threshold sweep + honest 5-fold CV (held-out)")
    print("| stat | AUC | in-sample J | CV held-out J | CV recall | CV FT | CV thr(±sd) | CV risk R |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['name']} | {r['auc']:.4f} | {r['ins_j']:.3f} | "
              f"{r['cv_j']:.3f} | {r['cv_recall']:.3f} | {r['cv_ft']:.3f} | "
              f"{r['cv_thr']:.3f}±{r['cv_thr_sd']:.3f} | {r['cv_risk']:.5f} |")

    print("\n## Fixed deployed operating points (no fitting -> honest)")
    print("| ver | rule | AUC | recall | FT | J | risk R |")
    print("|---|---|---|---|---|---|---|")
    for r in fixed:
        print(f"| {r['name']} | {r['rule']} | {r['auc']:.4f} | {r['ins_recall']:.3f} | "
              f"{r['ins_ft']:.3f} | {r['ins_j']:.3f} | {r['ins_risk']:.5f} |")

    # Honest nested-CV for the C4 two-feature rule (Codex finding 6).
    c4r, c4f, c4j, c4risk = nested_cv_c4(D)
    print(f"\n## C4 (dark16 AND entropy) honest NESTED-CV held-out")
    print(f"  recall={c4r:.3f} FT={c4f:.3f} J={c4j:.3f} risk={c4risk:.5f}")
    best_scalar_j = max(r["cv_j"] for r in rows)
    print(f"  best scalar CV J = {best_scalar_j:.3f} -> C4 nested-CV "
          f"{'BEATS' if c4j > best_scalar_j else 'does NOT beat'} best scalar "
          f"(delta {c4j - best_scalar_j:+.3f}) => reject-C4 "
          f"{'REFUTED' if c4j > best_scalar_j + 0.005 else 'HOLDS honestly'}")

    # best by honest held-out J and by held-out risk
    best_j = max(rows, key=lambda r: r["cv_j"])
    best_r = min(rows, key=lambda r: r["cv_risk"])
    print(f"\n## Best honest held-out J: {best_j['name']} "
          f"(CV J={best_j['cv_j']:.3f}, AUC={best_j['auc']:.4f})")
    print(f"## Lowest honest held-out risk: {best_r['name']} "
          f"(CV R={best_r['cv_risk']:.5f}, CV recall={best_r['cv_recall']:.3f}, "
          f"CV FT={best_r['cv_ft']:.3f})")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with out.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows + fixed)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
