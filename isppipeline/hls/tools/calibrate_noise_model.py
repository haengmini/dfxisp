#!/usr/bin/env python3
"""Estimate the Poisson-Gaussian noise model sigma^2 = a*y + b from real RAW.

Canonical status: **measurement tool**. Produces the `a` and `b` that
src/lowlight_isp.cpp's GAT/VST tone curve needs (A_Q8, B_DN2). Until this is
run, those constants are estimates and every claim resting on the curve shape
must say so (src/lowlight_isp.md "parameters").

Method (single-image photon transfer, Foi et al. 2008 style -- EMVA1288 flat
fields are not available for these sensors):

  1. Split the CFA into its four Bayer site planes; noise statistics are
     per-site, and mixing sites would blend different channel gains.
  2. Tile each plane into blocks and take (mean, variance) per block.
  3. In each mean bin, keep a LOW percentile of the block variances. A flat
     block's variance is pure noise; a textured block's is inflated by
     structure, never deflated -- so the low percentile of many blocks tracks
     the noise floor and rejects texture without needing a flat-field rig.
  4. Correct the percentile for estimator bias: a block variance over n
     samples is chi-square distributed with n-1 dof, so the p-th percentile of
     a FLAT block's estimate sits below the true variance by a known factor
     (Wilson-Hilferty). Without this the fit is biased low -- badly enough to
     produce physically impossible negative intercepts.
  5. Least-squares fit variance = a*mean + b over the binned points, restricted
     to the dark region (--max-mean). Flat blocks are abundant there, textured
     ones dominate higher up and inflate the slope; the dark region is also the
     only place where b (the read-noise floor) is observable rather than
     extrapolated -- and it is exactly the region the GAT offset term shapes.

Sources used 2026-08-06: Sony RX100 VII night ARWs from the Drive folder
`Sony-ARW` (id 1SH3Pb4BidscXwDRqbkQX2gNDhJ-aaZcq, 100 frames, ISO 6400) and
PASCALRAW original NEFs. Local copies were removed after measuring; re-download
from Drive to reproduce.

Requires rawpy for the 12-bit originals. The repo's `raw_bin` conversions are
NOT usable here: they are shift8 (8-bit values scaled up), so every sample is a
multiple of 256 and the read-noise scale we are trying to measure has been
quantised away.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np

try:
    import rawpy
except ImportError:  # pragma: no cover
    rawpy = None


def site_planes(raw: np.ndarray, pattern: np.ndarray, desc: bytes, black=None):
    """Return {label: plane} for the four CFA sites of a 2x2 pattern.

    `black` (per-CFA-index pedestal, as rawpy reports it) is subtracted so the
    fit is against signal above the pedestal -- otherwise the intercept absorbs
    the pedestal instead of the read noise.
    """
    out = {}
    seen: dict[str, int] = {}
    for dy in (0, 1):
        for dx in (0, 1):
            idx = pattern[dy][dx]
            ch = chr(desc[idx])
            seen[ch] = seen.get(ch, 0) + 1
            label = ch if seen[ch] == 1 else f"{ch}{seen[ch]}"
            plane = raw[dy::2, dx::2].astype(np.float64)
            if black is not None:
                plane = plane - float(black[idx])
            out[label] = plane
    return out


def block_stats(plane: np.ndarray, block: int):
    """(mean, variance) per block, computed with the unbiased estimator."""
    h = plane.shape[0] // block * block
    w = plane.shape[1] // block * block
    p = plane[:h, :w].astype(np.float64)
    t = p.reshape(h // block, block, w // block, block).transpose(0, 2, 1, 3)
    t = t.reshape(-1, block * block)
    return t.mean(axis=1), t.var(axis=1, ddof=1)


def chi2_percentile_factor(dof: int, pct: float) -> float:
    """E[percentile of the sample variance] / true variance, Wilson-Hilferty.

    A sample variance over `dof+1` samples is chi2(dof)/dof times the true
    variance, so taking a low percentile systematically under-estimates. This
    returns that factor so it can be divided out.
    """
    from math import sqrt
    # inverse normal CDF via Acklam-style rational approximation is overkill;
    # the percentiles used here are tabulated.
    z = {1.0: -2.3263, 2.0: -2.0537, 5.0: -1.6449, 10.0: -1.2816,
         25.0: -0.6745, 50.0: 0.0}.get(pct)
    if z is None:
        return 1.0
    t = 2.0 / (9.0 * dof)
    return (1.0 - t + z * sqrt(t)) ** 3


def fit_noise_model(means, variances, white, nbins, pct, min_per_bin,
                    max_mean=None, bias_factor=1.0):
    """Bin by mean, take the bias-corrected low variance percentile, fit a line."""
    # Drop blocks near saturation: clipping truncates the noise distribution.
    keep = means < 0.9 * white
    if max_mean is not None:
        keep &= means < max_mean
    means, variances = means[keep], variances[keep]
    if means.size == 0:
        return None

    edges = np.linspace(means.min(), means.max(), nbins + 1)
    xs, ys, ns = [], [], []
    for i in range(nbins):
        sel = (means >= edges[i]) & (means < edges[i + 1])
        n = int(sel.sum())
        if n < min_per_bin:
            continue
        xs.append(float(means[sel].mean()))
        ys.append(float(np.percentile(variances[sel], pct)) / bias_factor)
        ns.append(n)
    if len(xs) < 3:
        return None
    a, b = np.polyfit(np.array(xs), np.array(ys), 1)
    resid = np.array(ys) - (a * np.array(xs) + b)
    ss_tot = float(((np.array(ys) - np.mean(ys)) ** 2).sum())
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    return {"a": float(a), "b": float(b), "r2": r2,
            "points": list(zip(xs, ys, ns))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-glob", required=True,
                    help="glob for 12-bit RAW originals, e.g. '.../raw/*.nef'")
    ap.add_argument("--limit", type=int, default=8, help="frames to use")
    ap.add_argument("--block", type=int, default=16)
    ap.add_argument("--bins", type=int, default=40)
    ap.add_argument("--pct", type=float, default=10.0,
                    help="variance percentile kept per bin (noise floor)")
    ap.add_argument("--min-per-bin", type=int, default=200)
    ap.add_argument("--max-mean", type=float, default=512.0,
                    help="fit only below this mean (dark region, where flat "
                         "blocks are abundant and b is observable)")
    args = ap.parse_args()

    if rawpy is None:
        print("ERROR: rawpy is required for the 12-bit originals.")
        return 2

    files = sorted(glob.glob(args.raw_glob))[: args.limit]
    if not files:
        print(f"ERROR: no files matched {args.raw_glob}")
        return 2

    per_site: dict[str, list] = {}
    white = None
    black = None
    for path in files:
        # Statistics must be computed inside the context manager: the site
        # planes are numpy views into rawpy's buffer, which is freed on exit.
        with rawpy.imread(path) as r:
            white = r.white_level
            black = list(r.black_level_per_channel)
            planes = site_planes(r.raw_image_visible, r.raw_pattern, r.color_desc,
                                 r.black_level_per_channel)
            for label, plane in planes.items():
                m, v = block_stats(plane, args.block)
                per_site.setdefault(label, []).append((m, v))

    dof = args.block * args.block - 1
    bias = chi2_percentile_factor(dof, args.pct)
    print(f"frames={len(files)}  block={args.block}  pct={args.pct}  "
          f"max_mean={args.max_mean}")
    print(f"percentile bias factor (chi2, dof={dof}): {bias:.4f} -- divided out")
    print(f"white_level={white}  black_level_per_channel={black}")
    print(f"{'site':>5} | {'a (DN)':>9} | {'b (DN^2)':>10} | {'sigma_read':>10} | {'R^2':>6}")
    print("-" * 56)

    all_m, all_v = [], []
    results = {}
    for label in sorted(per_site):
        m = np.concatenate([x[0] for x in per_site[label]])
        v = np.concatenate([x[1] for x in per_site[label]])
        all_m.append(m)
        all_v.append(v)
        fit = fit_noise_model(m, v, white, args.bins, args.pct, args.min_per_bin,
                              args.max_mean, bias)
        if fit is None:
            print(f"{label:>5} | {'(too few blocks)':>41}")
            continue
        results[label] = fit
        sr = fit["b"] ** 0.5 if fit["b"] > 0 else float("nan")
        print(f"{label:>5} | {fit['a']:9.4f} | {fit['b']:10.2f} | {sr:10.2f} | {fit['r2']:6.3f}")

    am = np.concatenate(all_m)
    av = np.concatenate(all_v)

    # Direct bound on b, no extrapolation. At the darkest observable signal
    # var = a*y + b with a*y >= 0, so the (bias-corrected) flat-block variance
    # there is an UPPER bound on b -- and subtracting a*y for the fitted slope
    # range brackets it. This is the only b statement natural images support:
    # the line fit's intercept is an extrapolation and comes out negative.
    dark = am < 5.0
    if dark.sum() > 500:
        y_dark = float(am[dark].mean())
        v_dark = float(np.percentile(av[dark], args.pct)) / bias
        print()
        print(f"darkest-bin bound (mean={y_dark:.2f} DN, n={int(dark.sum())}):")
        print(f"  flat-block variance there = {v_dark:.2f} DN^2  -> b <= {v_dark:.2f}")

    fit = fit_noise_model(am, av, white, args.bins, args.pct, args.min_per_bin,
                          args.max_mean, bias)
    if fit:
        results["ALL"] = fit
        sr = fit["b"] ** 0.5 if fit["b"] > 0 else float("nan")
        print("-" * 56)
        print(f"{'ALL':>5} | {fit['a']:9.4f} | {fit['b']:10.2f} | {sr:10.2f} | {fit['r2']:6.3f}")
        print()
        print("GAT constants for src/lowlight_isp.cpp (12-bit domain):")
        print(f"  A_Q8  = {round(fit['a'] * 256)}     # a = {fit['a']:.4f} DN")
        print(f"  B_DN2 = {round(fit['b'])}     # b = {fit['b']:.2f} DN^2"
              f"  (sigma_read = {sr:.2f} DN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
