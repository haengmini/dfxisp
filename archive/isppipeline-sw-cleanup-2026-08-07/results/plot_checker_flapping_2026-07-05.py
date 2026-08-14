#!/usr/bin/env python3
"""C0-C4 checker jitter/band/flapping comparison (hysteresis flaps excluded
per user request -- all five versions hit 0.00 there anyway).
Source: checker-principled-versions-2026-07-05.md SS3 (the primary results
doc -- checker-principles-2026-07-05.md SS5.2 only reproduced a 4-row subset
of this table and omitted C4; use the primary doc's full 5-row table here).
No re-run -- visualization of already-published numbers. C1 (deployed)
highlighted.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "NanumGothic"
import matplotlib.pyplot as plt
import numpy as np

RULES = ["C0", "C1", "C2", "C3", "C4"]
DATA = {
    "jitter σ":        {"C0": 0.0020, "C1": 0.0023, "C2": 0.0023, "C3": 0.0120, "C4": 0.0023},
    "δ 밴드":           {"C0": 0.020,  "C1": 0.020,  "C2": 0.020,  "C3": 0.043, "C4": 0.020},
    "단일임계 flaps/100fr": {"C0": 3.27, "C1": 1.50, "C2": 3.71, "C3": 16.69, "C4": 6.43},
}
DEPLOYED = "C1"
BAR_COLOR = "#4C72B0"
DEPLOYED_COLOR = "#C44E52"

x = np.arange(len(RULES))
BAR_W = 0.5

fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.2))
for ax, metric in zip(axes, DATA):
    ys = [DATA[metric][r] for r in RULES]
    colors = [DEPLOYED_COLOR if r == DEPLOYED else BAR_COLOR for r in RULES]
    bars = ax.bar(x, ys, width=BAR_W, color=colors)
    for xi, v in zip(x, ys):
        ax.annotate(f"{v:.4f}" if v < 1 else f"{v:.2f}", (xi, v),
                     textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8)
    ax.set_ylim(0, max(ys) * 1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(RULES, fontsize=9)
    ax.set_title(metric)
    ax.grid(axis="y", alpha=0.3)

fig.suptitle("checker 규칙 비교")
fig.tight_layout()

out = Path(__file__).parent / "checker_flapping_comparison_2026-07-05.png"
fig.savefig(out, dpi=150)
print(f"wrote {out}")
