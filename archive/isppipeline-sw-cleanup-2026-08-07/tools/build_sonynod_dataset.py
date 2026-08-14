#!/usr/bin/env python3
"""Convert Sony RAW-NOD test-split .ARW + COCO annotations into the
dfxisp SW-eval dataset layout (images/ + labels/ + raw_bin/), matching
the format tools/eval_map_newrm.py expects (see isppipeline/hls/SPEC.md §2).

Real-sensor conversion spec (measured via rawpy on sample ARW files,
2026-07-06):
  - Sony RX100 VII, RGGB Bayer (raw_pattern [[R,G],[G,B]], color_desc RGBG)
  - active-area crop: top=12, left=12, width=5472, height=3648 (even offset
    -> RGGB phase preserved). Matches GT bbox coordinate space exactly.
  - black_level=800, white_level=16380 (14-bit ADC, uniform across channels
    on this body/lens combination -- confirmed on 2 samples).
  - Re-quantized into the SAME "shift8" uint16 convention the existing
    pseudo-RAW datasets use (value = round(linear*255) << 8), so the
    unmodified baseline core / newrm_pipeline.py (`bayer16 >> SHIFT`) can
    consume this real-RAW dataset as a drop-in arm.

Labels: RAW-NOD COCO category_id {1:person, 2:bicycle, 3:car} -> COCO-80
0-indexed ids {0,1,2}, matching eval_map_newrm.py's "already COCO-80 ids,
no remap" assumption.

Usage:
  python3 tools/build_sonynod_dataset.py \\
      raw_str_labeled_new_Sony_RX100m7_test.json \\
      <dir containing the referenced .ARW files> \\
      ../../data/sonynod_test
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image

CROP_TOP, CROP_LEFT = 12, 12
CROP_W, CROP_H = 5472, 3648
BLACK_LEVEL = 800
WHITE_LEVEL = 16380
CAT_REMAP = {1: 0, 2: 1, 3: 2}  # person, bicycle, car -> COCO-80 0-indexed


def arw_to_raw_bin_and_meta(arw_path: Path) -> tuple[np.ndarray, dict]:
    with rawpy.imread(str(arw_path)) as raw:
        bayer = raw.raw_image_visible.astype(np.float64)
        bayer = bayer[CROP_TOP:CROP_TOP + CROP_H, CROP_LEFT:CROP_LEFT + CROP_W]
        iso = float(getattr(raw.other, 'iso_speed', 0.0)) or None
        exposure_s = float(getattr(raw.other, 'shutter_speed', 0.0)) or None
        f_number = float(getattr(raw.other, 'aperture', 0.0)) or None

    lin = np.clip((bayer - BLACK_LEVEL) / (WHITE_LEVEL - BLACK_LEVEL), 0.0, 1.0)
    u8 = np.round(lin * 255).astype(np.uint16)
    raw_bin = (u8 << 8).astype("<u2")
    dark16 = float(((raw_bin >> 8) < 16).mean())

    meta = {
        "iso": iso,
        "exposure_s": exposure_s,
        "f_number": f_number,
        "dark16": round(dark16, 5),
    }
    return raw_bin, meta


def arw_to_preview_jpg(arw_path: Path) -> Image.Image:
    with rawpy.imread(str(arw_path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=False, no_auto_bright=False,
                               output_bps=8)
    img = Image.fromarray(rgb)
    if img.size != (CROP_W, CROP_H):  # rawpy postprocess already matches the active-area crop
        img = img.resize((CROP_W, CROP_H), Image.BILINEAR)
    return img


def coco_to_yolo_labels(annos_by_image: dict, image_id: int | str, w: int, h: int) -> list[str]:
    lines = []
    for a in annos_by_image.get(image_id, []):
        cls = CAT_REMAP.get(a["category_id"])
        if cls is None:
            continue
        x, y, bw, bh = a["bbox"]
        cx = (x + bw / 2) / w
        cy = (y + bh / 2) / h
        nw = bw / w
        nh = bh / h
        cx, cy, nw, nh = (max(0.0, min(1.0, v)) for v in (cx, cy, nw, nh))
        if nw <= 0 or nh <= 0:
            continue
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
    return lines


def main():
    ann_json = Path(sys.argv[1])
    arw_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])

    coco = json.loads(ann_json.read_text())
    images = {im["id"]: im for im in coco["images"]}
    annos_by_image: dict[int | str, list] = {}
    for a in coco["annotations"]:
        annos_by_image.setdefault(a["image_id"], []).append(a)

    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)
    (out_dir / "raw_bin").mkdir(parents=True, exist_ok=True)

    n_ok, n_skip, n_noanno = 0, 0, 0
    errors = []
    meta_rows = []

    for img_id, im in sorted(images.items(), key=lambda x: str(x[0])):
        stem = Path(im["file_name"]).stem
        arw_path = arw_dir / im["file_name"]
        if not arw_path.exists():
            n_skip += 1
            errors.append(f"missing ARW: {im['file_name']}")
            continue
        w, h = im["width"], im["height"]
        if (w, h) != (CROP_W, CROP_H):
            n_skip += 1
            errors.append(f"unexpected dims {w}x{h}: {im['file_name']}")
            continue

        lines = coco_to_yolo_labels(annos_by_image, img_id, w, h)
        if not lines:
            n_noanno += 1
            continue  # skip images with no in-scope GT boxes

        try:
            raw_bin, frame_meta = arw_to_raw_bin_and_meta(arw_path)
            preview = arw_to_preview_jpg(arw_path)
        except Exception as e:  # noqa: BLE001
            n_skip += 1
            errors.append(f"decode failed {im['file_name']}: {e}")
            continue

        raw_bin.tofile(out_dir / "raw_bin" / f"{stem}.bin")
        preview.save(out_dir / "images" / f"{stem}.jpg", quality=95)
        (out_dir / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")

        meta_rows.append({
            "stem": stem,
            "w": CROP_W,
            "h": CROP_H,
            "light": "night",
            "weather": "",
            "iso": frame_meta["iso"],
            "exposure_s": frame_meta["exposure_s"],
            "f_number": frame_meta["f_number"],
            "black_level": BLACK_LEVEL,
            "white_level": WHITE_LEVEL,
            "bayer": "RGGB",
            "dark16": frame_meta["dark16"],
            "illum_label": 1,
        })
        n_ok += 1

    (out_dir / "convert_errors.log").write_text("\n".join(errors) + ("\n" if errors else ""))

    if meta_rows:
        with (out_dir / "frames_meta.csv").open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(meta_rows[0].keys()))
            wr.writeheader()
            wr.writerows(meta_rows)

    meta = {
        "source": str(ann_json),
        "camera": "Sony RX100 VII",
        "bayer": "RGGB",
        "crop": {"top": CROP_TOP, "left": CROP_LEFT, "width": CROP_W, "height": CROP_H},
        "black_level": BLACK_LEVEL,
        "white_level": WHITE_LEVEL,
        "scale": "shift8 (round(linear*255)<<8) -- compatible with existing SHIFT=8 pipeline",
        "category_remap": CAT_REMAP,
        "n_images_total": len(images),
        "n_converted": n_ok,
        "n_skipped": n_skip,
        "n_no_gt": n_noanno,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"converted={n_ok} skipped={n_skip} no_gt={n_noanno} total={len(images)}")


if __name__ == "__main__":
    raise SystemExit(main())

