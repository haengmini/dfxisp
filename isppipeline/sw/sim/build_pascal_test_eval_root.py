#!/usr/bin/env python3
"""Build an eval_map_isp.py-compatible {images/,labels/,raw_bin/} root from
dataset/PASCAL_test/{raw/,images/,labels/} -- the PASCAL-side mirror of
build_lod_test_eval_root.py (checker.md Sec.3.2/Sec.5).

Why this exists (2026-08-13 checker simulation): checker_sim.py's dark16/
dark50 discriminability experiment (checker.md Sec.3.2-3.6) needs both
LOD_test and PASCAL_test as shift8-normalised raw16 arrays in the same
convention build_lod_test_eval_root.py already uses for LOD, so the two
sets are directly comparable. No such PASCAL-side script existed before this.

Nikon NEF differs from the Sony ARW case in two ways (checked via rawpy on
15/100 samples, all identical): raw_image_visible is already the correct
6034x4012 crop with no extra margin to slice (top_margin=left_margin=0,
unlike ARW's CROP_TOP/LEFT=12), and the sensor is natively 12-bit with
black_level_per_channel=(0,0,0,0)/white_level=4095 (vs ARW's 14-bit
800/16380) -- so the shift8 normalisation collapses to a plain /4095 scale,
no pedestal subtraction needed.

**Output location**: the default --out is intentionally OUTSIDE dataset/
(isppipeline/sw/sim/checker/_cache/PASCAL_test_eval, gitignored) -- per
current project policy, dataset/ holds only LOD_test/PASCAL_test raw
originals; derived sets are not written there. This mirrors what
build_lod_test_eval_root.py is invoked with for this same simulation
(see checker_sim.py's defaults), even though that script's own --out
default still points at dataset/LOD_test_eval for its original (gamma)
call site.

dataset/PASCAL_test/{raw,images,labels}/ are left untouched.

Usage:
  python3 isppipeline/sw/sim/build_pascal_test_eval_root.py \
      --src dataset/PASCAL_test \
      --out isppipeline/sw/sim/checker/_cache/PASCAL_test_eval
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image

BLACK_LEVEL = 0
WHITE_LEVEL = 4095


def nef_to_raw_bin(nef_path: Path) -> np.ndarray:
    with rawpy.imread(str(nef_path)) as raw:
        bayer = raw.raw_image_visible.astype(np.float64)
    lin = np.clip((bayer - BLACK_LEVEL) / (WHITE_LEVEL - BLACK_LEVEL), 0.0, 1.0)
    u8 = np.round(lin * 255).astype(np.uint16)
    return (u8 << 8).astype("<u2")


def nef_to_preview_jpg(nef_path: Path) -> Image.Image:
    with rawpy.imread(str(nef_path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=False,
                              no_auto_bright=False, output_bps=8)
    return Image.fromarray(rgb)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default="dataset/PASCAL_test")
    ap.add_argument("--out", default="isppipeline/sw/sim/checker/_cache/PASCAL_test_eval")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    (out / "raw_bin").mkdir(parents=True, exist_ok=True)

    stems = sorted(p.stem for p in (src / "raw").glob("*.nef"))
    if args.limit:
        stems = stems[: args.limit]

    n_ok = 0
    errors = []
    expect_shape = None
    for stem in stems:
        nef_path = src / "raw" / f"{stem}.nef"
        lab_path = src / "labels" / f"{stem}.txt"
        if not lab_path.exists():
            errors.append(f"missing label: {stem}")
            continue
        try:
            raw_bin = nef_to_raw_bin(nef_path)
            preview = nef_to_preview_jpg(nef_path)
        except Exception as e:  # noqa: BLE001
            errors.append(f"decode failed {stem}: {e}")
            continue
        if expect_shape is None:
            expect_shape = raw_bin.shape
        elif raw_bin.shape != expect_shape:
            # PASCALRAW mixes landscape/portrait NEFs -- flag rather than
            # silently reshaping (checker's dark_ratio is shape-agnostic per
            # frame, but a divergent shape here would signal an unexpected
            # sensor/crop variant worth a manual look, not blind acceptance).
            errors.append(f"shape mismatch {stem}: {raw_bin.shape} vs {expect_shape}")
        raw_bin.tofile(out / "raw_bin" / f"{stem}.bin")
        preview.save(out / "images" / f"{stem}.jpg", quality=95)
        shutil.copy(lab_path, out / "labels" / f"{stem}.txt")
        n_ok += 1
        if n_ok % 10 == 0:
            print(f"  converted {n_ok}/{len(stems)}")

    (out / "convert_errors.log").write_text("\n".join(errors) + ("\n" if errors else ""))
    print(f"converted={n_ok} errors={len(errors)} total={len(stems)}")
    print(f"raw_bin shape: {expect_shape} (shift8, black={BLACK_LEVEL} white={WHITE_LEVEL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
