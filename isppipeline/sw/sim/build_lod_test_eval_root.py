#!/usr/bin/env python3
"""Build an eval_map_isp.py-compatible {images/,labels/,raw_bin/} root from
dataset/LOD_test/{raw/,images/,labels/}.

Why this exists (2026-08-12 LOD_test migration): dataset/LOD_test/images/*.jpg
are pre-existing 1280x855 preview thumbnails (uniform across all 100 frames --
verified, not a per-image auto-crop). eval_map_isp.py's build_arm_images()
reshapes each raw_bin/*.bin to the (w, h) it reads from the matching jpg's SOF
header (jpg_dims()), so raw_bin MUST be pixel-identical in size to the jpg it
is paired with. But the raw Bayer mosaic (native crop 5472x3648, confirmed via
rawpy on 5/100 samples: raw_pattern RGGB, black_level 800, white_level 16380,
crop_top/left=12, crop_width/height=5472/3648 -- exactly build_sonynod_dataset.py's
hardcoded Sony RX100 VII constants) cannot be resampled to 1280x855 without
breaking the 2x2 CFA phase (5472/1280 = 4.275, not an integer, let alone a
multiple of 2) -- any such resize would silently corrupt every downstream
binning/demosaic stage.

Decision: render raw_bin at the FULL native crop resolution (matching
build_sonynod_dataset.py's arw_to_raw_bin() exactly, same constants, same
"shift8" convention: value = round(clip((bayer-BLACK)/(WHITE-BLACK),0,1)*255) << 8),
and regenerate a MATCHING-resolution preview jpg (also mirroring
build_sonynod_dataset.py's arw_to_preview_jpg()) so jpg_dims() agrees with
raw_bin's actual array shape. Labels are copied verbatim from
dataset/LOD_test/labels/ (YOLO-normalized, dimension-independent to first
order) -- NOT recomputed, because they are unchanged 0..1 fractions and the
aspect-ratio delta between the original 1280x855 preview (1.4971) and the
raw crop (5472/3648 = 1.5 exactly) is ~0.2%, well under any IoU-threshold
sensitivity. This is documented as a known minor caveat, not silently fixed.

dataset/LOD_test/{raw,images,labels}/ are left untouched -- this script only
writes a new sibling directory, dataset/LOD_test_eval/, analogous to how
build_sonynod_dataset.py writes a separate --out root rather than mutating its
source tree.

Usage:
  python3 isppipeline/sw/sim/build_lod_test_eval_root.py \
      --src dataset/LOD_test --out dataset/LOD_test_eval
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image

CROP_TOP, CROP_LEFT = 12, 12
CROP_W, CROP_H = 5472, 3648
BLACK_LEVEL = 800
WHITE_LEVEL = 16380

# Sensor profiles (2026-08-13 addition). "sony_lod" repeats the module-level
# constants above verbatim, so the default path is byte-identical to what this
# script produced before the profiles existed; "nikon_pascal" is the new entry
# needed to build the same eval root for dataset/PASCAL_test (Nikon D3200 .NEF,
# 12-bit, black 0 / white 4095, no crop margins -- confirmed via rawpy on the
# 100 local frames). Pure addition, same posture as eval_map_isp.py's
# --wb-lowlight (see lowlight-wb-mode-split-2026-08-03.md 6).
SENSORS = {
    "sony_lod":     {"ext": ".ARW", "crop": (CROP_TOP, CROP_LEFT, CROP_W, CROP_H),
                     "black": BLACK_LEVEL, "white": WHITE_LEVEL},
    "nikon_pascal": {"ext": ".nef", "crop": (0, 0, 6034, 4012),
                     "black": 0, "white": 4095},
}


def arw_to_raw_bin(arw_path: Path, sensor: dict = SENSORS["sony_lod"]) -> np.ndarray:
    top, left, w, h = sensor["crop"]
    with rawpy.imread(str(arw_path)) as raw:
        bayer = raw.raw_image_visible.astype(np.float64)
        bayer = bayer[top:top + h, left:left + w]
    lin = np.clip((bayer - sensor["black"]) / (sensor["white"] - sensor["black"]), 0.0, 1.0)
    u8 = np.round(lin * 255).astype(np.uint16)
    return (u8 << 8).astype("<u2")


def arw_to_preview_jpg(arw_path: Path, sensor: dict = SENSORS["sony_lod"]) -> Image.Image:
    _, _, w, h = sensor["crop"]
    with rawpy.imread(str(arw_path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=False,
                              no_auto_bright=False, output_bps=8)
    img = Image.fromarray(rgb)
    if img.size != (w, h):
        img = img.resize((w, h), Image.BILINEAR)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default="dataset/LOD_test")
    ap.add_argument("--out", default="dataset/LOD_test_eval")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sensor", choices=sorted(SENSORS), default="sony_lod",
                    help="sensor profile (crop/black/white/extension). The default "
                         "reproduces this script's original hardcoded Sony constants.")
    args = ap.parse_args()

    sensor = SENSORS[args.sensor]
    src = Path(args.src)
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    (out / "raw_bin").mkdir(parents=True, exist_ok=True)

    stems = sorted(p.stem for p in (src / "raw").glob("*" + sensor["ext"]))
    if args.limit:
        stems = stems[: args.limit]

    n_ok = 0
    errors = []
    for stem in stems:
        arw_path = src / "raw" / f"{stem}{sensor['ext']}"
        lab_path = src / "labels" / f"{stem}.txt"
        if not lab_path.exists():
            errors.append(f"missing label: {stem}")
            continue
        try:
            raw_bin = arw_to_raw_bin(arw_path, sensor)
            preview = arw_to_preview_jpg(arw_path, sensor)
        except Exception as e:  # noqa: BLE001
            errors.append(f"decode failed {stem}: {e}")
            continue
        raw_bin.tofile(out / "raw_bin" / f"{stem}.bin")
        preview.save(out / "images" / f"{stem}.jpg", quality=95)
        shutil.copy(lab_path, out / "labels" / f"{stem}.txt")
        n_ok += 1
        if n_ok % 10 == 0:
            print(f"  converted {n_ok}/{len(stems)}")

    (out / "convert_errors.log").write_text("\n".join(errors) + ("\n" if errors else ""))
    print(f"converted={n_ok} errors={len(errors)} total={len(stems)}")
    print(f"note: labels copied verbatim from {src}/labels (unchanged 0..1 YOLO "
          f"fractions); images regenerated at native crop res "
          f"{sensor['crop'][2]}x{sensor['crop'][3]} "
          f"(source preview jpgs were 1280x855 -- see module docstring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
