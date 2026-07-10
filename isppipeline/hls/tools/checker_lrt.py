#!/usr/bin/env python3
"""checker_lrt.py -- histogram likelihood-ratio checker (strategy #2).

Campaign : checker-sota (2026-07-09), branch exp/principled-checker-rm-2026-07-05.
Track    : strategy doc checker-strengthening-2026-07-10.md item #2.

Learns a linear log-likelihood-ratio score over the SAME 256-bin (raw>>8)
histogram the HW checker already computes in one streaming pass:

    score = sum_b w_b * hhat_b + b0,    hhat_b = h_b / N
    LOW_LIGHT  <=>  score > t

This is the data-processing-inequality upgrade over the dark-ratio family
(dark16 is the special case w = 1[b<16]). Regularization: ridge + second-
difference smoothness on w (OOD guard, per the strategy doc; monotonicity is
CHECKED post-hoc rather than enforced). Coarse log-binned variants (16/8
aggregated bins) are the cheaper fallback the theory doc deferred.

HONESTY PROTOCOL (same bar that rejected C4):
  * outer 5-fold CV (seed 0, np.array_split -- identical fold construction to
    checker_stat_sweep.kfold_cv); weights AND threshold fit on train folds
    only; all reported recall/FT/J are held-out (out-of-fold).
  * hyperparameters (lam_ridge, lam_smooth) chosen by INNER 3-fold CV inside
    each outer train split (nested CV, cf. checker_versions_fine.nested_cv_c4).
  * int8 weight quantization evaluated per fold (HW = 256-entry ROM + MAC).
  * acceptance bar (strategy doc): held-out J >= C1 J + 0.04, else reject
    after also trying the coarse variants.

HW realization note: score>t with hhat=h/N is equivalent to the pure-integer
comparison  sum_b wq_b*h_b > T(N)  with int8 wq and a per-frame T linear in N
(N is known from width*height at frame start), i.e. 256-entry int8 ROM + one
MAC accumulator + one comparator -- same streaming contract as today.

Usage:
  python3 tools/checker_lrt.py --compute                # dump per-frame hists
  python3 tools/checker_lrt.py --analyze                # nested-CV campaign
  (defaults: results/scratch_frame_hist.npz)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import checker_stat_sweep as S

# Mis-decision costs (ablation, analysis-2026-07-04 s4): mAP@0.5:0.95 loss.
C_MISS, C_FA = 0.1118, 0.0387

# C1 deployed baseline (checker-principled-versions-2026-07-05.md s5).
C1_THR = 0.62
ACCEPT_MARGIN = 0.04  # strategy doc #2 acceptance bar over C1's honest J

# Hyperparameter grid for nested CV. Features are scaled 256*hhat (mean 1.0
# per bin), so O(1) weights; lambdas span 3 decades around that scale.
LAM_GRID = [(lr, ls) for lr in (1e-3, 1e-2, 1e-1) for ls in (0.0, 1e-2, 1.0)]

# Coarse log-spaced aggregation edges (bin index space, 0..256).
LOG16_EDGES = [0, 1, 2, 3, 4, 6, 8, 11, 16, 23, 32, 45, 64, 91, 128, 181, 256]
LOG8_EDGES = [0, 2, 4, 8, 16, 32, 64, 128, 256]


def risk(recall: float, ft: float) -> float:
    return 0.5 * ((1.0 - recall) * C_MISS + ft * C_FA)


# ------------------------------------------------------------------ compute --
def compute(npz_path: Path) -> None:
    """One pass over raw_bin -> per-frame full 256-bin histogram + label.
    Same frame iteration order and (raw>>8) domain as checker_stat_sweep."""
    hists, labels, stems, dsets = [], [], [], []
    for name, (d, label) in S.DATASETS.items():
        raw_dir = S.REPO / "data" / d / "raw_bin"
        img_dir = S.REPO / "data" / d / "images"
        for i, bp in enumerate(sorted(raw_dir.glob("*.bin"))):
            w, hgt = S.img_dims(img_dir, bp.stem)
            a = np.fromfile(bp, dtype="<u2")
            if a.size != w * hgt:
                w, hgt = w - w % 2, hgt - hgt % 2
            assert a.size == w * hgt, f"{bp}: {a.size} != {w}x{hgt}"
            v8 = (a >> 8).astype(np.uint8)
            hists.append(np.bincount(v8, minlength=256).astype(np.int64))
            labels.append(label)
            stems.append(bp.stem)
            dsets.append(name)
            if (i + 1) % 100 == 0:
                print(f"  {name}: {i + 1} frames", flush=True)
    np.savez_compressed(
        npz_path, hist=np.stack(hists), label=np.array(labels, np.int8),
        stem=np.array(stems), dataset=np.array(dsets))
    print(f"wrote {len(labels)} frames -> {npz_path}")


# ---------------------------------------------------------------- modelling --
def second_diff(d: int) -> np.ndarray:
    D = np.zeros((d - 2, d))
    i = np.arange(d - 2)
    D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
    return D


def fit_irls(X: np.ndarray, y: np.ndarray, lam_r: float, lam_s: float,
             iters: int = 30) -> np.ndarray:
    """Penalized logistic regression via IRLS/Newton. Returns w of length
    d+1 (last = intercept; penalties never touch the intercept)."""
    n, d = X.shape
    Xb = np.concatenate([X, np.ones((n, 1))], 1)
    P = np.zeros((d + 1, d + 1))
    P[:d, :d] += lam_r * np.eye(d)
    if lam_s > 0 and d > 2:
        D = second_diff(d)
        P[:d, :d] += lam_s * (D.T @ D)
    w = np.zeros(d + 1)
    for _ in range(iters):
        z = np.clip(Xb @ w, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        Wt = np.maximum(p * (1.0 - p), 1e-6)
        A = Xb.T @ (Xb * Wt[:, None]) + P + 1e-9 * np.eye(d + 1)
        b = Xb.T @ (Wt * z + (y - p))
        w_new = np.linalg.solve(A, b)
        if np.max(np.abs(w_new - w)) < 1e-7:
            w = w_new
            break
        w = w_new
    return w


def quantize_w(w: np.ndarray) -> tuple[np.ndarray, float]:
    """int8 symmetric quantization of the bin weights (intercept kept float:
    it folds into the threshold register in HW)."""
    s = float(np.max(np.abs(w[:-1]))) / 127.0
    if s == 0.0:
        return w.copy(), 1.0
    wq = np.round(w[:-1] / s)
    return np.concatenate([wq, [w[-1]]]), s


def score_of(X: np.ndarray, w: np.ndarray, qscale: float = 1.0) -> np.ndarray:
    return (X @ w[:-1]) * qscale + w[-1]


def nested_cv(X: np.ndarray, y: np.ndarray, name: str, k: int = 5,
              inner: int = 3, seed: int = 0) -> dict:
    """Nested CV: inner grid-search (lam_r, lam_s) on train folds, outer
    held-out eval. Returns held-out metrics + out-of-fold predictions +
    per-fold quantized metrics."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    oof_score = np.full(len(y), np.nan)
    oof_pred = np.zeros(len(y), bool)
    rec, ft, rec_q, ft_q, lams, wbars = [], [], [], [], [], []
    for f in folds:
        tr = np.ones(len(y), bool)
        tr[f] = False
        tr_idx = np.where(tr)[0]
        # ---- inner CV over the hyper grid (threshold refit per inner fold)
        rng_in = np.random.default_rng(seed + 1)
        infolds = np.array_split(rng_in.permutation(tr_idx), inner)
        best_lam, best_j = LAM_GRID[0], -np.inf
        for lam in LAM_GRID:
            js = []
            for g in infolds:
                tr2 = tr.copy()
                tr2[g] = False
                w = fit_irls(X[tr2], y[tr2], *lam)
                thr = S.op_points(score_of(X[tr2], w), y[tr2])["J_thr"]
                r, t = S.eval_at(score_of(X[g], w), y[g], thr)
                js.append(r - t)
            if np.mean(js) > best_j:
                best_j, best_lam = float(np.mean(js)), lam
        # ---- refit on the full outer-train split with the chosen lambdas
        w = fit_irls(X[tr], y[tr], *best_lam)
        thr = S.op_points(score_of(X[tr], w), y[tr])["J_thr"]
        s_te = score_of(X[~tr], w)
        r, t = S.eval_at(s_te, y[~tr], thr)
        rec.append(r)
        ft.append(t)
        oof_score[~tr] = s_te
        oof_pred[~tr] = s_te > thr
        # ---- int8 quantized twin (threshold refit on train, honest)
        wq, qs = quantize_w(w)
        thr_q = S.op_points(score_of(X[tr], wq, qs), y[tr])["J_thr"]
        rq, tq = S.eval_at(score_of(X[~tr], wq, qs), y[~tr], thr_q)
        rec_q.append(rq)
        ft_q.append(tq)
        lams.append(best_lam)
        wbars.append(w[:-1])
    r, t = float(np.mean(rec)), float(np.mean(ft))
    rq, tq = float(np.mean(rec_q)), float(np.mean(ft_q))
    auc = S.roc(oof_score, y)[3]
    wbar = np.mean(np.stack(wbars), 0)
    # post-hoc monotonicity check: fraction of adjacent weight pairs that are
    # non-increasing (darkness score should weight low bins more).
    mono = float(np.mean(np.diff(wbar) <= 1e-9))
    return dict(name=name, cv_recall=r, cv_recall_sd=float(np.std(rec)),
                cv_ft=t, cv_ft_sd=float(np.std(ft)), cv_j=r - t,
                cv_risk=risk(r, t), q_recall=rq, q_ft=tq, q_j=rq - tq,
                oof_auc=auc, oof_pred=oof_pred, oof_score=oof_score,
                lams=lams, wbar=wbar, mono=mono)


def aggregate(hist: np.ndarray, edges: list[int]) -> np.ndarray:
    return np.stack([hist[:, a:b].sum(1) for a, b in zip(edges, edges[1:])], 1)


# ----------------------------------------------------------------- analysis --
def analyze(npz_path: Path) -> None:
    Z = np.load(npz_path, allow_pickle=False)
    hist = Z["hist"].astype(np.float64)
    y = Z["label"].astype(np.float64)
    stems, dsets = Z["stem"], Z["dataset"]
    N = hist.sum(1, keepdims=True)
    npos, nneg = int((y == 1).sum()), int((y == 0).sum())
    print(f"# checker_lrt -- {npos} LOW_LIGHT(ExDark) + {nneg} NORMAL(COCO) "
          f"= {len(y)} frames\n")

    # Baselines from the SAME histograms (dark16 = CDF read-out at bin 15).
    dark16 = np.cumsum(hist, 1)[:, 15] / N[:, 0]
    r1, f1 = S.eval_at(dark16, y, C1_THR)
    j1 = r1 - f1
    cvr, cvrs, cvf, cvfs, _, _ = S.kfold_cv(dark16, y, k=5, seed=0)
    print("## Baselines (identical folds, seed 0)")
    print(f"C1 fixed  dark16>{C1_THR}: recall={r1:.3f} FT={f1:.3f} "
          f"J={j1:.3f} R={risk(r1, f1):.5f}  (no fitting -> honest)")
    print(f"dark16 J-fit 5-fold CV : recall={cvr:.3f}+-{cvrs:.3f} "
          f"FT={cvf:.3f}+-{cvfs:.3f} J={cvr - cvf:.3f}")
    accept_bar = j1 + ACCEPT_MARGIN
    print(f"acceptance bar (C1 J + {ACCEPT_MARGIN}): held-out J >= "
          f"{accept_bar:.3f}\n")

    # Feature sets: scaled densities 256*hhat (per-bin mean 1.0).
    Xfull = 256.0 * hist / N
    feats = {
        "LRT-256 (ridge+smooth)": Xfull,
        "LRT-log16": aggregate(hist, LOG16_EDGES) * len(LOG16_EDGES[:-1]) / N,
        "LRT-log8": aggregate(hist, LOG8_EDGES) * len(LOG8_EDGES[:-1]) / N,
    }
    results = {k: nested_cv(X, y, k) for k, X in feats.items()}

    print("## Nested-CV held-out results (outer 5-fold / inner 3-fold)")
    print("| variant | oof AUC | CV recall | CV FT | CV J | CV R | "
          "int8 J | mono(w) |")
    print("|---|---|---|---|---|---|---|---|")
    for res in results.values():
        print(f"| {res['name']} | {res['oof_auc']:.4f} | "
              f"{res['cv_recall']:.3f}+-{res['cv_recall_sd']:.3f} | "
              f"{res['cv_ft']:.3f}+-{res['cv_ft_sd']:.3f} | "
              f"{res['cv_j']:.3f} | {res['cv_risk']:.5f} | "
              f"{res['q_j']:.3f} | {res['mono']:.2f} |")

    best = max(results.values(), key=lambda r: r["cv_j"])
    print(f"\nchosen-per-fold (lam_ridge, lam_smooth) of {best['name']}: "
          f"{best['lams']}")

    # ---- residual-error recovery vs C1 (out-of-fold predictions -> honest)
    pred_c1 = dark16 > C1_THR
    err_c1 = pred_c1 != (y == 1)
    miss_c1 = err_c1 & (y == 1)
    ftr_c1 = err_c1 & (y == 0)
    p = best["oof_pred"]
    err_lrt = p != (y == 1)
    print(f"\n## Residual-error recovery vs C1 (best variant: {best['name']})")
    print(f"C1 errors: {int(err_c1.sum())} "
          f"(miss {int(miss_c1.sum())} / FT {int(ftr_c1.sum())})")
    print(f"LRT out-of-fold errors: {int(err_lrt.sum())} "
          f"(miss {int((err_lrt & (y == 1)).sum())} / "
          f"FT {int((err_lrt & (y == 0)).sum())})")
    rec_miss = int((miss_c1 & ~err_lrt).sum())
    rec_ft = int((ftr_c1 & ~err_lrt).sum())
    new_err = int((~err_c1 & err_lrt).sum())
    print(f"recovered: {rec_miss}/{int(miss_c1.sum())} misses, "
          f"{rec_ft}/{int(ftr_c1.sum())} FTs; new errors introduced: {new_err}")
    worst = np.where(err_lrt & err_c1)[0]
    print(f"still-wrong-in-both (common bottleneck set): {len(worst)}")
    for i in worst[:10]:
        print(f"  {dsets[i]}/{stems[i]} label={int(y[i])} "
              f"dark16={dark16[i]:.3f}")

    # ---- mean weight profile of the best variant (for the results doc)
    print(f"\n## Mean learned weight profile ({best['name']}, "
          "fold-averaged, first 32 bins then every 16th)")
    wb = best["wbar"]
    idx = list(range(min(32, len(wb)))) + list(range(32, len(wb), 16))
    print("bin: " + " ".join(f"{i}" for i in idx))
    print("w  : " + " ".join(f"{wb[i]:+.2f}" for i in idx))

    # ---- verdict against the strategy-doc acceptance bar
    print("\n## VERDICT")
    for res in results.values():
        margin = res["cv_j"] - j1
        status = ("PASS" if res["cv_j"] >= accept_bar else
                  "within fold-variance" if margin > 0 else "no gain")
        print(f"  {res['name']}: held-out J={res['cv_j']:.3f} vs C1 {j1:.3f} "
              f"(margin {margin:+.3f}) -> {status}")
    print(f"  bar was J >= {accept_bar:.3f} (C1 + {ACCEPT_MARGIN}, exceeding "
          "5-fold FT fold-variance +-0.03~0.04)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--npz", default=str(Path(__file__).parent.parent /
                                         "results" / "scratch_frame_hist.npz"))
    args = ap.parse_args()
    p = Path(args.npz)
    if args.compute:
        compute(p)
    if args.analyze:
        analyze(p)
    if not (args.compute or args.analyze):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
