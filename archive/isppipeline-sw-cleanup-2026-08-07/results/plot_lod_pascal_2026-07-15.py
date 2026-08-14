#!/usr/bin/env python3
"""LOD_split(=SonyNOD 321)/PASCAL_split(321) 3-arm BLC sweep, YOLOv8n.
Source CSVs copied verbatim from ~/workspace/dfxisp/.claude/worktrees/
hw-interface-prompt (lod-pascal-isp-simulation-2026-07-15.md). No re-run --
visualization only.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
ARM_COLORS = {"normal": "#4C72B0", "lowlight": "#DD8452", "adaptive": "#55A868"}
ARM_MARKERS = {"normal": "o", "lowlight": "s", "adaptive": "^"}


def load(name):
    rows = list(csv.DictReader(open(HERE / name)))
    data = {}
    for r in rows:
        data.setdefault(r["arm"], {})[int(r["blc_offset"])] = float(r["mAP_50"])
    return data


def plot_panel(ax, data, title):
    blcs = sorted(next(iter(data.values())).keys())
    x = list(range(len(blcs)))
    for arm in ("normal", "lowlight", "adaptive"):
        ys = [data[arm][b] for b in blcs]
        ax.plot(x, ys, marker=ARM_MARKERS[arm], color=ARM_COLORS[arm],
                 label=arm, linewidth=2, markersize=6)
    ax.set_xticks(x)
    ax.set_xticklabels([str(b) for b in blcs])
    ax.set_xlabel("BLC offset")
    ax.set_ylabel("mAP")
    ax.set_title(title)
    ax.grid(alpha=0.3)


def main():
    lod = load("map_isp_lod_split_2026-07-15.csv")
    pascal = load("map_isp_pascal_split_2026-07-15.csv")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    plot_panel(axes[0], lod, "LOD_split (SonyNOD, 321)")
    plot_panel(axes[1], pascal, "PASCAL_split (321)")
    axes[1].legend(loc="lower right")

    fig.suptitle("LOD vs PASCAL, 321 frames each")
    fig.tight_layout()
    out = HERE / "lod_pascal_map_2026-07-15.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
