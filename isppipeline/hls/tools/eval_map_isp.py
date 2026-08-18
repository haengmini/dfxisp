#!/usr/bin/env python3
"""BLC recalibration ablation (re-run), SonyNOD real-RAW mAP swept over
BLC_OFFSET, on the CORRECTED canonical-matched pipeline files.

Companion to baseline_isp_pipeline.py / low_light_isp_pipeline.py /
checker.py -- the new, independent pipeline trio that mirrors
src/dfxisp_accel.cpp's actual gain/gamma (gamma-2.0 shared GAMMA2_LUT,
GAIN_NORMAL=1.25x, GAIN_LOWLIGHT=2.0x), superseding the archived
newrm_pipeline_blcfix.py used for the original ablation (which used the
wrong gain/gamma -- gamma-2.2/2.5/none instead of the canonical shared
gamma-2.0 -- so that result, in
results/realraw-sonynod-benchmark-2026-07-06.md §6ter, is invalidated and
this script reproduces the same sweep shape against the corrected
pipeline). See results/isp-pipeline-recalibration-2026-07-08.md.

"none" is intentionally excluded: it bypasses the BLC/WB/gain/gamma core
entirely and is out of scope for this ablation (same rationale as the
archived eval_map_newrm_blcfix.py).

Usage:
  python3 eval_map_isp.py --root ../../../sonynod_test \
      --blc-offsets 0,8,16,24,32,48,64,96,128,192,256 --tag SonyNOD-ISPFix \
      --model yolov8n.pt --out ../results/map_isp_sonynod_blcfix_yolov8n.csv

--blc-offsets is in native 12-bit BLC_LEVEL12 units (2026-08-18) -- the
pipeline is 12-bit throughout (baseline_isp_pipeline.py/
low_light_isp_pipeline.py's blc_offset override was previously 8-bit-
equivalent units, e.g. old value 2 == 32 in 12-bit terms; that convention
forced BLC ablations onto a 16-wide grid even though nothing about the
pipeline is 8-bit). Old-style runs used --blc-offsets 0,1,2,4,8,16, which is
equivalent to 0,16,32,64,128,256 under the new convention.

The default sweep grid is sw/sim/blc/blc_sim.py's SIGNAL_LEVELS list
truncated at 256 (the highest BLC value ever measured, isp-pipeline-
recalibration-2026-07-08.md; mAP was already collapsing there, 0.0372 vs the
0.214 peak, so nothing above it is worth the GPU time) -- same dense-near-
zero/coarse-at-the-tail shape as that sim's signal sweep, now covering the
full range instead of just the 16-32 tie zone the old 6-point grid left
unresolved.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import struct
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

import baseline_isp_pipeline as PB
import low_light_isp_pipeline as PL
import checker as PC
import default_isp_pipeline as PD
import lowlight_isp_pipeline as PW
from model_paths import resolve_yolo_model

ARMS = ["normal", "lowlight", "adaptive"]

# v2 arms (2026-08-06): default_ISP (Vitis-Vision-ordered standard arm) and
# lowlight_ISP (principle-derived low-light arm), each with its ablation axes
# as separate arm names. Their black level is a fixed constant coupled to the
# range-restore multiplier, so they do NOT participate in the BLC sweep --
# main() refuses to run them across multiple offsets rather than emitting
# duplicate rows labelled as different BLC values.
ARMS_V2 = [
    "default_isp", "default_isp_noawb",
    "lowlight_isp",
    # binning ablation (stage 1)
    "lowlight_isp_subsample",
    # tone-curve ablation (stage 5): the deployed gamma 2.0 vs the GAT it
    # replaced, and plain truncation as the floor. Only stage (5) differs.
    "lowlight_isp_gat", "lowlight_isp_linear",
]


def jpg_dims(p: Path):
    d = p.read_bytes(); i = 2
    while i < len(d):
        if d[i] != 0xFF:
            i += 1; continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3):
            h = struct.unpack(">H", d[i + 5:i + 7])[0]; w = struct.unpack(">H", d[i + 7:i + 9])[0]
            return w, h
        ln = struct.unpack(">H", d[i + 2:i + 4])[0]; i += 2 + ln
    raise ValueError(f"no SOF in {p}")


def load_adaptive_verdicts(manifest: Path) -> dict[str, bool]:
    """stem -> adaptive-tau LOW_LIGHT verdict, precomputed by
    build_matched_splits.py (checker_adaptive_tau.tau_for_frame-based, the
    #1-strengthening-plan-adopted Path A scheme -- see
    checker-status-2026-07-10.md SS2 #1) and carried in the split manifest's
    `adaptive_verdict_lowlight` column. This is NOT the same as
    checker.py's selected_mode() (the deployed rule -- C1 dark16>0.62 since
    2026-07-20, C0 dark50>0.80 before that) --
    conflating the two was a 2026-07-15 handoff bug (see
    results/HANDOFF-lod-pascal-isp-simulation-2026-07-15.md SS4 vs the actual
    eval_map_isp.py code at that time)."""
    with manifest.open() as f:
        return {row["stem"]: row["adaptive_verdict_lowlight"] == "True" for row in csv.DictReader(f)}


def render_arm(bayer, w, h, arm, blc_offset, stem=None, adaptive_verdicts=None,
               wb_lowlight=None):
    """Synthesize the uint8 RGB image for a given arm + swept BLC offset,
    using the new independent normal/lowlight/checker modules.

    wb_lowlight: optional (R,G,B) Q8 WB override applied to the LOW-LIGHT path
    only (the normal path keeps the deployed shared gains). None = unchanged."""
    if arm == "normal":
        return PB.run_arm(bayer, w, h, "normal", blc_offset=blc_offset)
    if arm == "lowlight":
        return PL.run_arm(bayer, w, h, "lowlight", blc_offset=blc_offset, wb=wb_lowlight)
    if arm in ("default_isp", "default_isp_noawb"):
        return PD.run_arm(bayer, w, h, arm)
    if arm.startswith("lowlight_isp"):
        return PW.run_arm(bayer, w, h, arm)
    if arm == "adaptive":
        if adaptive_verdicts is not None:
            if stem not in adaptive_verdicts:
                raise KeyError(f"stem {stem!r} missing from --manifest adaptive verdicts")
            is_lowlight = adaptive_verdicts[stem]
        else:
            # Back-compat fallback for standalone (non-split, no --manifest)
            # runs: the deployed C0 checker, NOT adaptive-tau. Prefer passing
            # --manifest whenever a build_matched_splits.py manifest exists.
            is_lowlight = PC.selected_mode(bayer, w, h) == "lowlight"
        if is_lowlight:
            return PL.run_arm(bayer, w, h, "lowlight", blc_offset=blc_offset, wb=wb_lowlight)
        return PB.run_arm(bayer, w, h, "normal", blc_offset=blc_offset)
    raise ValueError(f"unsupported arm for BLC ablation: {arm}")


def _render_one(stem, raw_dir: Path, lab_dir: Path, img_dir: Path, work: Path,
                arms, blc_offset, adaptive_verdicts, wb_lowlight) -> int:
    """Render every arm for one frame. Self-contained so it can run in a
    worker process: each frame reads its own raw and writes its own outputs,
    with no shared state."""
    w, h = jpg_dims(img_dir / f"{stem}.jpg")
    bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
    if bayer.size != w * h:
        return 0
    bayer = bayer.reshape(h, w)
    for a in arms:
        out = render_arm(bayer, w, h, a, blc_offset, stem=stem,
                         adaptive_verdicts=adaptive_verdicts, wb_lowlight=wb_lowlight)
        Image.fromarray(out).save(work / a / "images" / f"{stem}.jpg", quality=95)
        shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
    return 1


def default_jobs() -> int:
    """Workers that fit in RAM. A 20 MP frame peaks around 1 GB of int32
    intermediates per worker, so cap by memory as well as by cores; rendering
    is pure CPU numpy (no GPU involvement at any point)."""
    cores = os.cpu_count() or 1
    try:
        gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1 << 30)
        by_mem = max(1, int(gb // 2))
    except (ValueError, OSError):
        by_mem = cores
    return max(1, min(cores, by_mem, 8))


def build_arm_images(root: Path, work: Path, arms, limit: int, blc_offset: int,
                      adaptive_verdicts=None, wb_lowlight=None, jobs=None) -> int:
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists())
    if limit:
        stems = stems[:limit]
    for a in arms:
        (work / a / "images").mkdir(parents=True, exist_ok=True)
        (work / a / "labels").mkdir(parents=True, exist_ok=True)

    jobs = default_jobs() if jobs is None else max(1, int(jobs))
    fn = partial(_render_one, raw_dir=raw_dir, lab_dir=lab_dir, img_dir=img_dir,
                 work=work, arms=arms, blc_offset=blc_offset,
                 adaptive_verdicts=adaptive_verdicts, wb_lowlight=wb_lowlight)
    if len(stems) <= 1:
        return sum(fn(s) for s in stems)
    # Full-resolution frames can leave large NumPy allocator arenas resident.
    # Recycle after each frame so the CPU-only evaluator remains bounded on
    # modest-RAM hosts (at the cost of small process startup overhead).
    with Pool(processes=jobs, maxtasksperchild=1) as pool:
        return sum(pool.imap_unordered(fn, stems, chunksize=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="../../../sonynod_test")
    ap.add_argument("--blc-offsets", default="0,8,16,24,32,48,64,96,128,192,256",
                     help="comma-separated BLC_OFFSET sweep values, in native 12-bit "
                          "BLC_LEVEL12 units (2026-08-18; previously 8-bit-equivalent "
                          "units, e.g. the old default '0,1,2,4,8,16' meant 0/16/32/64/"
                          "128/256 in 12-bit terms -- pass those 12-bit values directly now). "
                          "Default grid mirrors sw/sim/blc/blc_sim.py's SIGNAL_LEVELS "
                          "(dense near 0, coarser toward the tail), truncated at 256 -- "
                          "the highest value ever measured, where mAP was already "
                          "collapsing (see module docstring)")
    ap.add_argument("--work", default="data/_isp_work")
    ap.add_argument("--tag", default="SonyNOD-ISPFix")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--jobs", type=int, default=None,
                    help="parallel render workers (default: cores capped by RAM). "
                         "Rendering is CPU numpy and dominates runtime; detection "
                         "inference is a rounding error next to it.")
    ap.add_argument("--out", default="results/map_isp_sonynod_blcfix_yolov8n.csv")
    ap.add_argument("--manifest", type=Path, default=None,
                     help="build_matched_splits.py manifest CSV (lod/pascal/shuffle_split_*.csv) "
                          "supplying precomputed adaptive-tau verdicts per stem for the "
                          "'adaptive' arm. Required for LOD/PASCAL/Shuffle split runs -- without "
                          "it, 'adaptive' silently falls back to the deployed checker "
                          "(checker.selected_mode; C1 dark16>0.62 since 2026-07-20), which is "
                          "NOT the adopted adaptive-tau scheme.")
    ap.add_argument("--wb-lowlight", default=None,
                     help="mode-specific WB override for the LOW-LIGHT path only, as 'R,G,B' "
                          "Q8 gains (e.g. '435,256,616'). Omit to keep the deployed shared "
                          "gains (286,256,307). The normal path is never affected.")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    blc_offsets = [int(v.strip()) for v in args.blc_offsets.split(",") if v.strip() != ""]
    v2 = [a for a in arms if a in ARMS_V2]
    if v2 and len(blc_offsets) > 1:
        raise SystemExit(
            f"arms {v2} have a fixed black level (coupled to their range-restore "
            f"multiplier) and do not participate in the BLC sweep; got "
            f"{len(blc_offsets)} offsets. Re-run them with a single "
            f"--blc-offsets value, or drop them from --arms.")
    wb_lowlight = None
    if args.wb_lowlight:
        parts = [int(v.strip()) for v in args.wb_lowlight.split(",") if v.strip() != ""]
        if len(parts) != 3:
            raise SystemExit(f"--wb-lowlight needs 3 comma-separated Q8 gains, got {args.wb_lowlight!r}")
        wb_lowlight = tuple(parts)
    wb_label = "shared" if wb_lowlight is None else ":".join(str(v) for v in wb_lowlight)
    root = Path(args.root)
    adaptive_verdicts = load_adaptive_verdicts(args.manifest) if args.manifest else None

    from ultralytics import YOLO
    import yaml  # type: ignore
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)

    rows = []
    n = None
    for blc in blc_offsets:
        work = Path(args.work) / f"{args.tag.lower()}_blc{blc}_wb{wb_label.replace(':', '_')}"
        n = build_arm_images(root, work, arms, args.limit, blc, jobs=args.jobs,
                             adaptive_verdicts=adaptive_verdicts, wb_lowlight=wb_lowlight)
        print(f"[{args.tag}] blc_offset={blc} wb_lowlight={wb_label}: built arm images for {n} frames: {arms}")
        for a in arms:
            ds = work / a
            yml = ds / "data.yaml"
            yml.write_text(yaml.safe_dump({
                "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
                "names": [str(i) for i in range(80)],
            }))
            m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False, plots=False)
            map5095, map50 = float(m.box.map), float(m.box.map50)
            print(f"[{args.tag}] blc_offset={blc:2d} wb={wb_label:12s} {a:9s} "
                  f"mAP@[.5:.95]={map5095:.4f}  mAP@50={map50:.4f}")
            rows.append((args.tag, blc, wb_label, a, map5095, map50, model_path, n))

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "blc_offset", "wb_lowlight", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for tag, blc, wbl, a, m5095, m50, model_path, n in rows:
            wr.writerow([tag, blc, wbl, a, f"{m5095:.4f}", f"{m50:.4f}", model_path, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
