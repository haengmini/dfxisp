#!/usr/bin/env python3
"""checker_tile_probe.py -- spatial (tile) dark-metering probe for the checker.

Strengthening-strategy item #5 (spatial / tile metering). Tests the
backlit/spotlight hypothesis: do the C1 residual-error frames (frames the
deployed global checker C1 = `dark16 > 0.62` gets wrong) carry SPATIAL
structure -- a bright subject in a dark surround, or a dark region in a
bright scene -- that a 4x4 tile metering can separate but a single global
dark-pixel ratio cannot?

Pipeline (single pass, no cache file written):
  1. Load scratch_frame_stats.csv; C1 pred = dark16 > 0.62; find error frames
     (ExDark misses + COCO false-triggers).
  2. For every frame read data/<ds>_val/raw_bin/<stem>.bin (headerless LE
     uint16, shift8: 8-bit-equiv = raw>>8), reshape (H,W) via the CSV w,h,
     split into a 4x4 tile grid and compute the per-tile dark16 ratio
     (fraction of tile pixels with raw>>8 < 16). 16 ratios/frame.
       Tile index mirrors HW: ty = min(y // (H//4), 3), tx = min(x // (W//4),
       3). H//4 / W//4 are per-frame constants a HW block latches once; the
       min() clamp handles non-power-of-2 / non-divisible dims. No per-pixel
       multiply.
  3. CHEAP GATE (go/no-go, computed on the C1-error subset): quantify how many
     errors are "spatially structured" (coexisting very-dark and very-bright
     tiles / high tile spread) vs merely "globally borderline" (global ratio
     sits near 0.62, tiles roughly uniform). Enrichment of spatial structure
     in errors vs correctly-classified frames is the decision statistic.
  4. IF the gate is promising (>= ~1/3 of errors spatially structured AND
     errors enriched vs correct): evaluate 3 combine rules on the FULL 1150
     frames with honest 5-fold CV -- (a) center-weighted tile average,
     (b) M-of-16 count, (c) global OR/AND a tile extremum (2-feature nested
     CV). Accept only if held-out J beats C1's 0.847 by more than the
     fold-variance margin (~0.03-0.04) without hurting global recall/FT.

Deterministic: fixed seed=0 folds, mirroring checker_stat_sweep.kfold_cv.

Usage:
  cd isppipeline/hls/tools
  python3 checker_tile_probe.py            # gate + (conditional) full eval
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import checker_stat_sweep as css

REPO = css.REPO
CSV = REPO / "isppipeline" / "hls" / "results" / "scratch_frame_stats.csv"
C1_THR = 0.62          # deployed C1: dark16 > 0.62
DARK_T8 = 16           # dark16 = fraction of pixels with raw>>8 < 16
GRID = 4               # 4x4 tile grid
SEED = 0

# --- gate thresholds (fixed, pre-registered) -------------------------------
BORDER_BAND = 0.08     # |dark16 - 0.62| <= 0.08  => "globally borderline"
VERY_DARK = 0.80       # a tile ratio this high is a "dark" tile
VERY_BRIGHT = 0.20     # a tile ratio this low is a "bright" tile
BIMODAL_K = 3          # >= K dark tiles AND >= K bright tiles => bimodal
STRONG_SPREAD = 0.50   # (max_tile - min_tile) >= this => strong spatial struct
GATE_FRACTION = 1.0 / 3.0  # escalate if this fraction of errors is structured


def tile_ratios(a: np.ndarray) -> np.ndarray:
    """16 per-tile dark16 ratios for a (H,W) uint16 RAW frame, row-major
    tile order (ty*4 + tx). HW-faithful integer tiling."""
    h, w = a.shape
    v = a >> 8
    th, tw = h // GRID, w // GRID          # per-frame constants (HW latch)
    ty = np.minimum(np.arange(h) // th, GRID - 1)
    tx = np.minimum(np.arange(w) // tw, GRID - 1)
    tile_id = (ty[:, None] * GRID + tx[None, :]).ravel()
    dark = (v < DARK_T8).ravel().astype(np.float64)
    cnt = np.bincount(tile_id, minlength=GRID * GRID)
    dcnt = np.bincount(tile_id, weights=dark, minlength=GRID * GRID)
    return dcnt / cnt


def load_tiles(D: dict) -> np.ndarray:
    """(N,16) tile-ratio matrix computed straight from raw_bin (no cache)."""
    n = len(D["label"])
    T = np.empty((n, GRID * GRID), np.float64)
    for i in range(n):
        ds, stem = D["dataset"][i], D["stem"][i]
        w, h = int(D["w"][i]), int(D["h"][i])
        p = REPO / "data" / f"{ds}_val" / "raw_bin" / f"{stem}.bin"
        a = np.fromfile(p, dtype="<u2")
        assert a.size == w * h, f"{p}: {a.size} != {w}x{h}"
        T[i] = tile_ratios(a.reshape(h, w))
        if (i + 1) % 200 == 0:
            print(f"  tiled {i + 1}/{n} frames", file=sys.stderr)
    return T


# --------------------------------------------------------------- honest CV --
def kfold_2feat(fa, fb, y, mode, sign_b, k=5, seed=SEED):
    """Honest 5-fold CV for a 2-feature rule: predict LOW_LIGHT when
    (fa > ta) MODE (sign_b*fb > tb). Both thresholds fit by YouND-J grid
    search on the 4/5 train fold, evaluated on the held-out 1/5. Mirrors the
    seed-0 fold construction of checker_stat_sweep.kfold_cv."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    ga = np.round(np.arange(0.30, 0.96, 0.02), 3)
    sb = sign_b * fb
    gb = np.quantile(sb, np.arange(0.02, 0.99, 0.02))
    rec, ft, js = [], [], []
    for f in folds:
        m = np.ones(len(y), bool)
        m[f] = False
        yt = y[m]
        best = None
        for ta in ga:
            pa = fa[m] > ta
            for tb in gb:
                pb = sb[m] > tb
                pred = (pa & pb) if mode == "AND" else (pa | pb)
                j = pred[yt == 1].mean() - pred[yt == 0].mean()
                if best is None or j > best[0]:
                    best = (j, ta, tb)
        _, ta, tb = best
        pa = fa[~m] > ta
        pb = sb[~m] > tb
        pred = (pa & pb) if mode == "AND" else (pa | pb)
        yh = y[~m]
        r = float(pred[yh == 1].mean())
        t = float(pred[yh == 0].mean())
        rec.append(r), ft.append(t), js.append(r - t)
    return (np.mean(rec), np.std(rec), np.mean(ft), np.std(ft),
            np.mean(js), np.std(js))


def main() -> int:
    D = css.load(CSV)
    y = D["label"].astype(int)
    g = D["dark16"]                    # global dark16 (== count-weighted tile avg)
    pred_c1 = g > C1_THR
    n = len(y)

    miss = (y == 1) & (~pred_c1)       # ExDark low-light called normal
    ftrg = (y == 0) & (pred_c1)        # COCO normal called low-light
    err = miss | ftrg
    correct = ~err

    print("=" * 74)
    print(f"C1 = dark16 > {C1_THR}  |  N = {n} "
          f"(COCO/label0 = {(y==0).sum()}, ExDark/label1 = {(y==1).sum()})")
    r0, f0 = css.eval_at(g, y, C1_THR)
    print(f"C1 in-sample: recall={r0:.3f} FT={f0:.3f} J={r0-f0:.3f}")
    print(f"C1 errors: {err.sum()}  (misses={miss.sum()}, "
          f"false-triggers={ftrg.sum()})")
    print("=" * 74)

    print("Computing 4x4 tile dark16 ratios from raw_bin ...", file=sys.stderr)
    T = load_tiles(D)
    # sanity: count-weighted tile avg reproduces global -- but tiles are
    # unequal in pixel count only at the clamped edge; use simple checks.
    tmin = T.min(1)
    tmax = T.max(1)
    tstd = T.std(1)
    spread = tmax - tmin
    ndark = (T > VERY_DARK).sum(1)
    nbright = (T < VERY_BRIGHT).sum(1)
    bimodal = (ndark >= BIMODAL_K) & (nbright >= BIMODAL_K)
    structured = (spread >= STRONG_SPREAD) | bimodal
    borderline = np.abs(g - C1_THR) <= BORDER_BAND

    # ---------------------------------------------------------------- GATE --
    print("\n" + "#" * 74)
    print("# CHEAP GATE (C1-error subset): spatial structure vs global-border")
    print("#" * 74)
    e = err
    ne = int(e.sum())
    print(f"\nError frames: {ne}")
    print(f"  spatially structured (spread>=%.2f OR bimodal>=%d/%d): "
          "%d (%.1f%%)" % (STRONG_SPREAD, BIMODAL_K, BIMODAL_K,
                           int(structured[e].sum()),
                           100 * structured[e].mean()))
    print(f"  bimodal (>=%d dark AND >=%d bright tiles):            "
          "%d (%.1f%%)" % (BIMODAL_K, BIMODAL_K, int(bimodal[e].sum()),
                           100 * bimodal[e].mean()))
    print(f"  globally borderline (|dark16-%.2f|<=%.2f):            "
          "%d (%.1f%%)" % (C1_THR, BORDER_BAND, int(borderline[e].sum()),
                           100 * borderline[e].mean()))
    print(f"  borderline AND NOT structured (pure global-border):  "
          "%d (%.1f%%)" % (int((borderline & ~structured)[e].sum()),
                           100 * (borderline & ~structured)[e].mean()))

    print("\nEnrichment of spatial structure (errors vs correct):")
    for nm, arr in (("spread", spread), ("tile std", tstd)):
        print(f"  {nm:9s}: err median={np.median(arr[e]):.3f} "
              f"p75={np.percentile(arr[e],75):.3f} | "
              f"correct median={np.median(arr[correct]):.3f} "
              f"p75={np.percentile(arr[correct],75):.3f}")
    for nm, arr in (("structured", structured), ("bimodal", bimodal)):
        pe = arr[e].mean()
        pc = arr[correct].mean()
        print(f"  P[{nm}] err={pe:.3f} correct={pc:.3f} "
              f"enrichment x{(pe/pc if pc>0 else float('inf')):.2f}")

    # break the error set down by type
    for nm, sub in (("misses (ExDark)", miss), ("false-trig (COCO)", ftrg)):
        s = sub
        print(f"\n  {nm}: N={int(s.sum())} structured={int(structured[s].sum())}"
              f" bimodal={int(bimodal[s].sum())} "
              f"borderline={int(borderline[s].sum())}")

    frac_struct = structured[e].mean()
    gate_pass = frac_struct >= GATE_FRACTION and structured[e].mean() > \
        structured[correct].mean()
    print("\n" + "-" * 74)
    print(f"GATE decision: structured fraction of errors = {frac_struct:.3f} "
          f"(threshold {GATE_FRACTION:.3f})")
    print(f"               errors enriched vs correct    = "
          f"{structured[e].mean() > structured[correct].mean()}")
    print(f"  => GATE {'PASS (escalate to full CV)' if gate_pass else 'FAIL (reject cheaply)'}")
    print("-" * 74)

    # ---------------------------------------------- STEP 4 (full CV eval) ---
    # Always computed for the record; the verdict follows the pre-registered
    # accept criterion (J > 0.847 + fold margin) regardless.
    print("\n" + "#" * 74)
    print("# FULL 1150-frame honest 5-fold CV (baseline C1 J = 0.847)")
    print("#" * 74)

    print("\n[baseline] global dark16 (C1 family), single-threshold CV:")
    r, rs, ftm, fs, tm, ts = css.kfold_cv(g, y, seed=SEED)
    print(f"  recall={r:.3f}+-{rs:.3f} FT={ftm:.3f}+-{fs:.3f} "
          f"J={r-ftm:.3f} thr={tm:.3f}+-{ts:.3f}")

    # (a) center-weighted tile average -----------------------------------
    w = np.ones(GRID * GRID)
    for c in (5, 6, 9, 10):            # inner 2x2 tiles
        w[c] = 2.0
    cwa = (T * w).sum(1) / w.sum()
    print("\n[a] center-weighted tile average (inner 2x2 weight 2):")
    r, rs, ftm, fs, tm, ts = css.kfold_cv(cwa, y, seed=SEED)
    print(f"  recall={r:.3f}+-{rs:.3f} FT={ftm:.3f}+-{fs:.3f} "
          f"J={r-ftm:.3f} thr={tm:.3f}+-{ts:.3f}")

    # (b) M-of-16 count of tiles with ratio > 0.62 -----------------------
    cnt62 = (T > C1_THR).sum(1).astype(np.float64)
    print("\n[b] M-of-16: #tiles with ratio > 0.62 (score in 0..16):")
    r, rs, ftm, fs, tm, ts = css.kfold_cv(cnt62, y, seed=SEED)
    print(f"  recall={r:.3f}+-{rs:.3f} FT={ftm:.3f}+-{fs:.3f} "
          f"J={r-ftm:.3f} M*={tm:.2f}+-{ts:.2f}")

    # (c) global OR/AND tile extremum (2-feature honest nested CV) --------
    print("\n[c] global dark16 combined with a tile extremum (2-feature "
          "nested CV):")
    combos = [
        ("dark16 OR max_tile>tb", g, tmax, "OR", +1),
        ("dark16 OR median_tile>tb", g, np.median(T, 1), "OR", +1),
        ("dark16 AND min_tile>tb", g, tmin, "AND", +1),
        ("dark16 AND (bright absent) min_tile>tb", g, tmin, "AND", +1),
    ]
    seen = set()
    for nm, fa, fb, mode, sb in combos:
        key = (nm.split(" ")[0], mode, id(fb))
        r, rs, ftm, fs, jm, jss = kfold_2feat(fa, fb, y, mode, sb)
        print(f"  {nm:38s}: recall={r:.3f}+-{rs:.3f} FT={ftm:.3f}+-{fs:.3f}"
              f" J={jm:.3f}+-{jss:.3f}")

    print("\n" + "=" * 74)
    print("ACCEPT criterion: held-out J > 0.847 + fold-margin (~0.03-0.04) "
          "AND recall/FT not hurt.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
