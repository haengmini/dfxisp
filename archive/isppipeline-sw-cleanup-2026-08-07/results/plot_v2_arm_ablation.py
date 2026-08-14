#!/usr/bin/env python3
"""Reuse-and-visualize: v2 arm (default_ISP/lowlight_ISP) mAP ablation.

Source of numbers: map_ablation_nod100_2026-08-06.csv,
map_ablation_pascal100_2026-08-06.csv, rm_default_isp_top_csynth.rpt,
rm_lowlight_isp_top_csynth.rpt -- all copied verbatim from
~/workspace/dfxisp/.claude/worktrees/hw-interface-prompt (branch
docs/gat-doc-consistency-2026-08-06, 31 commits ahead of main, unmerged).
No pipeline was re-run here; this script only tabulates/plots existing,
already-validated numbers (see v2-arm-ablation-2026-08-06.md for the
original analysis and methodology).
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent


def load(name):
    with open(HERE / name) as f:
        return list(csv.DictReader(f))


def bar_map(rows, title, out_png, highlight=None):
    arms = [r["arm"] for r in rows]
    m5095 = [float(r["mAP_50_95"]) for r in rows]
    m50 = [float(r["mAP_50"]) for r in rows]

    x = range(len(arms))
    w = 0.35
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(arms)), 4.5))
    b1 = ax.bar([i - w / 2 for i in x], m5095, width=w, label="mAP@[.5:.95]", color="#4C72B0")
    b2 = ax.bar([i + w / 2 for i in x], m50, width=w, label="mAP@50", color="#DD8452")
    ax.set_xticks(list(x))
    ax.set_xticklabels(arms, rotation=30, ha="right")
    ax.set_ylabel("mAP")
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    for bars in (b1, b2):
        for rect in bars:
            h = rect.get_height()
            ax.annotate(f"{h:.4f}", (rect.get_x() + rect.get_width() / 2, h),
                        ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def bar_resource(out_png):
    # (BRAM_18K, DSP, FF, LUT) totals from csynth reports, Fmax = 1/3.650ns for both
    data = {
        "default_isp\n(rm_default_isp_top)": dict(BRAM_18K=4, DSP=28, FF=8794, LUT=12659),
        "lowlight_isp\n(rm_lowlight_isp_top)": dict(BRAM_18K=1, DSP=10, FF=2089, LUT=4150),
    }
    metrics = ["BRAM_18K", "DSP", "FF", "LUT"]
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.6))
    colors = ["#4C72B0", "#DD8452"]
    for ax, metric in zip(axes, metrics):
        vals = [data[k][metric] for k in data]
        bars = ax.bar(list(data.keys()), vals, color=colors)
        ax.set_title(metric)
        ax.tick_params(axis="x", rotation=30, labelsize=7)
        ax.grid(axis="y", alpha=0.3)
        for rect, v in zip(bars, vals):
            ax.annotate(str(v), (rect.get_x() + rect.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=8)
    fig.suptitle("csynth resource estimate -- both @ Fmax=273.97MHz (3.650ns, target 5.00ns)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    nod = load("map_ablation_nod100_2026-08-06.csv")
    pascal = load("map_ablation_pascal100_2026-08-06.csv")

    bar_map(nod, "split_nod (night, n=100) -- v1/v2 low-light arm comparison",
             HERE / "v2_arm_map_nod100_2026-08-06.png")
    bar_map(pascal, "pascal_split_100 (daylight, n=100) -- v1/v2 normal arm comparison",
             HERE / "v2_arm_map_pascal100_2026-08-06.png")
    bar_resource(HERE / "v2_arm_csynth_resource_2026-08-06.png")
    print("wrote 3 PNGs")


if __name__ == "__main__":
    main()
