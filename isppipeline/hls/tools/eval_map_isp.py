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
      --blc-offsets 0,1,2,4,8,16 --tag SonyNOD-ISPFix --model yolov8n.pt \
      --out ../results/map_isp_sonynod_blcfix_yolov8n.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import baseline_isp_pipeline as PB
import low_light_isp_pipeline as PL
import checker as PC
from model_paths import resolve_yolo_model

ARMS = ["normal", "lowlight", "adaptive"]


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
    checker.py's selected_mode() (the deployed C0 rule, dark50>0.80) --
    conflating the two was a 2026-07-15 handoff bug (see
    results/HANDOFF-lod-pascal-isp-simulation-2026-07-15.md SS4 vs the actual
    eval_map_isp.py code at that time)."""
    with manifest.open() as f:
        return {row["stem"]: row["adaptive_verdict_lowlight"] == "True" for row in csv.DictReader(f)}


def render_arm(bayer, w, h, arm, blc_offset, stem=None, adaptive_verdicts=None):
    """Synthesize the uint8 RGB image for a given arm + swept BLC offset,
    using the new independent normal/lowlight/checker modules."""
    if arm == "normal":
        return PB.run_arm(bayer, w, h, "normal", blc_offset=blc_offset)
    if arm == "lowlight":
        return PL.run_arm(bayer, w, h, "lowlight", blc_offset=blc_offset)
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
            return PL.run_arm(bayer, w, h, "lowlight", blc_offset=blc_offset)
        return PB.run_arm(bayer, w, h, "normal", blc_offset=blc_offset)
    raise ValueError(f"unsupported arm for BLC ablation: {arm}")


def build_arm_images(root: Path, work: Path, arms, limit: int, blc_offset: int,
                      adaptive_verdicts=None) -> int:
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists())
    if limit:
        stems = stems[:limit]
    for a in arms:
        (work / a / "images").mkdir(parents=True, exist_ok=True)
        (work / a / "labels").mkdir(parents=True, exist_ok=True)
    built = 0
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            continue
        bayer = bayer.reshape(h, w)
        for a in arms:
            out = render_arm(bayer, w, h, a, blc_offset, stem=stem, adaptive_verdicts=adaptive_verdicts)
            Image.fromarray(out).save(work / a / "images" / f"{stem}.jpg", quality=95)
            shutil.copy(lab_dir / f"{stem}.txt", work / a / "labels" / f"{stem}.txt")
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="../../../sonynod_test")
    ap.add_argument("--blc-offsets", default="0,1,2,4,8,16", help="comma-separated BLC_OFFSET sweep values")
    ap.add_argument("--work", default="data/_isp_work")
    ap.add_argument("--tag", default="SonyNOD-ISPFix")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="results/map_isp_sonynod_blcfix_yolov8n.csv")
    ap.add_argument("--manifest", type=Path, default=None,
                     help="build_matched_splits.py manifest CSV (lod/pascal/shuffle_split_*.csv) "
                          "supplying precomputed adaptive-tau verdicts per stem for the "
                          "'adaptive' arm. Required for LOD/PASCAL/Shuffle split runs -- without "
                          "it, 'adaptive' silently falls back to the deployed C0 checker "
                          "(checker.selected_mode), which is NOT the adopted adaptive-tau scheme.")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    blc_offsets = [int(v.strip()) for v in args.blc_offsets.split(",") if v.strip() != ""]
    root = Path(args.root)
    adaptive_verdicts = load_adaptive_verdicts(args.manifest) if args.manifest else None

    from ultralytics import YOLO
    import yaml  # type: ignore
    model_path = resolve_yolo_model(args.model)
    model = YOLO(model_path)

    rows = []
    n = None
    for blc in blc_offsets:
        work = Path(args.work) / f"{args.tag.lower()}_blc{blc}"
        n = build_arm_images(root, work, arms, args.limit, blc, adaptive_verdicts=adaptive_verdicts)
        print(f"[{args.tag}] blc_offset={blc}: built arm images for {n} frames: {arms}")
        for a in arms:
            ds = work / a
            yml = ds / "data.yaml"
            yml.write_text(yaml.safe_dump({
                "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
                "names": [str(i) for i in range(80)],
            }))
            m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False, plots=False)
            map5095, map50 = float(m.box.map), float(m.box.map50)
            print(f"[{args.tag}] blc_offset={blc:2d} {a:9s} mAP@[.5:.95]={map5095:.4f}  mAP@50={map50:.4f}")
            rows.append((args.tag, blc, a, map5095, map50, model_path, n))

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["dataset", "blc_offset", "arm", "mAP_50_95", "mAP_50", "model", "n"])
        for tag, blc, a, m5095, m50, model_path, n in rows:
            wr.writerow([tag, blc, a, f"{m5095:.4f}", f"{m50:.4f}", model_path, n])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
