#!/usr/bin/env python3
"""Render the 2026-08-14 dfxisp_accel csynth/co-sim rerun figures."""

from pathlib import Path

import matplotlib.pyplot as plt


OUT = Path(__file__).resolve().parent.parent
NAVY = "#24445c"
BLUE = "#3f83a6"
TEAL = "#37a48d"
ORANGE = "#e28743"
GREEN = "#4f9d69"
GRID = "#d8dee4"


def finish(fig, name):
    fig.savefig(OUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def resource_figure():
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8))
    axes[0].bar(["BRAM_18K", "DSP"], [9, 24], color=[BLUE, ORANGE], width=0.62)
    axes[0].set_ylabel("Count")
    axes[0].set_title("Dedicated resources")
    axes[1].bar(["FF", "LUT"], [5540, 8439], color=[TEAL, NAVY], width=0.62)
    axes[1].set_ylabel("Count")
    axes[1].set_title("Logic resources")
    for ax in axes:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for bar in ax.patches:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{int(bar.get_height()):,}", ha="center", va="bottom", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("dfxisp_accel C-synthesis utilization", fontweight="bold")
    fig.tight_layout()
    finish(fig, "csynth-resources-2026-08-14.png")


def timing_figure():
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    labels = ["Target period", "Estimated period", "Margin"]
    values = [5.0, 3.65, 1.35]
    bars = ax.barh(labels, values, color=[NAVY, BLUE, GREEN], height=0.58)
    ax.invert_yaxis()
    ax.set_xlabel("Nanoseconds")
    ax.set_title("5 ns timing target met in C synthesis", fontweight="bold")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(bars, values):
        ax.text(value + 0.06, bar.get_y() + bar.get_height() / 2,
                f"{value:.2f} ns", va="center", fontsize=10)
    ax.set_xlim(0, 5.7)
    fig.tight_layout()
    finish(fig, "csynth-timing-2026-08-14.png")


def cosim_figure():
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), gridspec_kw={"width_ratios": [1.25, 1]})
    labels = ["Minimum", "Average", "Maximum", "Interval", "Total run"]
    values = [346, 753, 1160, 1120, 1466]
    colors = [TEAL, BLUE, NAVY, ORANGE, GREEN]
    bars = axes[0].bar(labels, values, color=colors, width=0.66)
    axes[0].set_ylabel("Clock cycles")
    axes[0].set_title("Measured RTL co-sim cycles")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(axis="y", color=GRID, linewidth=0.8)
    axes[0].set_axisbelow(True)
    axes[0].spines[["top", "right"]].set_visible(False)
    for bar, value in zip(bars, values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, value,
                     f"{value:,}", ha="center", va="bottom", fontsize=9)

    stages = ["C simulation", "C synthesis", "RTL 2 / 2", "C post-check"]
    y = list(range(len(stages)))
    axes[1].scatter([0] * len(stages), y, s=650, color=GREEN, edgecolor="white", linewidth=2)
    axes[1].plot([0] * len(stages), y, color=GREEN, linewidth=4, zorder=0)
    for yi, stage in zip(y, stages):
        axes[1].text(0, yi, "PASS", color="white", ha="center", va="center",
                     fontsize=8, fontweight="bold")
        axes[1].text(0.18, yi, stage, va="center", fontsize=10)
    axes[1].set_ylim(-0.5, len(stages) - 0.5)
    axes[1].invert_yaxis()
    axes[1].set_xlim(-0.3, 1.25)
    axes[1].axis("off")
    axes[1].set_title("Verification chain", pad=12)
    fig.suptitle("C/RTL co-simulation: automatic post-check PASS", fontweight="bold")
    fig.tight_layout()
    finish(fig, "cosim-pass-summary-2026-08-14.png")


def main():
    resource_figure()
    timing_figure()
    cosim_figure()
    print("wrote 3 figures to", OUT)


if __name__ == "__main__":
    main()
