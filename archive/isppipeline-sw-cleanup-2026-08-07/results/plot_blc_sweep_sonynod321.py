#!/usr/bin/env python3
"""BLC offset sweep -- SonyNOD 321 frames, YOLOv8n, arms: normal/lowlight/adaptive.
Source: map_isp_sonynod_blcfix_yolov8n.csv (copied verbatim from
~/workspace/dfxisp/.claude/worktrees/hw-interface-prompt, isp-pipeline-recalibration-2026-07-08.md).
No re-simulation -- this only visualizes existing, already-validated numbers.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV = HERE / "map_isp_sonynod_blcfix_yolov8n.csv"

ARM_COLORS = {"normal": "#4C72B0", "lowlight": "#DD8452", "adaptive": "#55A868"}
ARM_MARKERS = {"normal": "o", "lowlight": "s", "adaptive": "^"}


def load():
    rows = list(csv.DictReader(open(CSV)))
    data = {}  # arm -> {blc: (map5095, map50)}
    for r in rows:
        arm = r["arm"]
        blc = int(r["blc_offset"])
        data.setdefault(arm, {})[blc] = (float(r["mAP_50_95"]), float(r["mAP_50"]))
    return data


def main():
    data = load()
    blcs = sorted(next(iter(data.values())).keys())  # 0,1,2,4,8,16
    x = list(range(len(blcs)))  # categorical positions (BLC spacing is non-linear)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    for arm in ("normal", "lowlight", "adaptive"):
        ys = [data[arm][b][1] for b in blcs]  # index 1 = mAP_50
        ax.plot(x, ys, marker=ARM_MARKERS[arm], color=ARM_COLORS[arm],
                 label=arm, linewidth=2, markersize=6)
    ax.set_xticks(x)
    ax.set_xticklabels([str(b * 16) for b in blcs])  # 8-bit -> 12-bit (<<4)
    ax.set_xlabel("BLC offset (12-bit)")
    ax.set_ylabel("mAP")
    ax.grid(alpha=0.3)
    ax.axvspan(x[blcs.index(1)] - 0.5, x[blcs.index(2)] + 0.5, color="gold", alpha=0.15)
    ax.legend(loc="upper right")

    fig.suptitle("BLC sweep -- SonyNOD 321")
    ax.set_title("Black Level Correction (BLC) offset calibration experiment", fontsize=10)
    fig.tight_layout()
    out = HERE / "blc_sweep_sonynod321_map_2026-07-08.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
