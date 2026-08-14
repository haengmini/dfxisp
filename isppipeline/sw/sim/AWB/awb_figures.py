#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/AWB/awb_figures.py
# Date   : 2026-08-13
# Function: Draw the AWB figure set from the measurements in this directory.
#           Every figure is computed from dataset/{LOD,PASCAL}_test as they
#           exist now -- awb_stats_*.json / awb_hist_*.npz (awb_figure_data.py)
#           and the mAP sweep CSVs.
# Figures : F1 diagnosis-vs-response (2 panels) | F2 WB lever vs BLC lever
#           F3 cross-dataset reproducibility     | F4 per-frame as-shot WB
#           F5 post-BLC channel histogram + clipping wall
#           (F6 qualitative render is awb_qualitative.py -- images, not plots)
# Palette : dataviz reference categorical slots 1-3, validated all-pairs in
#           light mode (CVD dE 9.2, normal-vision dE 24.0). Every series is
#           also direct-labelled, which is required anyway for slot 3 (aqua
#           sits below 3:1 on the light surface -- the relief rule).
# Usage   : python3 awb_figures.py [--figs 1,2,3,4,5] [--out-dir figures]
# =============================================================================
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

HERE = Path(__file__).resolve().parent
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"     # blue, orange, aqua
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8983"
SURFACE = "#fcfcfb"
DEPLOYED = {"R": 286, "G": 256, "B": 307}
# Project convention for the mAP noise band (gamma.md and neighbours): a
# spread under ~0.005 is not treated as a real difference.
NOISE = 0.005

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.8,
    "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "legend.frameon": False, "savefig.facecolor": SURFACE,
})


def tidy(ax, grid_axis=None):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, color="#e4e3dd", linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)


def load_stats(name: str) -> dict | None:
    p = HERE / f"awb_stats_{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def load_sweep(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    with path.open() as f:
        return list(csv.DictReader(f))


def sweep_rows(rows, key="mAP_50_95"):
    """(labels, values) ordered as the report's table, deployed marked."""
    order = ["256:256:256", "286:256:307", "360:256:307",
             "286:256:460", "360:256:460", "435:256:616"]
    names = {"256:256:256": "WB off", "286:256:307": "deployed",
             "360:256:307": "R only", "286:256:460": "B only",
             "360:256:460": "R+B mid", "435:256:616": "gray-world"}
    by_wb = {r["wb_lowlight"]: r for r in rows}
    labs, vals = [], []
    for wb in order:
        if wb in by_wb:
            labs.append(names[wb])
            vals.append(float(by_wb[wb][key]))
    return labs, vals


# ------------------------------------------------------------------- F1 -----
def fig1(out: Path):
    lod, pas = load_stats("lod"), load_stats("pascal")
    if not lod:
        print("F1: skipped (awb_stats_lod.json missing)")
        return
    sweeps = [(HERE / "awb_wb_sweep_lodtest.csv", "LOD (night)", S1),
              (HERE / "awb_wb_sweep_pascaltest.csv", "PASCAL (day)", S2)]
    sweeps = [(p, l, c) for p, l, c in sweeps if load_sweep(p)]
    # Each dataset's mAP sits at a different level (LOD ~0.072, PASCAL ~0.100),
    # so they get one facet each. Sharing an axis here would be a dual scale.
    fig, axes = plt.subplots(1, 1 + len(sweeps),
                             figsize=(4.4 + 3.0 * len(sweeps), 3.7),
                             gridspec_kw={"width_ratios": [1.35] + [1] * len(sweeps)})
    axa, sweep_axes = axes[0], axes[1:]

    # (a) deployed / gray-world required gain, per channel and dataset
    sets = [(lod, "LOD (night)", S1)] + ([(pas, "PASCAL (day)", S2)] if pas else [])
    chans, w = ["R", "B"], 0.34
    for i, (st, label, col) in enumerate(sets):
        ratios = [st["deployed_over_grayworld"][c] for c in chans]
        y = np.arange(len(chans)) + (i - (len(sets) - 1) / 2) * w
        axa.barh(y, ratios, height=w * 0.88, color=col, zorder=3,
                 label=f"{label}  n={st['n_images']}")
        for yy, r, c in zip(y, ratios, chans):
            gw = st["gray_world_wb_q8"][c]
            axa.text(r + 0.03, yy, f"{r:.2f}×  ({DEPLOYED[c]}→{gw})",
                     va="center", fontsize=8, color=INK2)
    axa.axvline(1.0, color=INK, linewidth=1.0, zorder=4)
    axa.annotate("correct", (1.0, -0.62), fontsize=8, color=INK, ha="center")
    axa.set_yticks(range(len(chans)))
    axa.set_yticklabels([f"{c} gain" for c in chans])
    axa.set_ylim(len(chans) - 0.45, -0.8)
    axa.set_xlim(0, 1.75)
    axa.set_xlabel("deployed ÷ gray-world required gain")
    axa.set_title("(a) The deployed WB is wrong for night,\n     near-correct for day",
                  loc="left", color=INK, fontsize=9.5)
    axa.legend(loc="upper right", fontsize=8)
    tidy(axa, grid_axis="x")

    # (b..) one facet per dataset: the sweep does not move outside the noise band
    for k, (ax, (path, label, col)) in enumerate(zip(sweep_axes, sweeps)):
        labs, vals = sweep_rows(load_sweep(path))
        base = vals[labs.index("deployed")]
        y = np.arange(len(labs))
        ax.axvspan(base - NOISE / 2, base + NOISE / 2, color=col, alpha=0.12,
                   zorder=1)
        ax.plot([base, base], [-0.6, len(labs) - 0.4], color=col,
                linewidth=1.0, linestyle="--", zorder=2)
        ax.plot(vals, y, "o", color=col, markersize=7.5, zorder=3,
                markeredgecolor=SURFACE, markeredgewidth=1.0)
        ax.set_yticks(y)
        ax.set_yticklabels(labs if k == 0 else [""] * len(labs))
        ax.set_ylim(len(labs) - 0.4, -0.6)
        ax.set_xlim(base - NOISE, base + NOISE)
        ax.set_xlabel("mAP@[.5:.95]   (shaded: ±0.005)")
        ax.set_title(f"({'bcd'[k]}) {label}", loc="left", color=INK, fontsize=9.5)
        tidy(ax, grid_axis="x")
    fig.suptitle("Diagnosis confirmed, response absent — every candidate lands inside the noise band",
                 x=0.006, ha="left", color=INK, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    for ext in ("png", "pdf"):
        fig.savefig(out / f"F1_diagnosis_vs_response.{ext}", dpi=200)
    plt.close(fig)
    print("F1 written")


# ------------------------------------------------------------------- F2 -----
def fig2(out: Path):
    bars = []
    for path, label, col in (
            (HERE / "awb_wb_sweep_lodtest.csv", "WB, LOD\noff → 2× overcorrection", S1),
            (HERE / "awb_wb_sweep_pascaltest.csv", "WB, PASCAL\noff → 2× overcorrection", S2)):
        rows = load_sweep(path)
        if rows:
            _, v = sweep_rows(rows)
            bars.append((label, max(v) - min(v), col))
    blc = load_sweep(HERE / "awb_blc_sweep_lodtest.csv")
    if blc:
        v = [float(r["mAP_50_95"]) for r in blc]
        bars.append(("BLC, LOD\noffset 0 → 16", max(v) - min(v), S3))
    if not bars:
        print("F2: skipped (no sweeps yet)")
        return
    fig, ax = plt.subplots(figsize=(6.8, 0.72 * len(bars) + 1.7))
    y = np.arange(len(bars))
    top = max(b[1] for b in bars)
    ax.axvspan(0, NOISE, color="#e4e3dd", zorder=1)
    ax.barh(y, [b[1] for b in bars], height=0.5,
            color=[b[2] for b in bars], zorder=3)
    for yy, (label, val, _) in zip(y, bars):
        ax.text(val + top * 0.015, yy, f"{val:.4f}", va="center",
                fontsize=9, color=INK, zorder=5)
    ax.set_yticks(y)
    ax.set_yticklabels([b[0] for b in bars], fontsize=8.5)
    ax.set_ylim(len(bars) - 0.45, -0.85)
    ax.text(NOISE * 1.25, -0.72, "noise band (0.005)", fontsize=8, color=INK2,
            va="center")
    ax.set_xlim(0, top * 1.14)
    ax.set_xlabel("full-sweep mAP@[.5:.95] spread   (same 100 frames, YOLOv8n)")
    ax.set_title("WB is not a lever; BLC is", loc="left", color=INK)
    tidy(ax, grid_axis="x")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"F2_lever_scale.{ext}", dpi=200)
    plt.close(fig)
    print("F2 written")


# ------------------------------------------------------------------- F3 -----
def fig3(out: Path):
    series = []
    for path, label, col in ((HERE / "awb_wb_sweep_lodtest.csv", "LOD (night)", S1),
                             (HERE / "awb_wb_sweep_pascaltest.csv", "PASCAL (day)", S2)):
        rows = load_sweep(path)
        if rows:
            series.append((label, col, rows))
    if not series:
        print("F3: skipped (no sweeps yet)")
        return
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=True)
    for ax, key, title in zip(axes, ("mAP_50_95", "mAP_50"),
                              ("mAP@[.5:.95]", "mAP@50")):
        h = 0.8 / len(series)
        for i, (label, col, rows) in enumerate(series):
            labs, vals = sweep_rows(rows, key)
            base = vals[labs.index("deployed")]
            delta = [(v - base) / base * 100 for v in vals]
            y = np.arange(len(labs)) + (i - (len(series) - 1) / 2) * h
            ax.barh(y, delta, height=h * 0.85, color=col, zorder=3, label=label)
        ax.axvline(0, color=INK, linewidth=1.0, zorder=4)
        ax.set_yticks(range(len(labs)))
        ax.set_yticklabels(labs)
        # sharey=True: inverting per-facet would flip twice and undo itself,
        # and the order must match F1's facets
        ax.set_ylim(len(labs) - 0.5, -0.5)
        ax.set_xlabel(f"Δ {title} vs deployed [%]")
        tidy(ax, grid_axis="x")
    axes[0].set_title("Every candidate, both datasets — no consistent winner",
                      loc="left", color=INK)
    axes[0].legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"F3_reproducibility.{ext}", dpi=200)
    plt.close(fig)
    print("F3 written")


# ------------------------------------------------------------------- F4 -----
def fig4(out: Path):
    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    any_data = False
    for name, label, col in (("lod", "LOD (night)", S1), ("pascal", "PASCAL (day)", S2)):
        st = load_stats(name)
        if not st:
            continue
        any_data = True
        wb = np.array([f["as_shot_wb"] for f in st["frames"]])
        uniq = np.unique(wb.round(4), axis=0)
        ax.scatter(wb[:, 0], wb[:, 2], s=26, color=col, alpha=0.55,
                   edgecolor="none", zorder=3, label=f"{label}  n={len(wb)}")
        if len(uniq) == 1:
            # a locked camera preset: 100 frames land on one point, and saying so
            # matters more than the dot does
            ax.annotate(f"all {len(wb)} frames identical\n(camera locked to one preset)",
                        (wb[0, 0], wb[0, 2]), textcoords="offset points",
                        xytext=(-14, 16), ha="right", fontsize=8, color=INK2,
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
        gw = st["gray_world_wb_q8"]
        ax.plot(gw["R"] / 256, gw["B"] / 256, "^", color=col, markersize=11,
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=5)
        ax.annotate(f"gray-world ({name.upper()})", (gw["R"] / 256, gw["B"] / 256),
                    textcoords="offset points", xytext=(10, -2),
                    fontsize=8, color=INK2)
    if not any_data:
        print("F4: skipped (no stats yet)")
        plt.close(fig)
        return
    ax.plot(DEPLOYED["R"] / 256, DEPLOYED["B"] / 256, "*", color=INK, markersize=17,
            markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=6)
    ax.annotate("deployed 286/256/307", (DEPLOYED["R"] / 256, DEPLOYED["B"] / 256),
                textcoords="offset points", xytext=(12, 0), fontsize=8.5, color=INK)
    ax.set_xlabel("R / G gain")
    ax.set_ylabel("B / G gain")
    ax.set_title("The deployed constant sits outside every scene it serves",
                 loc="left", color=INK)
    ax.legend(loc="upper left", fontsize=8)
    tidy(ax, grid_axis="both")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"F4_as_shot_wb_scatter.{ext}", dpi=200)
    plt.close(fig)
    print("F4 written")


# ------------------------------------------------------------------- F5 -----
def fig5(out: Path):
    have = [(n, l) for n, l in (("lod", "LOD (night)"), ("pascal", "PASCAL (day)"))
            if (HERE / f"awb_hist_{n}.npz").exists()]
    if not have:
        print("F5: skipped (no histograms yet)")
        return
    # The 12-bit values are sparse (shift8 origin -> only multiples of 16 are
    # populated, spread by the BLC range-restore), so a per-code histogram is a
    # comb that reads as a solid block on a log axis. Rebin to 32-wide bins.
    BINW, XMAX = 32, 2048
    fig, axes = plt.subplots(1, len(have), figsize=(5.1 * len(have), 3.9), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (name, label) in zip(axes, have):
        z = np.load(HERE / f"awb_hist_{name}.npz")
        st = load_stats(name)
        tot = float(z["g"].sum())
        nb = (len(z["g"]) - 1) // BINW + 1
        centres = np.arange(nb) * BINW + BINW / 2
        for i, (ch, col) in enumerate(zip("rgb", (S1, S2, S3))):
            h = z[ch].astype(float)
            nz = np.add.reduceat(h[1:], np.arange(0, len(h) - 1, BINW)) / tot * 100
            ax.step(centres[:len(nz)], nz, where="mid", color=col,
                    linewidth=1.5, zorder=3, label=ch.upper())
            # the clipping wall: the 0 bin, drawn as its own mark, not a spike
            ax.bar(-90 + i * 55, h[0] / tot * 100, width=48, color=col,
                   zorder=4, align="center")
        clip = st["clip0_pct_rgb"] if st else None
        if clip:
            ax.text(-100, max(clip) * 1.35,
                    f"clipped to 0 by BLC\nR {clip[0]:.0f}%   G {clip[1]:.0f}%   B {clip[2]:.0f}%",
                    fontsize=8.5, color=INK, va="bottom")
        ax.axvline(-10, color=MUTED, linewidth=0.8, linestyle=":", zorder=2)
        ax.set_yscale("log")
        ax.set_xlim(-190, XMAX)
        ax.set_ylim(1e-4, 400)
        ax.set_xticks([0, 512, 1024, 1536, 2048])
        ax.set_xlabel("post-BLC value (12-bit)")
        ax.set_title(label, loc="left", color=INK)
        tidy(ax, grid_axis="y")
    axes[0].set_ylabel("share of pixels [%, log]")
    axes[-1].legend(loc="upper right", fontsize=8, title="channel", title_fontsize=8)
    fig.suptitle("Why WB cannot matter: most night pixels are already 0 when WB applies",
                 x=0.008, ha="left", color=INK, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    for ext in ("png", "pdf"):
        fig.savefig(out / f"F5_channel_histogram.{ext}", dpi=200)
    plt.close(fig)
    print("F5 written")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--figs", default="1,2,3,4,5")
    ap.add_argument("--out-dir", default=str(HERE / "figures"))
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fns = {"1": fig1, "2": fig2, "3": fig3, "4": fig4, "5": fig5}
    for k in a.figs.split(","):
        fns[k.strip()](out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
