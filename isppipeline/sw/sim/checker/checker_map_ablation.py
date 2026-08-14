#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/checker/checker_map_ablation.py
# Date   : 2026-08-13
# Function: Implements checker.md Sec.3.4 -- re-derives C_miss/C_FA (the
#           asymmetric mis-trigger costs Sec.3.5's Bayes-risk search needs)
#           by rendering LOD_test/PASCAL_test through BOTH arms (normal,
#           lowlight) and scoring each render with YOLOv8n, instead of
#           inheriting the original campaign's COCO/ExDark-derived values.
#           Kept out of checker_sim.py because this is the one step in the
#           checker plan that needs detector inference (checker.md Sec.5) --
#           400 renders+inferences at native resolution, much slower than
#           checker_sim.py's pure-numpy statistics.
# Sources: isppipeline/sw/sim/checker/checker.md Sec.3.4,
#          isppipeline/sw/default_isp_pipeline.py (normal arm, live, reused
#          unmodified), isppipeline/sw/lowlight_isp_pipeline.py (lowlight
#          arm, live, reused unmodified), ultralytics (YOLOv8n, installed).
# =============================================================================
"""checker_map_ablation: dual-arm mAP ablation on LOD_test/PASCAL_test to
re-derive C_miss/C_FA (checker.md Sec.3.4).

For each of the 4 (dataset, arm) combinations, every raw_bin frame in the
matching *_test_eval/ eval-root (built by build_lod_test_eval_root.py /
build_pascal_test_eval_root.py into checker_sim.py's _cache/, see checker.md
Sec.5) is rendered through that arm's pipeline function -- imported
unmodified from default_isp_pipeline.py / lowlight_isp_pipeline.py, no
reimplementation -- and the renders are scored against the dataset's own
YOLO-format labels with YOLOv8n via ultralytics' standard val() path (which
wraps its own COCO-style AP computation; not reimplemented here either).

    C_FA   = mAP(normal arm, PASCAL) - mAP(lowlight arm, PASCAL)
    C_miss = mAP(lowlight arm, LOD)  - mAP(normal arm, LOD)

Output: checker_map_ablation_results.csv (all 4 mAP figures) and
checker_costs_derived.csv (the one-line c_miss/c_fa file checker_sim.py's
Sec.3.5/3.6 read).

Usage:
    python3 checker_map_ablation.py [--limit N] [--imgsz 640]
                                     [--lod-eval-root PATH] [--pascal-eval-root PATH]
                                     [--out-dir PATH]
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # isppipeline/sw

import default_isp_pipeline as DP  # noqa: E402
import lowlight_isp_pipeline as LP  # noqa: E402

SIM_DIR = Path(__file__).resolve().parent
CACHE_DIR = SIM_DIR / "_cache"

# checker.md Sec.3.4/Sec.4: both eval-roots are a single, uniform native-crop
# resolution across all 100 frames (rawpy-confirmed during checker.md's
# authoring -- LOD on 100/100 by build_lod_test_eval_root.py's own decode,
# PASCAL on 15/100 spot samples, all identical).
FRAME_DIMS = {
    "LOD": (5472, 3648),      # (w, h)
    "PASCAL": (6034, 4012),
}

# arm name -> (module, dispatch) exactly as SPEC'd (checker.md Sec.3.4):
# normal = default_isp_pipeline.run_arm("default_isp"),
# lowlight = lowlight_isp_pipeline.run_arm("lowlight_isp") (deployed
# BIN_BINNING+TONE_GAMMA combination).
ARMS = {
    "normal": ("default_isp", lambda raw16, w, h: DP.run_arm(raw16, w, h, "default_isp")),
    "lowlight": ("lowlight_isp", lambda raw16, w, h: LP.run_arm(raw16, w, h, "lowlight_isp")),
}


def load_raw16(bin_path: Path, w: int, h: int) -> np.ndarray:
    arr = np.fromfile(bin_path, dtype="<u2")
    if arr.size != w * h:
        raise ValueError(f"{bin_path}: size {arr.size} != {w}x{h}={w*h}")
    return arr


def render_arm(eval_root: Path, dims: tuple[int, int], arm_fn, out_dir: Path,
                limit: int = 0) -> int:
    w, h = dims
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)
    bins = sorted((eval_root / "raw_bin").glob("*.bin"))
    if limit:
        bins = bins[:limit]

    n = 0
    for p in bins:
        raw16 = load_raw16(p, w, h)
        rgb = arm_fn(raw16, w, h)
        Image.fromarray(rgb).save(out_dir / "images" / f"{p.stem}.png")
        lab = eval_root / "labels" / f"{p.stem}.txt"
        (out_dir / "labels" / f"{p.stem}.txt").write_text(lab.read_text())
        n += 1
        if n % 10 == 0:
            print(f"    rendered {n}/{len(bins)}")
    return n


def write_dataset_yaml(render_dir: Path, names: dict[int, str]) -> Path:
    yaml_path = render_dir / "data.yaml"
    lines = [f"path: {render_dir.resolve()}", "train: images", "val: images", "names:"]
    for idx in sorted(names):
        lines.append(f"  {idx}: {names[idx]}")
    yaml_path.write_text("\n".join(lines) + "\n")
    return yaml_path


def run_val(model, yaml_path: Path, imgsz: int) -> tuple[float, float]:
    metrics = model.val(data=str(yaml_path), imgsz=imgsz, device="cpu",
                        plots=False, verbose=False, split="val")
    return float(metrics.box.map), float(metrics.box.map50)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="frames per dataset (0 = all)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--lod-eval-root", type=Path, default=CACHE_DIR / "LOD_test_eval")
    ap.add_argument("--pascal-eval-root", type=Path, default=CACHE_DIR / "PASCAL_test_eval")
    ap.add_argument("--out-dir", type=Path, default=SIM_DIR)
    ap.add_argument("--render-dir", type=Path, default=CACHE_DIR / "map_render")
    args = ap.parse_args()

    from ultralytics import YOLO  # deferred: slow import, only needed here

    eval_roots = {"LOD": args.lod_eval_root, "PASCAL": args.pascal_eval_root}
    for name, root in eval_roots.items():
        if not (root / "raw_bin").exists():
            print(f"[checker_map_ablation] FATAL: {name} eval-root not found "
                  f"at {root} -- run build_{name.lower()}_test_eval_root.py first.")
            return 1

    t0 = time.time()
    print("Loading YOLOv8n...")
    model = YOLO("yolov8n.pt")
    names = model.names

    results: dict[tuple[str, str], tuple[float, float]] = {}
    for dataset, eval_root in eval_roots.items():
        for arm_key, (arm_name, arm_fn) in ARMS.items():
            render_dir = args.render_dir / f"{dataset}_{arm_key}"
            print(f"\n=== Rendering {dataset} / {arm_key} ({arm_name}) -> {render_dir} ===")
            n = render_arm(eval_root, FRAME_DIMS[dataset], arm_fn, render_dir, args.limit)
            yaml_path = write_dataset_yaml(render_dir, names)
            print(f"  {n} frames rendered, running YOLOv8n val (imgsz={args.imgsz})...")
            map_5095, map_50 = run_val(model, yaml_path, args.imgsz)
            results[(dataset, arm_key)] = (map_5095, map_50)
            print(f"  {dataset}/{arm_key}: mAP@[.5:.95]={map_5095:.4f}  mAP@50={map_50:.4f}")

    map_normal_pascal, _ = results[("PASCAL", "normal")]
    map_lowlight_pascal, _ = results[("PASCAL", "lowlight")]
    map_lowlight_lod, _ = results[("LOD", "lowlight")]
    map_normal_lod, _ = results[("LOD", "normal")]

    c_fa = map_normal_pascal - map_lowlight_pascal
    c_miss = map_lowlight_lod - map_normal_lod

    print(f"\n=== checker.md Sec.3.4 result ===")
    print(f"C_FA   = mAP(normal,PASCAL) - mAP(lowlight,PASCAL) "
          f"= {map_normal_pascal:.4f} - {map_lowlight_pascal:.4f} = {c_fa:.4f}")
    print(f"C_miss = mAP(lowlight,LOD) - mAP(normal,LOD) "
          f"= {map_lowlight_lod:.4f} - {map_normal_lod:.4f} = {c_miss:.4f}")
    if c_fa != 0:
        print(f"ratio C_miss/C_FA = {c_miss / c_fa:.2f}:1 "
              f"(original campaign reference: 2.89:1)")

    rows = []
    for (dataset, arm_key), (m5095, m50) in results.items():
        rows.append({"dataset": dataset, "arm": arm_key, "map_50_95": m5095, "map_50": m50,
                     "n": args.limit or 100})
    with (args.out_dir / "checker_map_ablation_results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["dataset", "arm", "map_50_95", "map_50", "n"])
        w.writeheader()
        w.writerows(rows)

    with (args.out_dir / "checker_costs_derived.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["c_miss", "c_fa", "ratio",
                                          "map_normal_pascal", "map_lowlight_pascal",
                                          "map_lowlight_lod", "map_normal_lod"])
        w.writeheader()
        w.writerow({"c_miss": c_miss, "c_fa": c_fa,
                    "ratio": (c_miss / c_fa) if c_fa else float("nan"),
                    "map_normal_pascal": map_normal_pascal,
                    "map_lowlight_pascal": map_lowlight_pascal,
                    "map_lowlight_lod": map_lowlight_lod,
                    "map_normal_lod": map_normal_lod})

    print(f"\nElapsed: {time.time() - t0:.0f}s")
    print(f"Wrote {args.out_dir / 'checker_map_ablation_results.csv'}")
    print(f"Wrote {args.out_dir / 'checker_costs_derived.csv'} "
          f"(checker_sim.py's Sec.3.5/3.6 will pick this up automatically)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
