#!/usr/bin/env python3
"""blc12bit_resweep_plot: mAP vs BLC_OFFSET (12-bit native units) for the
2026-08-18 LOD_test_hw / PASCAL_test_hw resweep, companion figure for
blc12bit_resweep_report.md.

Reads the two CSVs eval_map_isp.py wrote (isppipeline/hls/results/
map_isp_{lod,pascal}_blc12bit_yolov8n.csv) and plots mAP@.5:.95 against
blc_offset per dataset x arm, with the deployed constant (32, 12-bit) marked.

Usage:
  python3 blc12bit_resweep_plot.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent.parent.parent / "hls" / "results"
DEPLOYED_BLC12 = 32

DATASET_STYLE = {
    "LOD-BLC12bit": {"color": "#e34948", "label": "LOD_test_hw"},
    "PASCAL-BLC12bit": {"color": "#2a78d6", "label": "PASCAL_test_hw"},
}
ARM_STYLE = {
    "normal": {"linestyle": "-", "marker": "o"},
    "lowlight": {"linestyle": "--", "marker": "x"},
}


def load(csv_path: Path) -> dict[str, dict[int, float]]:
    """arm -> {blc_offset: mAP_50_95}"""
    out: dict[str, dict[int, float]] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            out.setdefault(row["arm"], {})[int(row["blc_offset"])] = float(row["mAP_50_95"])
    return out


def main() -> int:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150, sharey=True)

    for ax, (dataset, csv_name) in zip(
        axes,
        [("LOD-BLC12bit", "map_isp_lod_blc12bit_yolov8n.csv"),
         ("PASCAL-BLC12bit", "map_isp_pascal_blc12bit_yolov8n.csv")],
    ):
        style = DATASET_STYLE[dataset]
        by_arm = load(RESULTS / csv_name)
        for arm, points in by_arm.items():
            x = sorted(points)
            y = [points[v] for v in x]
            a_style = ARM_STYLE[arm]
            ax.plot(x, y, color=style["color"], linestyle=a_style["linestyle"],
                     marker=a_style["marker"], markersize=4, linewidth=1.5,
                     label=f"{arm}", zorder=3)
        ax.axvline(DEPLOYED_BLC12, color="#8a8a86", linewidth=1, linestyle=":",
                   zorder=1, label=f"deployed (BLC={DEPLOYED_BLC12})")
        ax.set_xscale("symlog", linthresh=8)
        ax.set_xlim(left=0)
        offsets = sorted(next(iter(by_arm.values())))
        ax.set_xticks(offsets)
        ax.set_xticklabels([str(v) for v in offsets], rotation=60, ha="right", fontsize=7)
        ax.set_xlabel("BLC_OFFSET (12-bit DN)")
        ax.set_title(style["label"])
        ax.grid(True, which="both", color="#e3e2dc", linewidth=0.8, zorder=0)
        ax.legend(fontsize=8, loc="upper right")

    axes[0].set_ylabel("mAP@.5:.95 (yolov8n)")
    fig.suptitle("12-bit BLC_OFFSET resweep -- LOD_test_hw / PASCAL_test_hw (2026-08-18)")
    fig.tight_layout()
    out = HERE / "blc12bit_resweep_map.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
