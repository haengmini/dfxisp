#!/usr/bin/env python3
"""C0-C4 checker rule comparison across AUC/Recall/FT/J.
Source: ~/workspace/dfxisp/.../results/checker-principled-versions-2026-07-05.md
(1150-frame full-sweep campaign, tools/checker_versions.py). No re-run --
visualization of already-published numbers. C1 (dark16>0.62) is the deployed
rule, highlighted.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "NanumGothic"
import matplotlib.pyplot as plt
import numpy as np

RULES = ["C0", "C1", "C2", "C3", "C4"]
LABELS = {
    "C0": "C0\ndark50>0.80",
    "C1": "C1\ndark16>0.62",
    "C2": "C2\ndark16>0.553",
    "C3": "C3\nlogmean",
    "C4": "C4\ndark16+entropy",
}
DATA = {
    "AUC":    {"C0": 0.9632, "C1": 0.9766, "C2": 0.9766, "C3": 0.9780, "C4": 0.9784},
    "Recall": {"C0": 0.918,  "C1": 0.936,  "C2": 0.965,  "C3": 0.939,  "C4": 0.958},
    "FT":     {"C0": 0.125,  "C1": 0.089,  "C2": 0.134,  "C3": 0.090,  "C4": 0.101},
    "J":      {"C0": 0.793,  "C1": 0.847,  "C2": 0.831,  "C3": 0.849,  "C4": 0.857},
}
DEPLOYED = "C1"
BAR_COLOR = "#4C72B0"
DEPLOYED_COLOR = "#C44E52"

x = np.arange(len(RULES))
BAR_W = 0.5

fig, axes = plt.subplots(1, 4, figsize=(15, 4.2))
for ax, metric in zip(axes, DATA):
    ys = [DATA[metric][r] for r in RULES]
    colors = [DEPLOYED_COLOR if r == DEPLOYED else BAR_COLOR for r in RULES]
    bars = ax.bar(x, ys, width=BAR_W, color=colors)
    for xi, v in zip(x, ys):
        ax.annotate(f"{v:.3f}", (xi, v), textcoords="offset points",
                     xytext=(0, 4), ha="center", fontsize=8)
    span = max(ys) - min(ys)
    pad = max(span * 0.35, 0.01)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_xticks(x)
    ax.set_xticklabels(RULES, fontsize=9)
    ax.set_title(metric)
    ax.grid(axis="y", alpha=0.3)

fig.suptitle("checker 규칙 비교")
fig.tight_layout()

out = Path(__file__).parent / "checker_versions_comparison_2026-07-05.png"
fig.savefig(out, dpi=150)
print(f"wrote {out}")
