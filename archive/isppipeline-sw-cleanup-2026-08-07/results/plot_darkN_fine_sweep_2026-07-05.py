#!/usr/bin/env python3
"""dark8~32 fine sweep with 5-fold held-out CV (checker_fine_2026-07-05.csv).
Source: ~/workspace/dfxisp/.../results/checker_fine_2026-07-05.csv,
principled-v3-refinement-2026-07-05.md. No re-run -- visualization only.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "NanumGothic"
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV = HERE / "checker_fine_2026-07-05.csv"

N_VALUES = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32]
DEPLOYED_N = 16
BEST_N = 8


def load():
    rows = {r["name"]: r for r in csv.DictReader(open(CSV))}
    auc = []
    for n in N_VALUES:
        r = rows[f"dark{n}"]
        auc.append(float(r["auc"]))
    return auc


def color_for(n):
    if n == DEPLOYED_N:
        return "#C44E52"  # red: deployed
    if n == BEST_N:
        return "#55A868"  # green: best held-out J
    return "#4C72B0"


def main():
    auc = load()
    x = list(range(len(N_VALUES)))

    fig, ax = plt.subplots(figsize=(7, 4.5))

    colors = [color_for(n) for n in N_VALUES]
    ax.plot(x, auc, color="#999999", linewidth=1, zorder=1)
    ax.scatter(x, auc, c=colors, s=70, zorder=2)
    for xi, v in zip(x, auc):
        ax.annotate(f"{v:.4f}", (xi, v), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"dark{n}" for n in N_VALUES], rotation=0, fontsize=8)
    ax.set_ylabel("AUC")
    ax.grid(alpha=0.3)

    fig.suptitle("darkN 비교")
    fig.tight_layout()

    out = HERE / "darkN_fine_sweep_2026-07-05.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
