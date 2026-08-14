#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/hls/tools/checker_oracle_analysis.py
# Date   : 2026-07-20
# Function: gate 2 analysis -- consumes checker_oracle_label.py's per-frame
#           output (results/oracle_label_shuffle_2026-07-20.csv) joined back
#           to the Shuffle_split manifest (for dark16), and answers the three
#           questions checker-strengthening-2026-07-10.md SS4 posed for #4:
#           (a) how much of C1's disagreement with the naive per-dataset
#               label (LOD=True/PASCAL=False regardless of frame content) is
#               actually a label artifact vs a genuine checker error,
#           (b) recall/false-trigger recomputed against the oracle label
#               (don't-care frames excluded) for C0/C1/adaptive-tau,
#           (c) re-estimated C_miss/C_FA implied by keeping the C1 threshold
#               (dark16>0.62) as the Bayes-risk posterior-neutral point,
#               under the oracle label instead of the naive one (reusing the
#               isotonic p(H1|dark16) calibration from checker_temporal.py
#               strategy #6, checker-strengthening-2026-07-10.md SS3.3).
# =============================================================================
"""checker_oracle_analysis: gate-2 label-artifact quantification + C_miss/C_FA.

Usage:
  python3 checker_oracle_analysis.py \
      --oracle ../results/oracle_label_shuffle_2026-07-20.csv \
      --manifest ../results/shuffle_split_2026-07-15.csv \
      --out ../results/checker-oracle-label-gate2-2026-07-20.md
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from checker_temporal import isotonic_fit

T = 0.62  # deployed C1 threshold, dark16 ratio


def to_bool(s: str):
    if s == "True":
        return True
    if s == "False":
        return False
    return None  # don't-care / missing


def load(oracle_path: Path, manifest_path: Path) -> list[dict]:
    dark16 = {}
    with manifest_path.open() as f:
        for r in csv.DictReader(f):
            dark16[r["stem"]] = float(r["dark16"])
    rows = []
    with oracle_path.open() as f:
        for r in csv.DictReader(f):
            r["dark16"] = dark16.get(r["stem"])
            r["oracle_lowlight_b"] = to_bool(r["oracle_lowlight"])
            r["gt_naive_b"] = to_bool(r["gt_lowlight_naive"])
            r["c0_b"] = to_bool(r["c0_verdict_lowlight"])
            r["c1_b"] = to_bool(r["c1_verdict_lowlight"])
            r["adaptive_b"] = to_bool(r["adaptive_verdict_lowlight"])
            rows.append(r)
    return rows


def rate(rows, cond, of) -> tuple[int, int, float]:
    denom = [r for r in rows if of(r)]
    num = [r for r in denom if cond(r)]
    return len(num), len(denom), (len(num) / len(denom) if denom else float("nan"))


def confusion(rows, verdict_key: str, label_key: str = "oracle_lowlight_b"):
    dc = [r for r in rows if r[label_key] is not None]
    recall_n, recall_d, recall = rate(dc, lambda r: r[verdict_key] is True,
                                       lambda r: r[label_key] is True)
    ft_n, ft_d, ft = rate(dc, lambda r: r[verdict_key] is True,
                           lambda r: r[label_key] is False)
    j = (recall - ft) if (recall_d and ft_d) else float("nan")
    return recall, recall_n, recall_d, ft, ft_n, ft_d, j


def youden_sweep(dark16: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """Best threshold (dark16 > t) by Youden's J over unique candidate
    thresholds. Returns (best_t, best_j, recall_at_best, ft_at_best)."""
    cands = np.unique(dark16)
    best = (None, -1.0, 0.0, 0.0)
    pos = y == 1
    neg = y == 0
    n_pos, n_neg = pos.sum(), neg.sum()
    for t in cands:
        pred = dark16 > t
        recall = (pred & pos).sum() / n_pos if n_pos else 0.0
        ft = (pred & neg).sum() / n_neg if n_neg else 0.0
        j = recall - ft
        if j > best[1]:
            best = (float(t), float(j), float(recall), float(ft))
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--oracle", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows = load(args.oracle, args.manifest)
    n = len(rows)
    n_dontcare = sum(1 for r in rows if r["oracle_lowlight_b"] is None)
    n_decided = n - n_dontcare

    lines = []
    lines.append("# Checker gate 2 -- oracle label redefinition (2026-07-20)\n")
    lines.append(f"n={n} frames (Shuffle_split), don't-care |delta F1|<=eps: "
                  f"{n_dontcare} ({n_dontcare/n:.1%}), decided: {n_decided}\n")

    # (a) agreement: oracle vs naive per-dataset label
    dc = [r for r in rows if r["oracle_lowlight_b"] is not None]
    agree = sum(1 for r in dc if r["oracle_lowlight_b"] == r["gt_naive_b"])
    agree_pct = f"{agree/len(dc):.1%}" if dc else "n/a"
    lines.append("## 1. Oracle vs naive per-dataset label\n")
    lines.append(f"decided frames n={len(dc)}: oracle agrees with naive "
                  f"gt_lowlight (LOD=True/PASCAL=False regardless of frame "
                  f"content) in {agree}/{len(dc)} ({agree_pct})\n")
    for src in ("lod", "pascal"):
        sub = [r for r in dc if r["source"] == src]
        if not sub:
            continue
        a = sum(1 for r in sub if r["oracle_lowlight_b"] == r["gt_naive_b"])
        lines.append(f"  - {src}: {a}/{len(sub)} ({a/len(sub):.1%}) agree "
                      f"(naive label: {sub[0]['gt_naive_b']})")
    lines.append("")

    # (b) label-artifact fraction of C1's residual disagreement with naive gt
    lines.append("## 2. Label-artifact fraction of C1's residual error (vs naive gt)\n")
    lines.append("| checker | residual errors (verdict!=naive gt) | artifact-confirmed (oracle==verdict) | don't-care | genuine error (oracle!=verdict) |")
    lines.append("|---|---|---|---|---|")
    for name, key in (("C0", "c0_b"), ("C1", "c1_b"), ("adaptive-tau", "adaptive_b")):
        resid = [r for r in rows if r[key] != r["gt_naive_b"]]
        artifact = sum(1 for r in resid if r["oracle_lowlight_b"] is not None and r["oracle_lowlight_b"] == r[key])
        dontcare = sum(1 for r in resid if r["oracle_lowlight_b"] is None)
        genuine = len(resid) - artifact - dontcare
        lines.append(f"| {name} | {len(resid)} | {artifact} ({artifact/len(resid):.1%}) | "
                      f"{dontcare} ({dontcare/len(resid):.1%}) | {genuine} ({genuine/len(resid):.1%}) |")
    lines.append("")

    # (c) recall/FT recomputed against oracle label (don't-care excluded)
    lines.append("## 3. Recall / false-trigger against oracle label (don't-care excluded)\n")
    lines.append("| checker | recall (oracle) | n | FT (oracle) | n | Youden J (oracle) | recall (naive gt, reference) | FT (naive gt, reference) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name, key in (("C0", "c0_b"), ("C1", "c1_b"), ("adaptive-tau", "adaptive_b")):
        recall, rn, rd, ft, fn_, fd, j = confusion(rows, key, "oracle_lowlight_b")
        recall_naive, _, _, ft_naive, _, _, _ = confusion(rows, key, "gt_naive_b")
        lines.append(f"| {name} | {recall:.3f} | {rn}/{rd} | {ft:.3f} | {fn_}/{fd} | "
                      f"{j:.3f} | {recall_naive:.3f} | {ft_naive:.3f} |")
    lines.append("")

    # (d) C_miss/C_FA re-estimate via isotonic p(H1|dark16=T)
    lines.append("## 4. C_miss/C_FA re-estimate at the deployed C1 threshold "
                  f"(dark16>{T})\n")
    d16_all = np.array([r["dark16"] for r in rows if r["dark16"] is not None])
    y_naive = np.array([1 if r["gt_naive_b"] else 0 for r in rows if r["dark16"] is not None])
    d16_dc = np.array([r["dark16"] for r in dc])
    y_oracle = np.array([1 if r["oracle_lowlight_b"] else 0 for r in dc])

    p_naive = float(isotonic_fit(d16_all, y_naive)(T))
    p_oracle = float(isotonic_fit(d16_dc, y_oracle)(T))
    cost_naive = (1 - p_naive) / p_naive if p_naive > 0 else float("inf")
    cost_oracle = (1 - p_oracle) / p_oracle if p_oracle > 0 else float("inf")
    lines.append(f"- p(H1|dark16={T}) under naive gt: **{p_naive:.3f}** "
                  f"(reference: checker-strengthening-2026-07-10.md SS3.3 measured 0.516 "
                  f"on the earlier proxy-label dataset -- this is the Shuffle_split "
                  f"real-RAW re-measurement)")
    lines.append(f"- p(H1|dark16={T}) under oracle label (don't-care excluded): **{p_oracle:.3f}**")
    lines.append(f"- implied C_miss/C_FA (Bayes-risk posterior-neutral-point condition "
                  f"p(H1\\|t*)=C_FA/(C_FA+C_miss)) under naive gt: **{cost_naive:.3f}**")
    lines.append(f"- implied C_miss/C_FA under oracle label: **{cost_oracle:.3f}**")
    lines.append("")

    # (e) Youden-optimal threshold under oracle label vs C1's 0.62
    best_t, best_j, best_recall, best_ft = youden_sweep(d16_dc, y_oracle)
    j_at_c1 = None
    pred_c1 = d16_dc > T
    pos = y_oracle == 1
    neg = y_oracle == 0
    if pos.sum() and neg.sum():
        j_at_c1 = (pred_c1 & pos).sum() / pos.sum() - (pred_c1 & neg).sum() / neg.sum()
    lines.append("## 5. Youden-J-optimal dark16 threshold under oracle label\n")
    lines.append(f"- oracle-optimal threshold: dark16 > {best_t:.4f}, J={best_j:.3f} "
                  f"(recall={best_recall:.3f}, FT={best_ft:.3f})")
    lines.append(f"- deployed C1 threshold (dark16>{T}) under oracle label: J={j_at_c1:.3f}")
    lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
