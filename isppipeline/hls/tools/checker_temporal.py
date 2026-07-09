#!/usr/bin/env python3
"""checker_temporal.py -- temporal decision layer + probability calibration
for the DFXISP scene checker (strengthening strategy #3 + #6).

Compares FIVE per-frame decision layers operating on the checker score stream
s_t (dark16 ratio) at the deployed operating point (C1: dark16 > 0.62):

  (a) single    : instantaneous threshold  m = (s > t)
  (b) schmitt   : Schmitt hysteresis, enter t+delta / leave t-delta
  (c) kofn      : K-of-N majority voting on the last N frames
  (d) cusum     : two-sided Page CUSUM, g += (s - t -/+ nu), switch when g > h
  (e) sprt      : Wald SPRT log-likelihood-ratio accumulation, boundary A/B

Sequences are synthetic frame streams built from the MEASURED per-frame jitter
(ph16_dark16_std in results/scratch_frame_stats.csv: median 0.00226 / p95
0.00548) added to base values drawn from REAL near-boundary frames. Four
scenarios: steady (ideal 0 switches), ramp (ideal 1), flicker (ideal 0), step
(ideal 1).

Detectors are calibrated to a COMMON false-switch budget (<= 1 false switch per
10 min at 30 fps = 1/18000 frames) so the Pareto comparison is at EQUAL
false-switch rate. CUSUM/SPRT boundaries are asymmetric (enter cheaper than
leave) in the measured cost ratio C_miss/C_FA = 0.1118/0.0387 = 2.888 (miss is
costlier, so we enter LOW_LIGHT faster).

Also (strategy #6) fits a monotone score->probability calibration map (isotonic
PAV + Platt) on the 1150-frame data with 5-fold held-out evaluation and reports
ECE (expected calibration error).

Deterministic (fixed seeds), numpy only. Run from inside isppipeline/hls/tools/.

Usage:
  python3 checker_temporal.py            # full run (Pareto + calibration)
  python3 checker_temporal.py --csv PATH # override stats CSV
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import checker_stat_sweep as css  # reuse load()

# ----- deployed operating point & measured constants ------------------------
T = 0.62                 # C1 deployed dark16 threshold
DELTA = 0.02             # Schmitt half-band (strategy #3 / current scheduler)
C_MISS, C_FA = 0.1118, 0.0387          # measured mode-cost asymmetry
COST_RATIO = C_MISS / C_FA             # 2.888 -> enter faster than leave
FPS = 30
FS_BUDGET_FRAMES = 10 * 60 * FPS       # 18000: <=1 false switch / 10 min
SIGMAS = {"median": 0.0022557, "p95": 0.0054759}   # measured jitter proxies

STEADY_N = 100           # frames per steady/flicker trial (Pareto unit)
LONG_N = 18000           # frames per calibration steady stream
NTRIAL = 400             # trials for delay statistics
SEED = 20260710


# ==========================================================================
# decision layers -- each returns (decided[bool array], switch_frame_list)
# ==========================================================================
def d_single(s, t=T, init=False):
    dec = s > t
    sw = list(np.where(np.diff(np.concatenate([[init], dec])))[0])
    return dec, sw


def d_schmitt(s, t=T, delta=DELTA, init=False):
    hi, lo = t + delta, t - delta
    m = init
    dec = np.empty(len(s), bool)
    sw = []
    for i, v in enumerate(s):
        nxt = True if v > hi else (False if v < lo else m)
        if nxt != m:
            sw.append(i)
        m = nxt
        dec[i] = m
    return dec, sw


def d_kofn(s, t=T, k=3, n=5, init=False):
    """Switch to the opposite mode when >=k of the last n frame-votes (v=s>t)
    favour it. Symmetric voting window."""
    votes = np.zeros(n, bool)
    votes[:] = init
    m = init
    dec = np.empty(len(s), bool)
    sw = []
    for i, v in enumerate(s):
        votes[i % n] = v > t
        cnt_dark = int(votes.sum())
        if not m and cnt_dark >= k:
            m = True
            sw.append(i)
        elif m and (n - cnt_dark) >= k:
            m = False
            sw.append(i)
        dec[i] = m
    return dec, sw


def d_cusum(s, t=T, nu=None, h_enter=0.05, h_leave=None, init=False, sigma=None):
    """Two-sided Page CUSUM. Upward accumulator detects entry into LOW_LIGHT,
    downward accumulator detects exit. nu = slack/drift = the sequential analog
    of the Schmitt half-band, default DELTA/2 = 0.01 (so CUSUM and SPRT share
    identical slack semantics and are the same test up to LLR rescaling).
    Asymmetric thresholds: h_leave = h_enter * COST_RATIO."""
    if nu is None:
        nu = DELTA / 2.0
    if h_leave is None:
        h_leave = h_enter * COST_RATIO
    g_hi = g_lo = 0.0
    m = init
    dec = np.empty(len(s), bool)
    sw = []
    for i, v in enumerate(s):
        g_hi = max(0.0, g_hi + (v - t) - nu)
        g_lo = max(0.0, g_lo + (t - v) - nu)
        if not m and g_hi > h_enter:
            m = True
            sw.append(i)
            g_hi = g_lo = 0.0
        elif m and g_lo > h_leave:
            m = False
            sw.append(i)
            g_hi = g_lo = 0.0
        dec[i] = m
    return dec, sw


def d_sprt(s, t=T, sep=DELTA, sigma=None, b_enter=4.0, b_leave=None, init=False):
    """Repeated Wald SPRT (Page's repeated-SPRT form of change detection).
    Entry test: H0: mu = t (no change / worst NORMAL) vs H1: mu = t+sep. The
    Gaussian LLR increment is (sep/sigma^2)*(s - t - sep/2); the -sep/2 slack
    gives H0 a strictly negative drift so a scene sitting at t has a FINITE ARL
    (without it the walk is driftless and no boundary bounds the false-switch
    rate). Accumulate with a reflecting floor at 0; decide the change at upper
    boundary b (nats). This is exactly CUSUM with drift nu=sep/2 rescaled by the
    LLR slope k=sep/sigma^2 -- the equivalence is the point. Asymmetric
    b_leave = b_enter * COST_RATIO (miss costlier -> enter at lower evidence)."""
    if sigma is None:
        sigma = SIGMAS["median"]
    if b_leave is None:
        b_leave = b_enter * COST_RATIO
    k = sep / (sigma * sigma)              # LLR slope per unit score deviation
    slack = k * sep / 2.0                  # per-frame drift toward H0
    L_hi = L_lo = 0.0
    m = init
    dec = np.empty(len(s), bool)
    sw = []
    for i, v in enumerate(s):
        L_hi = max(0.0, L_hi + k * (v - t) - slack)
        L_lo = max(0.0, L_lo + k * (t - v) - slack)
        if not m and L_hi > b_enter:
            m = True
            sw.append(i)
            L_hi = L_lo = 0.0
        elif m and L_lo > b_leave:
            m = False
            sw.append(i)
            L_hi = L_lo = 0.0
        dec[i] = m
    return dec, sw


# ==========================================================================
# scenario generators (base from real near-boundary frames + measured jitter)
# ==========================================================================
def steady_seq(rng, base_pool, sigma, n=STEADY_N):
    """Static near-threshold scene. base is one real near-boundary value; the
    whole run is that constant + i.i.d. jitter. Ideal switches = 0."""
    base = float(rng.choice(base_pool))
    return base + rng.normal(0, sigma, n), (base > T)


def ramp_seq(rng, sigma, n=STEADY_N):
    """Bright->dark linear ramp crossing t. Span = max(0.08, 12*sigma) so the
    crossing is gradual. Returns (seq, cross_frame). Ideal switches = 1."""
    span = max(0.08, 12 * sigma)
    ramp = np.linspace(T - span / 2, T + span / 2, n)
    cross = int(np.argmin(np.abs(ramp - T)))
    return ramp + rng.normal(0, sigma, n), cross


def flicker_seq(rng, sigma, n=STEADY_N, amp=0.015, period=8):
    """Periodic lighting oscillation about t, amplitude amp < DELTA so it stays
    inside a well-set hysteresis band. Ideal switches = 0 (nuisance flicker)."""
    base = float(rng.choice(_near_pool))          # centred near boundary
    center = T + (base - T) * 0.0                 # oscillate about t
    phase = 2 * np.pi * np.arange(n) / period
    return center + amp * np.sin(phase) + rng.normal(0, sigma, n), None


def step_seq(rng, sigma, n=STEADY_N):
    """Abrupt bright->dark step at the midpoint. Levels well outside the band
    (t -/+ 0.06). Returns (seq, step_frame). Ideal switches = 1."""
    step = n // 2
    lvl = np.where(np.arange(n) < step, T - 0.06, T + 0.06).astype(float)
    return lvl + rng.normal(0, sigma, n), step


# ==========================================================================
# metrics
# ==========================================================================
def false_switches(detector, base_pool, sigma, n_frames, ntrial, seed):
    """Mean false switches per `n_frames`-frame steady scene. Init to the
    correct mode; every switch is spurious."""
    rng = np.random.default_rng(seed)
    tot = 0
    for _ in range(ntrial):
        seq, truth = steady_seq(rng, base_pool, sigma, n_frames)
        _, sw = detector(seq, init=truth)
        tot += len(sw)
    return tot / ntrial


def detect_delay(detector, gen, sigma, ntrial, seed):
    """Mean detection delay (frames) & detection rate on a crossing scenario.
    gen(rng, sigma) -> (seq, event_frame). Init to the pre-event (bright/False)
    mode; delay = first switch-to-dark frame - event_frame."""
    rng = np.random.default_rng(seed)
    delays, detected, extra = [], 0, 0
    for _ in range(ntrial):
        seq, ev = gen(rng, sigma)
        _, sw = detector(seq, init=False)
        enters = [i for i in sw if i >= 0]
        # first transition into dark after the event
        first = next((i for i in sw if i >= ev), None)
        if first is not None:
            delays.append(first - ev)
            detected += 1
        extra += max(0, len(sw) - 1)     # switches beyond the ideal single one
    md = float(np.mean(delays)) if delays else float("nan")
    return md, detected / ntrial, extra / ntrial


def flicker_switches(detector, sigma, ntrial, seed):
    rng = np.random.default_rng(seed)
    tot = 0
    for _ in range(ntrial):
        seq, _ = flicker_seq(rng, sigma)
        _, sw = detector(seq, init=False)
        tot += len(sw)
    return tot / ntrial


# ==========================================================================
# calibration to the common false-switch budget
# ==========================================================================
def _worstcase_fs(detector, sigma, n, seed):
    """False switches on a WORST-CASE static stream sitting exactly AT the
    threshold (base = t). This is the proper ARL definition: the maximum
    false-switch pressure occurs when the true scene equals t. Any switch on a
    static scene is spurious."""
    rng = np.random.default_rng(seed)
    seq = T + rng.normal(0, sigma, n)
    _, sw = detector(seq, init=False)
    return len(sw)


def calibrate(sigma, seed):
    """Return name->(detector, params) tuned to the FASTEST setting whose
    worst-case (base=t) false-switch count over LONG_N frames stays within the
    ARL budget = LONG_N / FS_BUDGET_FRAMES = 1.0 switch. single (no knob) and
    schmitt (delta spec-fixed at 0.02) are fixed references reported as-is."""
    budget = LONG_N / FS_BUDGET_FRAMES          # = 1.0 false switch / stream
    dets = {"single": (d_single, {}),
            "schmitt": (lambda s, init=False: d_schmitt(s, init=init),
                        {"delta": DELTA})}

    # K-of-N: N=5, smallest k (fastest) meeting the worst-case budget
    for k in range(1, 6):
        det = (lambda s, init=False, k=k: d_kofn(s, k=k, n=5, init=init))
        if _worstcase_fs(det, sigma, LONG_N, seed) <= budget:
            dets["kofn"] = (det, {"k": k, "n": 5})
            break
    else:
        dets["kofn"] = ((lambda s, init=False: d_kofn(s, k=5, n=5, init=init)),
                        {"k": 5, "n": 5})

    # CUSUM and SPRT share the slack nu=DELTA/2, so L_sprt = k*g_cusum exactly
    # (k=sep/sigma^2). Calibrate BOTH over the same effective-threshold grid
    # h_grid so the comparison is apples-to-apples; SPRT applies b_enter=k*h.
    # They should then agree numerically -- an empirical confirmation of the
    # Page-CUSUM = repeated-SPRT equivalence, not an artifact of grid mismatch.
    h_grid = np.round(np.arange(0.001, 0.40, 0.001), 4)
    k = DELTA / (sigma * sigma)

    for h in h_grid:
        det = (lambda s, init=False, h=h: d_cusum(s, h_enter=h, sigma=sigma,
                                                  init=init))
        if _worstcase_fs(det, sigma, LONG_N, seed) <= budget:
            dets["cusum"] = (det, {"nu": DELTA / 2.0,
                                   "h_enter": round(float(h), 4),
                                   "h_leave": round(float(h) * COST_RATIO, 4)})
            break
    else:
        h = 0.40
        dets["cusum"] = ((lambda s, init=False: d_cusum(s, h_enter=h,
                          sigma=sigma, init=init)),
                         {"nu": DELTA / 2.0, "h_enter": h,
                          "h_leave": round(h * COST_RATIO, 4)})

    for h in h_grid:
        b = float(k * h)
        det = (lambda s, init=False, b=b: d_sprt(s, sep=DELTA, sigma=sigma,
                                                 b_enter=b, init=init))
        if _worstcase_fs(det, sigma, LONG_N, seed) <= budget:
            dets["sprt"] = (det, {"sep": DELTA, "b_enter": round(b, 3),
                                  "b_leave": round(b * COST_RATIO, 3),
                                  "eff_h": round(float(h), 4)})
            break
    else:
        b = float(k * 0.40)
        dets["sprt"] = ((lambda s, init=False: d_sprt(s, sep=DELTA,
                         sigma=sigma, b_enter=b, init=init)),
                        {"sep": DELTA, "b_enter": round(b, 3),
                         "b_leave": round(b * COST_RATIO, 3), "eff_h": 0.40})
    return dets


# ==========================================================================
# probability calibration (strategy #6): isotonic (PAV) + Platt, 5-fold ECE
# ==========================================================================
def pav(x, y):
    """Pool-Adjacent-Violators isotonic regression. x sorted ascending, y in
    {0,1}. Returns fitted step values g(x) (non-decreasing)."""
    n = len(y)
    val = y.astype(float).copy()
    wgt = np.ones(n)
    # stack of (value, weight, start_index)
    v_st, w_st, i_st = [], [], []
    for i in range(n):
        cv, cw = val[i], wgt[i]
        while v_st and v_st[-1] > cv:
            pv, pw = v_st.pop(), w_st.pop()
            i_st.pop()
            cv = (pv * pw + cv * cw) / (pw + cw)
            cw = pw + cw
        v_st.append(cv)
        w_st.append(cw)
        i_st.append(i)
    # expand pooled blocks back to per-sample fitted values
    out = np.empty(n)
    idx = 0
    for v, w in zip(v_st, w_st):
        cnt = int(round(w))
        out[idx:idx + cnt] = v
        idx += cnt
    return out


def isotonic_fit(scores, y):
    """Fit isotonic map on (scores,y). Return callable p(score) via interp."""
    order = np.argsort(scores, kind="mergesort")
    xs = scores[order]
    g = pav(xs, y[order])
    # collapse to unique x for monotone interpolation
    ux, first = np.unique(xs, return_index=True)
    uy = g[first]

    def predict(q):
        return np.interp(q, ux, uy, left=uy[0], right=uy[-1])
    return predict


def platt_fit(scores, y, iters=500, lr=0.5):
    """1-D logistic p = sigmoid(a*z + b), z standardized score."""
    mu, sd = scores.mean(), scores.std() + 1e-12
    z = (scores - mu) / sd
    a, b = 0.0, 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(a * z + b)))
        ga = np.mean((p - y) * z)
        gb = np.mean(p - y)
        a -= lr * ga
        b -= lr * gb

    def predict(q):
        zz = (q - mu) / sd
        return 1.0 / (1.0 + np.exp(-(a * zz + b)))
    return predict


def ece(probs, y, nbins=10):
    """Expected calibration error (equal-width bins)."""
    edges = np.linspace(0, 1, nbins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (probs > lo) & (probs <= hi) if lo > 0 else (probs >= lo) & (probs <= hi)
        if not m.any():
            continue
        conf = probs[m].mean()
        acc = y[m].mean()
        e += (m.mean()) * abs(acc - conf)
    return float(e)


def calibration_cv(scores, y, k=5, seed=0):
    """5-fold held-out ECE for uncalibrated / isotonic / Platt."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    raw = (scores - scores.min()) / (scores.max() - scores.min())  # naive [0,1]
    out = {"raw": [], "isotonic": [], "platt": []}
    for f in folds:
        te = np.zeros(len(y), bool)
        te[f] = True
        tr = ~te
        out["raw"].append(ece(raw[te], y[te]))
        piso = isotonic_fit(scores[tr], y[tr])
        out["isotonic"].append(ece(piso(scores[te]), y[te]))
        ppl = platt_fit(scores[tr], y[tr])
        out["platt"].append(ece(ppl(scores[te]), y[te]))
    return {kk: (float(np.mean(v)), float(np.std(v))) for kk, v in out.items()}


# ==========================================================================
# driver
# ==========================================================================
_near_pool = None


def main() -> int:
    global _near_pool
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(Path(__file__).resolve().parent
                    / ".." / "results" / "scratch_frame_stats.csv"))
    args = ap.parse_args()

    D = css.load(Path(args.csv))
    d16, y = D["dark16"], D["label"].astype(int)
    n_all = len(y)

    # near-boundary base pool (real frames within +/-0.03 of t) for steady base
    near = d16[np.abs(d16 - T) <= 0.03]
    _near_pool = near
    print(f"# checker_temporal.py  (strategy #3 temporal layer + #6 calib)")
    print(f"# frames={n_all}  pos={int(y.sum())}  neg={int((y==0).sum())}  "
          f"t={T}  delta={DELTA}")
    print(f"# near-boundary base pool |dark16-{T}|<=0.03 : n={near.size} "
          f"[{near.min():.4f},{near.max():.4f}]")
    print(f"# jitter sigma: median={SIGMAS['median']:.5f} "
          f"p95={SIGMAS['p95']:.5f}  (measured ph16_dark16_std)")
    print(f"# false-switch budget: <=1 / {FS_BUDGET_FRAMES} frames "
          f"(1 / 10 min @ {FPS} fps); cost ratio C_miss/C_FA={COST_RATIO:.3f}")

    # ---------- Pareto: detection delay vs false-switch rate ----------
    for sname, sigma in SIGMAS.items():
        print(f"\n===== sigma = {sigma:.5f} ({sname}) =====")
        dets = calibrate(sigma, SEED)
        print("calibrated parameters (fastest setting within FS budget):")
        for name in ("single", "schmitt", "kofn", "cusum", "sprt"):
            print(f"  {name:8s} {dets[name][1]}")
        print("\n| detector | FS/100fr steady | flicker sw/100fr | "
              "ramp delay | ramp det% | step delay | step det% |")
        print("|---|---|---|---|---|---|---|")
        for name in ("single", "schmitt", "kofn", "cusum", "sprt"):
            det = dets[name][0]
            fs = false_switches(det, near, sigma, STEADY_N, NTRIAL, SEED + 1)
            fl = flicker_switches(det, sigma, NTRIAL, SEED + 2)
            rd, rdet, _ = detect_delay(det, ramp_seq, sigma, NTRIAL, SEED + 3)
            sd, sdet, _ = detect_delay(det, step_seq, sigma, NTRIAL, SEED + 4)
            print(f"| {name} | {fs:.3f} | {fl:.3f} | {rd:.2f} | {rdet:.3f} | "
                  f"{sd:.2f} | {sdet:.3f} |")

    # ---------- calibration (#6) ----------
    print("\n===== probability calibration (#6): 5-fold held-out ECE =====")
    cal = calibration_cv(d16, y, k=5, seed=0)
    print("| map | ECE mean+-std |")
    print("|---|---|")
    for m in ("raw", "isotonic", "platt"):
        mu, sd = cal[m]
        print(f"| {m} | {mu:.4f}+-{sd:.4f} |")
    # full-data isotonic map summary (the 256-entry LUT would sample this)
    piso = isotonic_fit(d16, y)
    grid = np.linspace(d16.min(), d16.max(), 9)
    print("\nfull-data isotonic map p(H1|dark16) at sample points:")
    print("  dark16: " + " ".join(f"{g:.3f}" for g in grid))
    print("  p(H1) : " + " ".join(f"{piso(g):.3f}" for g in grid))
    print(f"  p(H1|dark16={T}) = {float(piso(T)):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
