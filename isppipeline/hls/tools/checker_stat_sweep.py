#!/usr/bin/env python3
"""checker_stat_sweep.py -- scene-checker statistic sweep / simulation.

Evaluates single-pass, integer-arithmetic candidate statistics for the DFXISP
scene checker (checker_select_mode in src/dfxisp_accel.cpp) as a
LOW_LIGHT(ExDark) vs NORMAL(COCO) classifier, using the repo's real datasets
data/{coco_val,exdark_val}/raw_bin/*.bin (little-endian uint16 pseudo-RAW
Bayer RGGB; W,H recovered from the matching JPEG in images/).

All candidate statistics are computable in ONE streaming pass with integer
arithmetic; percentiles/entropy/log-mean derive from a 256-bin histogram of
(raw >> 8), which maps to a small BRAM in HW. Note: dark-ratio at an 8-bit
threshold T8 is exactly the histogram CDF at bin T8-1 (raw16 < T8*256 <=>
raw16>>8 < T8), so every dark-ratio variant is also "free" given the histogram.

Usage:
  python3 checker_stat_sweep.py --compute [--csv PATH]   # per-frame stats CSV
  python3 checker_stat_sweep.py --analyze [--csv PATH]   # tables to stdout

Baseline: dark-ratio at dark_pixel_threshold=12800 (= 8-bit 50 << 8, the
Y<50-equivalent used by the 2026-07-02 ver2 recalibration), trigger at >80%.

RAW-domain note (adversarial review, 2026-07-04): thresholds in this script are
in the DATASET domain -- the .bin files are shift-8 pseudo-RAW, so an 8-bit
threshold T8 is T8 << 8 (dark16 -> 4096). The HLS pipeline input is 12-bit
(RAW12_MAX=4095 in src/dfxisp_accel.cpp), where the same T8 is T8 << 4
(dark16 -> 256). Feeding a dataset-domain value like 4096 to the HLS
dark_pixel_threshold register would mark EVERY valid 12-bit pixel dark and
route all AUTO frames to LOW_LIGHT. --analyze prints both domains.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve()
for p in [REPO] + list(REPO.parents):
    if (p / "data" / "coco_val").is_dir():
        REPO = p
        break
else:
    REPO = Path("/home/mini/workspace/dfxisp")

DATASETS = {"coco": ("coco_val", 0), "exdark": ("exdark_val", 1)}  # label 1 = LOW_LIGHT truth

# 8-bit-equivalent dark thresholds swept (x256 in RAW16 domain). 50 = current.
DARK_T8 = [16, 24, 32, 48, 50, 64]
PCTL = [10, 25, 50, 75, 90]
LOG2_LUT = np.log2(1.0 + np.arange(256))  # HW: 256-entry fixed-point LUT

# Subsampling variants: Bayer 2x2 quads kept whole, quad-grid stride (ky,kx).
# Pixel fractions: 1/4, 1/8, 1/16.
SUBS = {"s4": (2, 2), "s8": (4, 2), "s16": (4, 4)}


def img_dims(img_dir: Path, stem: str) -> tuple[int, int]:
    """W,H of the source image matching a raw_bin stem (jpg/jpeg/png, any case)."""
    from PIL import Image  # noqa: PLC0415
    for p in img_dir.glob(f"{stem}.*"):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            with Image.open(p) as im:
                return im.size
    raise FileNotFoundError(f"{img_dir}/{stem}.*")


def hist_stats(hist: np.ndarray, prefix: str) -> dict[str, float]:
    """Derive all histogram-based statistics (one 256-bin BRAM histogram)."""
    n = int(hist.sum())
    out: dict[str, float] = {}
    cdf = np.cumsum(hist)
    for t8 in DARK_T8:  # dark-ratio family: CDF read-out, no extra counters
        out[f"{prefix}dark{t8}"] = cdf[t8 - 1] / n
    for q in PCTL:  # CDF walk percentile (integer)
        out[f"{prefix}p{q}"] = float(np.searchsorted(cdf, (q * n + 99) // 100))
    out[f"{prefix}logmean"] = float(hist @ LOG2_LUT) / n  # log-avg luminance
    pi = hist[hist > 0] / n
    out[f"{prefix}entropy"] = float(-(pi * np.log2(pi)).sum())
    return out


def frame_stats(a: np.ndarray) -> dict[str, float]:
    """All per-frame candidate statistics. a: (h, w) uint16 RAW."""
    h, w = a.shape
    v8 = (a >> 8).astype(np.uint8)
    out = {"w": w, "h": h, "mean8": float(a.mean()) / 256.0}
    out.update(hist_stats(np.bincount(v8.ravel(), minlength=256), ""))

    # Bayer-quad-preserving subsampling: quads Q[qy,qx,2,2]
    h2, w2 = h - h % 2, w - w % 2
    qv = v8[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).transpose(0, 2, 1, 3)
    for tag, (ky, kx) in SUBS.items():
        sub = qv[0::ky, 0::kx]
        out.update(hist_stats(np.bincount(sub.ravel(), minlength=256), f"{tag}_"))
    # phase spread at 1/16: same stat across all 16 quad-phase offsets -> std
    ph = {k: [] for k in ("dark16", "dark32", "dark50", "p50", "p90",
                          "logmean")}
    for oy in range(4):
        for ox in range(4):
            hs = hist_stats(
                np.bincount(qv[oy::4, ox::4].ravel(), minlength=256), "")
            for k in ph:
                ph[k].append(hs[k])
    for k, v in ph.items():
        out[f"ph16_{k}_std"] = float(np.std(v))
    return out


def golden_y50_ratio(a: np.ndarray) -> float:
    """C0-era golden-model checker view: demosaic -> Y -> ratio(Y<50).

    Kept self-contained on purpose (2026-07-20): checker.py now mirrors the
    deployed C1 rule (raw-domain dark16 > 0.62) and no longer exposes the old
    luminance-based dark_ratio(rgb) this historical statistic was defined on.
    Only the demosaic helper is still shared."""
    sys.path.insert(0, str(REPO / "isppipeline" / "hls" / "tools"))
    import checker as C  # noqa: PLC0415
    h, w = a.shape
    rgb = C.demosaic_rggb(a, w, h)
    r = rgb[..., 0].astype(np.int32); g = rgb[..., 1].astype(np.int32); b = rgb[..., 2].astype(np.int32)
    y = (r + 2 * g + b) // 4
    return float(np.mean(y < 50))


def compute(csv_path: Path) -> None:
    rows = []
    for name, (d, label) in DATASETS.items():
        raw_dir = REPO / "data" / d / "raw_bin"
        img_dir = REPO / "data" / d / "images"
        for i, bp in enumerate(sorted(raw_dir.glob("*.bin"))):
            w, hgt = img_dims(img_dir, bp.stem)
            a = np.fromfile(bp, dtype="<u2")
            if a.size != w * hgt:  # raw_bin is even-cropped vs the JPEG
                w, hgt = w - w % 2, hgt - hgt % 2
            assert a.size == w * hgt, f"{bp}: {a.size} != {w}x{hgt}"
            a = a.reshape(hgt, w)
            row = {"dataset": name, "stem": bp.stem, "label": label}
            row.update(frame_stats(a))
            row["y50_ratio"] = golden_y50_ratio(a)
            rows.append(row)
            if (i + 1) % 100 == 0:
                print(f"  {name}: {i + 1} frames", file=sys.stderr)
    cols = list(rows[0].keys())
    with csv_path.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {len(rows)} rows -> {csv_path}", file=sys.stderr)


# ---------------------------------------------------------------- analysis --
def load(csv_path: Path) -> dict[str, np.ndarray]:
    with csv_path.open() as f:
        rd = csv.DictReader(f)
        rows = list(rd)
    out: dict[str, np.ndarray] = {}
    for k in rows[0]:
        if k in ("dataset", "stem"):
            out[k] = np.array([r[k] for r in rows])
        else:
            out[k] = np.array([float(r[k]) for r in rows])
    return out


def roc(scores: np.ndarray, y: np.ndarray):
    """scores: darkness-increasing. Returns (thr, fpr, tpr, auc). Predict
    LOW_LIGHT when score > thr (matches HW strict-> comparison)."""
    u = np.unique(scores)
    thr = np.concatenate([[u[0] - 1], (u[:-1] + u[1:]) / 2, [u[-1] + 1]])
    pos = np.sort(scores[y == 1])
    neg = np.sort(scores[y == 0])
    tpr = 1.0 - np.searchsorted(pos, thr, side="right") / len(pos)
    fpr = 1.0 - np.searchsorted(neg, thr, side="right") / len(neg)
    # AUC via Mann-Whitney with tie correction (average ranks)
    allv = np.concatenate([pos, neg])
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt)
    ranks = (csum[inv] + (csum - cnt)[inv] + 1) / 2.0  # average ranks
    auc = (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (
        len(pos) * len(neg))
    return thr, fpr, tpr, auc


def op_points(scores, y):
    thr, fpr, tpr, auc = roc(scores, y)
    j = tpr - fpr
    bi = int(np.argmax(j))
    res = {"auc": auc, "J_thr": thr[bi], "J_tpr": tpr[bi], "J_fpr": fpr[bi],
           "J": j[bi]}
    for alpha, tag in ((0.05, "np05"), (0.10, "np10")):
        ok = fpr <= alpha + 1e-12
        k = int(np.argmax(np.where(ok, tpr, -1)))
        res[f"{tag}_thr"], res[f"{tag}_tpr"], res[f"{tag}_fpr"] = (
            thr[k], tpr[k], fpr[k])
    return res


def eval_at(scores, y, thr):
    pred = scores > thr
    return float(pred[y == 1].mean()), float(pred[y == 0].mean())  # recall, FT


def kfold_cv(scores, y, k=5, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    rec, ft, thrs = [], [], []
    for f in folds:
        mask = np.ones(len(y), bool)
        mask[f] = False
        op = op_points(scores[mask], y[mask])
        r, t = eval_at(scores[~mask], y[~mask], op["J_thr"])
        rec.append(r), ft.append(t), thrs.append(op["J_thr"])
    return (np.mean(rec), np.std(rec), np.mean(ft), np.std(ft),
            np.mean(thrs), np.std(thrs))


def _count_flips(seq, t_lo, t_hi, init):
    """(flips_single, flips_hyst) for one sequence. Hysteresis: enter
    LOW_LIGHT above t_hi, leave below t_lo; single threshold = midpoint."""
    t_mid = (t_lo + t_hi) / 2
    single = seq > t_mid
    fs = int(np.count_nonzero(np.diff(single)))
    st, fh = init, 0
    for v in seq:
        nxt = True if v > t_hi else (False if v < t_lo else st)
        fh += nxt != st
        st = nxt
    return fs, fh


def flap_sim(vals_near, t, delta, sigma, nframes=100, ntrial=300, seed=2):
    """Scenario A 'steady': a static scene whose stat sits near the threshold
    (base drawn from real frames within the near-boundary band), per-frame
    additive Gaussian jitter sigma. Ideal flips = 0.
    Scenario B 'ramp': bright->dark linear ramp crossing t (span 8 sigma or
    0.04, whichever larger) with the same jitter. Ideal flips = 1.
    Returns mean flips per sequence (single, hyst) for both scenarios."""
    rng = np.random.default_rng(seed)
    out = np.zeros(4)
    span = max(8 * sigma, 0.04)
    ramp = np.linspace(t - span / 2, t + span / 2, nframes)
    for _ in range(ntrial):
        base = rng.choice(vals_near)
        seq = base + rng.normal(0, sigma, nframes)
        out[:2] += _count_flips(seq, t - delta, t + delta, base > t)
        seq = ramp + rng.normal(0, sigma, nframes)
        out[2:] += _count_flips(seq, t - delta, t + delta, False)
    return out / ntrial


def fmt_op(name, op, scale=1.0, unit=""):
    return (f"| {name} | {op['auc']:.4f} | {op['J_thr']*scale:.3f}{unit} | "
            f"{op['J_tpr']:.3f} | {op['J_fpr']:.3f} | {op['J']:.3f} | "
            f"{op['np05_tpr']:.3f} @ {op['np05_thr']*scale:.3f}{unit} | "
            f"{op['np10_tpr']:.3f} @ {op['np10_thr']*scale:.3f}{unit} |")


def analyze(csv_path: Path) -> None:
    D = load(csv_path)
    y = D["label"]

    print("## dark_pixel_threshold domain mapping (see module docstring)")
    print("| 8-bit T8 | dataset pseudo-RAW16 (T8<<8) | HLS raw12 (T8<<4) |")
    print("|---|---|---|")
    for t8 in DARK_T8:
        cur = " (current)" if t8 == 50 else ""
        print(f"| {t8}{cur} | {t8 << 8} | {t8 << 4} |")

    print("\n## baseline reproduction")
    for col, note in (("y50_ratio", "golden Y<50 (ver2 recal metric)"),
                      ("dark50", "HW raw16<12800")):
        r, ft = eval_at(D[col], y, 0.80)
        print(f"{col:>10} >0.80 ({note}): recall={r:.3f} FT={ft:.3f} "
              f"J={r-ft:.3f}")
    # first-200-stem subsets (recalibration used n=150~200)
    for nlim in (150, 200):
        sel = np.zeros(len(y), bool)
        for ds in ("coco", "exdark"):
            ii = np.where(D["dataset"] == ds)[0]
            sel[ii[np.argsort(D["stem"][ii])][:nlim]] = True
        r, ft = eval_at(D["y50_ratio"][sel], y[sel], 0.80)
        print(f"  y50_ratio>0.80 on first {nlim}/class: recall={r:.3f} "
              f"FT={ft:.3f}")

    # statistic table (darkness-increasing sign)
    stats = [("dark%d" % t, +1) for t in DARK_T8]
    stats += [("mean8", -1), ("logmean", -1)]
    stats += [("p%d" % q, -1) for q in PCTL]
    stats += [("entropy", -1), ("y50_ratio", +1)]
    print("\n## per-statistic ROC")
    print("| stat | AUC | J* thr | recall | FT | J | NP FT<=0.05 | "
          "NP FT<=0.10 |")
    print("|---|---|---|---|---|---|---|---|")
    ops = {}
    for name, sign in stats:
        s = sign * D[name]
        op = op_points(s, y)
        ops[name] = (op, sign)
        print(fmt_op(name + ("" if sign > 0 else " (lower=dark)"), op,
                     scale=sign))

    # 2-feature grid rules: dark50 + p90
    print("\n## 2-feature combos (dark50 + p90)")
    a_grid = np.round(np.arange(0.30, 0.96, 0.01), 3)
    b_grid = np.arange(0, 256)
    d50, p90 = D["dark50"], D["p90"]
    for mode in ("AND", "OR"):
        best = None
        for a in a_grid:
            pa = d50 > a
            for b in b_grid:
                pb = p90 < b
                pred = pa & pb if mode == "AND" else pa | pb
                r = pred[y == 1].mean()
                f = pred[y == 0].mean()
                if best is None or r - f > best[0]:
                    best = (r - f, a, b, r, f)
        j, a, b, r, f = best
        print(f"{mode}: dark50>{a:.2f} {mode} p90<{b:.0f} -> "
              f"recall={r:.3f} FT={f:.3f} J={j:.3f}")
    # logistic (reference AUC only, gradient descent, standardized)
    X = np.stack([d50, 255.0 - p90], 1)
    Xs = (X - X.mean(0)) / X.std(0)
    wgt = np.zeros(3)
    Xb = np.concatenate([Xs, np.ones((len(y), 1))], 1)
    for _ in range(3000):
        z = 1 / (1 + np.exp(-Xb @ wgt))
        wgt -= 0.1 * Xb.T @ (z - y) / len(y)
    op = op_points(Xb @ wgt, y)
    print(f"logistic(dark50,p90) AUC={op['auc']:.4f} "
          f"J={op['J']:.3f} (recall={op['J_tpr']:.3f} FT={op['J_fpr']:.3f})")

    # subsampling study
    print("\n## subsampling (Bayer-quad-preserving)")
    print("| stat | frac | AUC | J | recall | FT |")
    print("|---|---|---|---|---|---|")
    for name, sign in [("dark16", 1), ("dark32", 1), ("dark50", 1),
                       ("p50", -1), ("p90", -1), ("logmean", -1)]:
        for tag, frac in (("", "1/1"), ("s4_", "1/4"), ("s8_", "1/8"),
                          ("s16_", "1/16")):
            op = op_points(sign * D[tag + name], y)
            print(f"| {name} | {frac} | {op['auc']:.4f} | {op['J']:.3f} | "
                  f"{op['J_tpr']:.3f} | {op['J_fpr']:.3f} |")
    print("\nphase std at 1/16 (16 quad offsets), mean over frames:")
    for k in ("dark16", "dark32", "dark50", "p50", "p90", "logmean"):
        v = D[f"ph16_{k}_std"]
        print(f"  {k}: mean={v.mean():.4f} p95={np.percentile(v, 95):.4f}")

    # margin / hysteresis
    print("\n## near-boundary density + hysteresis")
    for name, sign in [("dark16", 1), ("dark50", 1), ("p50", -1),
                       ("logmean", -1)]:
        op, _ = ops[name]
        t = op["J_thr"]
        s = sign * D[name]
        rng_ = s.max() - s.min()
        for eps_frac in (0.01, 0.02, 0.05):
            eps = eps_frac * rng_
            fr = float((np.abs(s - t) <= eps).mean())
            print(f"  {name}: |s-t*|<= {eps_frac*100:.0f}% of range "
                  f"(eps={eps:.3f}): {fr*100:.1f}% frames")
    # flapping sim, sigma from measured 1/16 phase-spread (median / p95 / 3x)
    print("\nflapping simulation (steady ideal=0 / ramp ideal=1 flips, "
          "300 trials x 100 frames):")
    for name in ("dark16", "dark50"):
        op, _ = ops[name]
        t = op["J_thr"]
        s = D[name]
        near = s[np.abs(s - t) <= 0.05]
        pstd = D[f"ph16_{name}_std"]
        for sg, tag in ((float(np.median(pstd)), "med"),
                        (float(np.percentile(pstd, 95)), "p95"),
                        (3 * float(np.percentile(pstd, 95)), "3xp95")):
            for delta in (0.0, sg, 2 * sg, 3 * sg, 0.02):
                st_s, st_h, rp_s, rp_h = flap_sim(near, t, delta, sg)
                print(f"  {name} sigma={sg:.4f}({tag}) delta={delta:.4f}: "
                      f"steady single={st_s:.2f} hyst={st_h:.2f} | "
                      f"ramp single={rp_s:.2f} hyst={rp_h:.2f}")

    # cross validation
    print("\n## 5-fold CV (J-max threshold fit on 4/5, eval 1/5)")
    print("| stat | recall mean+-std | FT mean+-std | thr mean+-std |")
    print("|---|---|---|---|")
    for name, sign in [("dark16", 1), ("dark24", 1), ("dark32", 1),
                       ("dark50", 1), ("p50", -1), ("p25", -1),
                       ("logmean", -1), ("mean8", -1), ("entropy", -1)]:
        r, rs, f, fs2, t, ts = kfold_cv(sign * D[name], y)
        print(f"| {name} | {r:.3f}+-{rs:.3f} | {f:.3f}+-{fs2:.3f} | "
              f"{sign*t:.3f}+-{ts:.3f} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--csv", default=str(Path(__file__).parent /
                                         "frame_stats.csv"))
    args = ap.parse_args()
    p = Path(args.csv)
    if args.compute:
        compute(p)
    if args.analyze:
        analyze(p)
    if not (args.compute or args.analyze):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
