#!/usr/bin/env python3
"""PASCAL vs LOD vs Shuffle, arm comparison (mAP@50). Values as requested by
user -- mixed BLC per cell (PASCAL normal=BLC2, lowlight/adaptive=BLC1;
LOD normal=BLC4, lowlight/adaptive=BLC2; Shuffle all three=BLC2). See chat
for the per-cell BLC breakdown. No re-run -- values copied from
already-verified source CSVs.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "NanumGothic"
import matplotlib.pyplot as plt
import numpy as np

DATA = {
    "PASCAL":  {"normal": 0.8956, "lowlight": 0.8927, "adaptive": 0.8942},
    "LOD":     {"normal": 0.2995, "lowlight": 0.3810, "adaptive": 0.3810},
    "Shuffle": {"normal": 0.4808, "lowlight": 0.5050, "adaptive": 0.5036},
}
ARM_COLORS = {"normal": "#4C72B0", "lowlight": "#DD8452", "adaptive": "#55A868"}
PANEL_TITLES = {"PASCAL": "주간", "LOD": "야간", "Shuffle": "혼합"}

arms = ["normal", "lowlight", "adaptive"]
x = np.arange(len(arms))
BAR_W = 0.35  # thin bars so each ISP arm stays visually separated

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
for ax, dataset in zip(axes, DATA):
    ys = [DATA[dataset][a] for a in arms]
    bars = ax.bar(x, ys, width=BAR_W, color=[ARM_COLORS[a] for a in arms])
    for xi, v in zip(x, ys):
        ax.annotate(f"{v:.4f}", (xi, v), textcoords="offset points",
                     xytext=(0, 4), ha="center", fontsize=9)
    span = max(ys) - min(ys)
    pad = max(span * 0.6, 0.005)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_xticks(x)
    ax.set_xticklabels(arms)
    ax.set_ylabel("mAP")
    ax.set_title(PANEL_TITLES[dataset])
    ax.grid(axis="y", alpha=0.3)

fig.suptitle("ISP 비교")
fig.tight_layout()

out = Path(__file__).parent / "pascal_lod_arm_comparison.png"
fig.savefig(out, dpi=150)
print(f"wrote {out}")
