#!/usr/bin/env python3
"""Additive Path-A adaptive-tau experiments (2026-07-20).

Builds one 256-bin shift8 histogram per frame once, persists the complete cache,
and performs every tau/cutoff sweep using cumulative-histogram lookups only.
No production checker source is modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np


BUCKETS = [(0, 400), (400, 800), (800, 1600), (1600, 3200),
           (3200, 6400), (6400, math.inf)]
BUCKET_NAMES = ["[0,400)", "[400,800)", "[800,1600)", "[1600,3200)",
                "[3200,6400)", "[6400,inf)"]
CORPORA = ("pascalraw", "sonynod")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def bucket_index(iso: float) -> int:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= iso < hi:
            return i
    raise ValueError(iso)


def is_train(stem: str, corpus: str, bucket: int) -> bool:
    # Stable pseudo-random split, independently balanced within corpus/bucket.
    digest = hashlib.sha256(f"adaptive-tau-v1:{corpus}:{bucket}:{stem}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % 10 < 7


def load_rows(root: Path) -> dict[str, list[dict]]:
    specs = {
        "pascalraw": (root / "isppipeline/hls/results/adaptive_tau_pascalraw_results.csv",
                      root / "data/pascalraw_test/raw_bin", 0.0, 4095.0),
        "sonynod": (root / "isppipeline/hls/results/adaptive_tau_sonynod_2026-07-13.csv",
                    root / "data/sonynod_test/raw_bin", 800.0, 16380.0),
    }
    out = {}
    for corpus, (csv_path, bin_dir, black, white) in specs.items():
        rows = []
        for r in read_csv(csv_path):
            stem = r["stem"]
            iso = float(r["iso"])
            exposure = float(r["exposure_s"])
            b = bucket_index(iso)
            rows.append({
                "corpus": corpus, "stem": stem, "iso": iso,
                "exposure_s": exposure, "black": black, "white": white,
                "bin": bin_dir / f"{stem}.bin", "bucket": b,
                "train": is_train(stem, corpus, b),
                "csv_dark16": float(r["dark16"]),
                "csv_current_thr": int(r["adaptive_thr8"]),
                "csv_dark50": float(r["dark50"]),
                "csv_dark_adaptive": float(r["dark_adaptive"]),
            })
        out[corpus] = rows
    return out


def build_or_load_cache(cache_path: Path, rows_by_corpus: dict[str, list[dict]],
                        rebuild: bool) -> tuple[np.ndarray, list[str], str, float]:
    expected = [f"{c}/{r['stem']}" for c in CORPORA for r in rows_by_corpus[c]]
    if cache_path.exists() and not rebuild:
        z = np.load(cache_path, allow_pickle=False)
        keys = z["keys"].astype(str).tolist()
        if keys != expected:
            raise RuntimeError("histogram cache key/order mismatch; use --rebuild-cache")
        return z["hist"], keys, "reused", 0.0

    start = time.monotonic()
    hist = np.empty((len(expected), 256), dtype=np.uint64)
    i = 0
    for corpus in CORPORA:
        for r in rows_by_corpus[corpus]:
            raw = np.fromfile(r["bin"], dtype="<u2")
            # This is the sole raw read and sole histogram construction per frame.
            hist[i] = np.bincount(raw >> 8, minlength=256)
            i += 1
            if i % 100 == 0 or i == len(expected):
                print(f"histograms {i}/{len(expected)}", flush=True)
    elapsed = time.monotonic() - start
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, hist=hist,
                        keys=np.asarray(expected, dtype=f"<U{max(map(len, expected))}"),
                        build_count=np.asarray([1], dtype=np.uint8),
                        raw_reads=np.asarray([len(expected)], dtype=np.int64))
    return hist, expected, "built", elapsed


def ratio_at(cdf: np.ndarray, totals: np.ndarray, threshold8) -> np.ndarray:
    """Strict pixel < threshold8. threshold may be scalar or length-N integer."""
    t = np.asarray(threshold8, dtype=np.int16)
    if t.ndim == 0:
        t = np.full(len(cdf), int(t), dtype=np.int16)
    t = np.clip(t, 0, 256)
    count = np.zeros(len(cdf), dtype=np.uint64)
    nz = t > 0
    count[nz] = cdf[np.nonzero(nz)[0], t[nz] - 1]
    return count / totals


def current_threshold(rows: list[dict], mode: str) -> np.ndarray:
    vals = []
    for r in rows:
        g = r["iso"] / 100.0
        g0 = 8.0
        rel = (r["exposure_s"] * g) / ((1.0 / 60.0) * g0)
        floor_dn = 5.0 * 3.0 * g / 0.25
        scene_dn = 5.0 * 3.0 * g0 / 0.25 * (min(rel, 1.0) if mode == "rcap" else rel)
        signal_dn = floor_dn if mode == "floor" else max(floor_dn, scene_dn)
        vals.append(int(round(signal_dn / (r["white"] - r["black"]) * 255.0)))
    return np.clip(vals, 0, 255).astype(np.int16)


def fitted_threshold(rows: list[dict], c: float) -> np.ndarray:
    return np.clip(np.rint(c * np.asarray([r["iso"] / 100.0 for r in rows])), 0, 255).astype(np.int16)


def score(recall: float, ft: float) -> float:
    return recall - ft


def choose_sensor_cs(rows: list[dict], cdf: np.ndarray, totals: np.ndarray) -> dict[str, float]:
    # With one label per corpus, Sony maximizes recall and Nikon minimizes FT.
    # Tie-break toward the smaller threshold to avoid gratuitous expansion.
    grid = np.arange(0.0, 32.0001, 0.25)
    result = {}
    for corpus in CORPORA:
        idx = np.asarray([i for i, r in enumerate(rows) if r["corpus"] == corpus and r["train"]])
        best = None
        for c in grid:
            rr = ratio_at(cdf[idx], totals[idx], fitted_threshold([rows[i] for i in idx], c))
            val = np.mean(rr > 0.62) if corpus == "sonynod" else -np.mean(rr > 0.62)
            candidate = (float(val), -float(c), float(c))
            if best is None or candidate > best:
                best = candidate
        result[corpus] = best[2]
    return result


def best_cutoff(pos: np.ndarray, neg: np.ndarray) -> float:
    values = np.unique(np.concatenate((pos, neg)))
    candidates = np.unique(np.concatenate(([0.0], values, np.nextafter(values, -np.inf), [1.0])))
    best = None
    for cut in candidates:
        recall = float(np.mean(pos > cut)) if len(pos) else float("nan")
        ft = float(np.mean(neg > cut)) if len(neg) else float("nan")
        if not (np.isfinite(recall) and np.isfinite(ft)):
            continue
        candidate = (score(recall, ft), -abs(float(cut) - 0.62), -float(cut), float(cut))
        if best is None or candidate > best:
            best = candidate
    return 0.62 if best is None else best[3]


def choose_joint_scale_cut(rows: list[dict], cdf: np.ndarray, totals: np.ndarray,
                           mask: np.ndarray, base_thr: np.ndarray) -> tuple[float, float, float]:
    """Train-only joint search of tau scale and strict ratio cutoff."""
    best = None
    for scale in np.arange(0.0, 3.0001, 0.05):
        thr = np.clip(np.rint(base_thr * scale), 0, 255).astype(np.int16)
        rr = ratio_at(cdf, totals, thr)
        pos = rr[mask & np.asarray([r["corpus"] == "sonynod" for r in rows])]
        neg = rr[mask & np.asarray([r["corpus"] == "pascalraw" for r in rows])]
        if not len(pos) or not len(neg):
            continue
        cut = best_cutoff(pos, neg)
        j = float(np.mean(pos > cut) - np.mean(neg > cut))
        candidate = (j, -abs(float(scale) - 1.0), -abs(cut - 0.62), float(scale), cut)
        if best is None or candidate > best:
            best = candidate
    return (1.0, 0.62, float("nan")) if best is None else (best[3], best[4], best[0])


def metrics(rows: list[dict], ratios: dict[str, np.ndarray], cutoffs: dict[str, np.ndarray],
            splits=("all", "train", "holdout")) -> list[dict]:
    out = []
    corp = np.asarray([r["corpus"] for r in rows])
    buckets = np.asarray([r["bucket"] for r in rows])
    train = np.asarray([r["train"] for r in rows])
    for variant, values in ratios.items():
        cuts = cutoffs[variant]
        verdict = values > cuts
        for split in splits:
            sm = np.ones(len(rows), bool) if split == "all" else (train if split == "train" else ~train)
            for bi, bn in [(-1, "overall")] + list(enumerate(BUCKET_NAMES)):
                bm = sm if bi == -1 else sm & (buckets == bi)
                p = bm & (corp == "sonynod")
                n = bm & (corp == "pascalraw")
                rec = float(np.mean(verdict[p])) if p.any() else float("nan")
                ft = float(np.mean(verdict[n])) if n.any() else float("nan")
                out.append({"variant": variant, "split": split, "iso_bucket": bn,
                            "sony_n": int(p.sum()), "pascal_n": int(n.sum()),
                            "recall": rec, "false_trigger": ft,
                            "youden_j": rec - ft if np.isfinite(rec) and np.isfinite(ft) else float("nan")})
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument("--rebuild-cache", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    result_dir = root / "isppipeline/hls/results"
    cache_path = result_dir / "adaptive_tau_histograms-2026-07-20.npz"
    rows_by_corpus = load_rows(root)
    hist, keys, cache_status, build_seconds = build_or_load_cache(cache_path, rows_by_corpus, args.rebuild_cache)
    rows = [r for c in CORPORA for r in rows_by_corpus[c]]
    cdf = np.cumsum(hist, axis=1, dtype=np.uint64)
    totals = cdf[:, -1]

    thresholds = {
        "c0": np.full(len(rows), 50, dtype=np.int16),
        "c1": np.full(len(rows), 16, dtype=np.int16),
        "current_adaptive": current_threshold(rows, "current"),
        "tau_floor_only": current_threshold(rows, "floor"),
        "r_cap_1": current_threshold(rows, "rcap"),
    }
    sensor_cs = choose_sensor_cs(rows, cdf, totals)
    thresholds["fitted_sensor_c"] = np.concatenate([
        fitted_threshold(rows_by_corpus[c], sensor_cs[c]) for c in CORPORA])
    ratios = {k: ratio_at(cdf, totals, v) for k, v in thresholds.items()}

    # Verify threshold math against both supplied CSVs before calibration.
    csv_c1 = np.asarray([r["csv_dark16"] for r in rows])
    csv_cur = np.asarray([r["csv_dark_adaptive"] for r in rows])
    max_c1_diff = float(np.max(np.abs(ratios["c1"] - csv_c1)))
    max_cur_diff = float(np.max(np.abs(ratios["current_adaptive"] - csv_cur)))
    current_thr_mismatch = int(np.sum(thresholds["current_adaptive"] != np.asarray([r["csv_current_thr"] for r in rows])))
    if max_c1_diff > 5e-6 or max_cur_diff > 5e-12 or current_thr_mismatch:
        raise RuntimeError(f"CSV cross-check failed: c1={max_c1_diff} current={max_cur_diff} thr_mismatch={current_thr_mismatch}")

    fixed_cutoffs = {k: np.full(len(rows), 0.80 if k == "c0" else 0.62) for k in ratios}
    fixed_metrics = metrics(rows, ratios, fixed_cutoffs)

    # Pick the best *deployable* structural tau on TRAIN overall J.  The fitted
    # per-sensor model is intentionally excluded: sensor identity equals class
    # identity in these corpora, so its apparent performance is label leakage.
    candidates = ("tau_floor_only", "r_cap_1")
    train_overall = {(m["variant"]): m for m in fixed_metrics
                     if m["split"] == "train" and m["iso_bucket"] == "overall"}
    best_tau = max(candidates, key=lambda v: (train_overall[v]["youden_j"], v))

    corp = np.asarray([r["corpus"] for r in rows])
    bucket = np.asarray([r["bucket"] for r in rows])
    train = np.asarray([r["train"] for r in rows])
    best_ratios = ratios[best_tau]
    global_cut = best_cutoff(best_ratios[train & (corp == "sonynod")],
                             best_ratios[train & (corp == "pascalraw")])
    bucket_cuts = []
    for b in range(len(BUCKETS)):
        pos = best_ratios[train & (corp == "sonynod") & (bucket == b)]
        neg = best_ratios[train & (corp == "pascalraw") & (bucket == b)]
        bucket_cuts.append(best_cutoff(pos, neg) if len(pos) and len(neg) else global_cut)
    ratios[f"{best_tau}_joint_cutoff"] = best_ratios.copy()
    fixed_cutoffs[f"{best_tau}_joint_cutoff"] = np.asarray([bucket_cuts[r["bucket"]] for r in rows])

    # Literal joint calibration: scale tau_floor(g) and select the cutoff per
    # ISO stratum on train. Strata missing either class inherit the global pair.
    base_thr = thresholds[best_tau].astype(float)
    global_scale, global_joint_cut, _ = choose_joint_scale_cut(rows, cdf, totals, train, base_thr)
    joint_pairs = []
    for b in range(len(BUCKETS)):
        bm = train & (bucket == b)
        has_both = np.any(bm & (corp == "sonynod")) and np.any(bm & (corp == "pascalraw"))
        joint_pairs.append(choose_joint_scale_cut(rows, cdf, totals, bm, base_thr)[:2]
                           if has_both else (global_scale, global_joint_cut))
    joint_thr = np.asarray([int(round(base_thr[i] * joint_pairs[r["bucket"]][0]))
                            for i, r in enumerate(rows)], dtype=np.int16)
    joint_thr = np.clip(joint_thr, 0, 255)
    joint_name = f"{best_tau}_joint_tau_cutoff"
    thresholds[joint_name] = joint_thr
    ratios[joint_name] = ratio_at(cdf, totals, joint_thr)
    fixed_cutoffs[joint_name] = np.asarray([joint_pairs[r["bucket"]][1] for r in rows])
    all_metrics = metrics(rows, ratios, fixed_cutoffs)
    write_csv(result_dir / "adaptive-tau-improvement-metrics-2026-07-20.csv", all_metrics)

    frame_rows = []
    for i, r in enumerate(rows):
        fr = {k: r[k] for k in ("corpus", "stem", "iso", "exposure_s", "bucket", "train")}
        fr["bucket"] = BUCKET_NAMES[r["bucket"]]
        for v in ratios:
            fr[f"{v}_thr8"] = int(thresholds[v][i]) if v in thresholds else int(thresholds[best_tau][i])
            fr[f"{v}_ratio"] = float(ratios[v][i])
            fr[f"{v}_cutoff"] = float(fixed_cutoffs[v][i])
            fr[f"{v}_lowlight"] = bool(ratios[v][i] > fixed_cutoffs[v][i])
        frame_rows.append(fr)
    write_csv(result_dir / "adaptive-tau-improvement-frames-2026-07-20.csv", frame_rows)

    manifest = {
        "date": "2026-07-20", "cache": str(cache_path.relative_to(root)),
        "cache_status_this_run": cache_status, "cache_build_count": 1,
        "raw_reads_when_built": len(rows), "histograms": len(rows),
        "build_seconds": build_seconds, "sweeps_use": "np.cumsum lookup only",
        "counts": {c: len(rows_by_corpus[c]) for c in CORPORA},
        "sensor_c": sensor_cs, "best_tau_train": best_tau,
        "best_tau_selection": "train J among structural variants; fitted_sensor_c excluded due sensor/class confounding",
        "global_joint_cutoff": global_cut,
        "bucket_joint_cutoffs": dict(zip(BUCKET_NAMES, bucket_cuts)),
        "global_joint_tau_scale_cutoff": [global_scale, global_joint_cut],
        "bucket_joint_tau_scale_cutoffs": {name: list(pair) for name, pair in zip(BUCKET_NAMES, joint_pairs)},
        "crosscheck": {"max_abs_c1_ratio_diff_vs_csv": max_c1_diff,
                       "max_abs_current_ratio_diff_vs_csv": max_cur_diff,
                       "current_threshold_mismatches": current_thr_mismatch},
    }
    (result_dir / "adaptive-tau-improvement-run-2026-07-20.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
