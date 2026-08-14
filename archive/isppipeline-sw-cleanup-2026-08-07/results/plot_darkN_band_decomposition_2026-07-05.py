#!/usr/bin/env python3
"""dark16 vs dark50 threshold derivation -- band-decomposition experiment.
Source: checker-principles-2026-07-05.md SS2.3 (band decomposition analysis,
checker-improvement-analysis-2026-07-04.md SS2). No re-run -- visualization
of already-published numbers.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "NanumGothic"
import matplotlib.pyplot as plt
import numpy as np

BANDS = ["[0,16)\n(dark16 대역)", "[16,50)\n(dark50이 추가로 세는 대역)"]
AUC = [0.977, 0.089]
MASS_EXDARK = [0.860, 0.072]
MASS_COCO = [0.360, 0.221]

fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))

# Panel 1: band-only AUC
ax = axes[0]
colors = ["#55A868" if a >= 0.5 else "#C44E52" for a in AUC]
bars = ax.bar(BANDS, AUC, width=0.5, color=colors)
for xi, v in enumerate(AUC):
    ax.annotate(f"{v:.3f}", (xi, v), textcoords="offset points",
                 xytext=(0, 4), ha="center", fontsize=10)
ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
ax.annotate("0.5 = 무작위 추측", (0.5, 0.5), textcoords="offset points",
             xytext=(0, 6), ha="center", fontsize=8, color="gray")
ax.set_ylim(0, 1.05)
ax.set_ylabel("대역 단독 AUC")
ax.set_title("대역별 판별력")
ax.grid(axis="y", alpha=0.3)

# Panel 2: class mass per band
ax = axes[1]
x = np.arange(len(BANDS))
w = 0.35
b1 = ax.bar(x - w/2, MASS_EXDARK, width=w, label="ExDark(야간)", color="#4C72B0")
b2 = ax.bar(x + w/2, MASS_COCO, width=w, label="COCO(주간)", color="#DD8452")
for bars_, vals in ((b1, MASS_EXDARK), (b2, MASS_COCO)):
    for rect, v in zip(bars_, vals):
        ax.annotate(f"{v:.3f}", (rect.get_x() + rect.get_width()/2, v),
                     textcoords="offset points", xytext=(0, 4), ha="center", fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels(BANDS)
ax.set_title("대역별 클래스 질량")
ax.legend()
ax.grid(axis="y", alpha=0.3)

fig.suptitle("dark16 vs dark50 대역 분해 실험")
fig.tight_layout()

out = Path(__file__).parent / "darkN_band_decomposition_2026-07-05.png"
fig.savefig(out, dpi=150)
print(f"wrote {out}")
