#!/usr/bin/env python3
"""checker_versions.py -- principled scene-checker versions C0..C4 (principled-v3).

Campaign : principled-v3 (2026-07-05), branch exp/principled-checker-rm-2026-07-05.
Track    : CHK (goal command Part 1). This is a NEW file; it does not modify the
           canonical checker (src/dfxisp_accel.cpp) nor the sweep infrastructure
           (tools/checker_stat_sweep.py) -- it imports the latter for the ROC /
           operating-point / flapping primitives and consumes the per-frame stats
           CSV that `checker_stat_sweep.py --compute` produces.

Each version is a PURE FUNCTION over per-frame statistics (the dark-ratio family,
log-mean, entropy, ... -- all derivable in one integer streaming pass from a
256-bin (raw>>8) histogram, see checker_stat_sweep docstring). Every version is a
single (or paired) integer-threshold comparison, i.e. HW-friendly: the only state
a HW checker needs beyond the existing counter is, for hysteresis, one mode FF.

Versions (per PLAN-principled-checker-rm-2026-07-05.md section 3.1):
  C0  baseline (current HW)   : dark50 ratio > 0.80
  C1  Youden J*               : dark16 ratio > 0.62
  C2  Bayes-opt (miss 2.9x)   : dark16 ratio > 0.553
  C3  log-domain metering     : logmean < theta*   (theta* = J-max on the data)
  C4  2-feature combo         : dark16 + entropy/dispersion, best AND/OR rule
Every version supports an optional hysteresis band delta=2%p (Schmitt trigger):
enter LOW_LIGHT when score > t+delta, leave when score < t-delta.

DOMAIN NOTE (critical, see checker_stat_sweep docstring / analysis-2026-07-04):
thresholds here are in the DATASET pseudo-RAW domain -- an 8-bit threshold T8 is
T8<<8 in the .bin (dark16 -> raw16<4096, i.e. (raw>>8)<16). The HLS 12-bit
pipeline register uses T8<<4 (dark16 -> 256). RATIO thresholds (0.80, 0.62,
0.553) are domain-independent.

Usage:
  python3 tools/checker_versions.py --csv results/scratch_frame_stats.csv
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

import checker_stat_sweep as S  # roc / op_points / eval_at / flap_sim / load


# --------------------------------------------------------------------------- #
# Version specification                                                        #
# --------------------------------------------------------------------------- #
@dataclass
class Checker:
    """A checker version = a scalar score (darkness-increasing) + a threshold.

    score_fn(D) -> np.ndarray of the darkness-increasing decision score.
    A frame predicts LOW_LIGHT iff score > thr (strict, matches HW '>').
    delta is the hysteresis half-band in SCORE units (enter thr+delta / leave
    thr-delta); 0 disables hysteresis.
    """
    name: str
    rule: str
    score_fn: Callable[[dict], np.ndarray]
    thr: float | None = None          # None -> fit J-max on the data
    delta: float = 0.0                # hysteresis half-band (score units)
    sigma_key: str | None = None      # CSV column of measured per-frame jitter
    hw: str = ""                      # HW cost note


# ---- score builders (pure, integer-derivable) ---------------------------- #
def _dark(t8: int):
    return lambda D: D[f"dark{t8}"]                    # ratio, higher = darker


def _neg_logmean(D):
    return -D["logmean"]                               # logmean lower = darker


# C4: two-feature AND rule dark16>a AND entropy<b, encoded as one darkness score
# via a soft margin so ROC/AUC are well defined. HW realizes it as two integer
# comparators + one AND gate; the score below is only for AUC/threshold reporting.
def _combo_dark16_entropy(D, a=0.615, b=5.293):
    # margin>0 iff both conditions hold; monotone darkness-increasing surrogate.
    m1 = (D["dark16"] - a)
    m2 = (b - D["entropy"])
    # min-combine (AND) scaled to comparable ranges, then shifted to a score.
    s1 = m1 / (D["dark16"].std() + 1e-9)
    s2 = m2 / (D["entropy"].std() + 1e-9)
    return np.minimum(s1, s2)


VERSIONS = [
    Checker("C0", "dark50 ratio>0.80 (current HW)", _dark(50), 0.80,
            sigma_key="ph16_dark50_std",
            hw="1 comparator + 1 counter (unchanged from current RTL)"),
    Checker("C1", "dark16 ratio>0.62 (Youden J*)", _dark(16), 0.62,
            sigma_key="ph16_dark16_std",
            hw="same RTL; register threshold 12800->4096 (HLS 800->256), PCT 80->62"),
    Checker("C2", "dark16 ratio>0.553 (Bayes-opt, miss 2.9x)", _dark(16), 0.553,
            sigma_key="ph16_dark16_std",
            hw="same as C1, PCT 62->55"),
    Checker("C3", "logmean < theta* (log-avg luminance, J-max)", _neg_logmean, None,
            sigma_key="ph16_logmean_std",
            hw="256-entry log2 LUT + 40b accumulator + 1 end-of-frame divide"),
    Checker("C4", "dark16>a AND entropy<b (2-feature, best J)", _combo_dark16_entropy,
            None, sigma_key="ph16_dark16_std",
            hw="256-bin histogram (BRAM) + 2 comparators + AND gate"),
]


# --------------------------------------------------------------------------- #
# Metrics                                                                      #
# --------------------------------------------------------------------------- #
def overlap_coef(scores: np.ndarray, y: np.ndarray, bins: int = 100) -> float:
    """Overlap coefficient (area of min of the two class score densities) --
    a Bayes-error-lower-bound proxy. Lower = better separation."""
    lo, hi = float(scores.min()), float(scores.max())
    if hi <= lo:
        return 1.0
    edges = np.linspace(lo, hi, bins + 1)
    hp, _ = np.histogram(scores[y == 1], bins=edges, density=False)
    hn, _ = np.histogram(scores[y == 0], bins=edges, density=False)
    hp = hp / hp.sum()
    hn = hn / hn.sum()
    return float(np.minimum(hp, hn).sum())


def flapping(scores: np.ndarray, thr: float, delta: float, sigma: float):
    """Return (steady_single, steady_hyst, ramp_single, ramp_hyst) mean flips
    per 100-frame sequence, using checker_stat_sweep's calibrated simulator.
    Steady ideal = 0 flips, ramp ideal = 1 flip."""
    near = scores[np.abs(scores - thr) <= max(0.05, 3 * sigma)]
    if near.size < 5:
        near = scores  # fall back to full support if the band is empty
    st_s, st_h, rp_s, rp_h = S.flap_sim(near, thr, delta, sigma)
    return st_s, st_h, rp_s, rp_h


@dataclass
class Result:
    name: str
    rule: str
    auc: float
    thr: float
    recall: float
    ft: float
    j: float
    overlap: float
    flap_single: float
    flap_hyst: float
    risk: float            # cost-weighted expected mAP loss per frame
    hw: str
    extra: dict = field(default_factory=dict)


# Measured mis-decision costs (ablation, analysis-2026-07-04 section 4 /
# theory-2026-07-03 section 1.2): mAP@0.5:0.95 loss.
C_MISS = 0.1118
C_FA = 0.0387


def risk_of(recall: float, ft: float) -> float:
    """Cost-weighted expected mAP loss per frame R = 1/2 (miss*C_miss + FT*C_FA),
    miss = 1 - recall. Balanced-prior form used across the prior docs."""
    miss = 1.0 - recall
    return 0.5 * (miss * C_MISS + ft * C_FA)


def evaluate(D: dict, v: Checker) -> Result:
    y = D["label"]
    s = np.asarray(v.score_fn(D), dtype=float)
    op = S.op_points(s, y)
    auc = op["auc"]
    # threshold: explicit ratio (compare on raw score) or fit J-max.
    if v.thr is not None:
        # v.thr is on the underlying ratio; score is that same ratio for C0-C2.
        thr = v.thr
    else:
        thr = float(op["J_thr"])
    recall, ft = S.eval_at(s, y, thr)
    j = recall - ft
    overlap = overlap_coef(s, y)
    sigma = float(np.median(D[v.sigma_key])) if v.sigma_key in D else 0.005
    # hysteresis band: 2%p for ratio scores; for non-ratio use 3.6*sigma (matched
    # to the p95-jitter design rule in checker-improvement-simulation section 5.2).
    is_ratio = v.score_fn in (VERSIONS[0].score_fn,) or v.name in ("C0", "C1", "C2")
    delta = 0.02 if is_ratio else max(0.02, 3.6 * sigma)
    fs, fh, _, _ = flapping(s, thr, delta, sigma)
    return Result(v.name, v.rule, auc, thr, recall, ft, j, overlap, fs, fh,
                  risk_of(recall, ft), v.hw,
                  extra={"delta": delta, "sigma": sigma})


def fit_c4(D: dict) -> tuple[float, float, float, float, float]:
    """Grid-search the C4 AND rule dark16>a AND entropy<b for max Youden J.
    Returns (a, b, recall, ft, J)."""
    y = D["label"]
    d16, ent = D["dark16"], D["entropy"]
    a_grid = np.round(np.arange(0.40, 0.85, 0.01), 3)
    b_grid = np.round(np.arange(4.0, 6.0, 0.05), 3)
    best = None
    for a in a_grid:
        pa = d16 > a
        for b in b_grid:
            pred = pa & (ent < b)
            r = float(pred[y == 1].mean())
            f = float(pred[y == 0].mean())
            if best is None or r - f > best[-1]:
                best = (a, b, r, f, r - f)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(Path(__file__).parent.parent /
                                         "results" / "scratch_frame_stats.csv"))
    args = ap.parse_args()
    D = S.load(Path(args.csv))
    y = D["label"]
    npos, nneg = int((y == 1).sum()), int((y == 0).sum())
    print(f"# checker_versions -- {npos} LOW_LIGHT(ExDark) + {nneg} NORMAL(COCO) "
          f"= {len(y)} frames\n")

    # Refine C4 rule on the data before evaluating (report the fitted a,b).
    a4, b4, r4, f4, j4 = fit_c4(D)
    VERSIONS[-1].rule = f"dark16>{a4:.2f} AND entropy<{b4:.2f} (2-feature, best J)"
    VERSIONS[-1].score_fn = lambda D, a=a4, b=b4: _combo_dark16_entropy(D, a, b)

    results = [evaluate(D, v) for v in VERSIONS]

    print("## Version statistic table (full 1150 frames)")
    print("| ver | rule | AUC | op-thr | recall | FT | J | "
          "overlap | R (mAP loss/fr) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r.name} | {r.rule} | {r.auc:.4f} | {r.thr:.3f} | "
              f"{r.recall:.3f} | {r.ft:.3f} | {r.j:.3f} | {r.overlap:.3f} | "
              f"{r.risk:.5f} |")

    print("\n## Hysteresis flapping (per 100-frame steady scene, ideal=0 flips)")
    print("| ver | jitter sigma | delta band | flaps single | flaps hyst |")
    print("|---|---|---|---|---|")
    for r in results:
        print(f"| {r.name} | {r.extra['sigma']:.4f} | {r.extra['delta']:.4f} | "
              f"{r.flap_single:.2f} | {r.flap_hyst:.2f} |")

    print("\n## Cost model (analysis-2026-07-04 s4): "
          f"C_miss={C_MISS} C_FA={C_FA} (ratio {C_MISS/C_FA:.2f}:1); "
          "R = 1/2 (miss*C_miss + FT*C_FA)")

    # Recommendation heuristic: lowest risk R, tie-break higher J.
    best = min(results, key=lambda r: (round(r.risk, 5), -r.j))
    print(f"\n## Lowest expected-mAP-loss version: {best.name} "
          f"(R={best.risk:.5f}, J={best.j:.3f}, recall={best.recall:.3f}, "
          f"FT={best.ft:.3f})")
    # Also report the best balanced-error (J) version.
    bestj = max(results, key=lambda r: r.j)
    print(f"## Highest Youden J version: {bestj.name} (J={bestj.j:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
