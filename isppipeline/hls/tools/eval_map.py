#!/usr/bin/env python3
"""E2 — pseudo-RAW object-detection mAP harness for the 4 RM variants.

Pipeline (per variant):
  pseudo-RAW Bayer  --rm_model.variant_frame-->  RGB888  -->  detector  -->  COCO mAP

This is the board-independent software experiment. It is READY TO RUN but
requires dependencies/data not present in the scaffold environment:
  pip install numpy pillow torch torchvision ultralytics pycocotools
  data: DFXISP/dataset/COCO_5000_raw (pseudo-RAW) + COCO-style annotations json

Outputs measurements-style rows (Tab6): mAP per variant for COCO/ExDark.

Design notes:
  - ISP is applied via tools/rm_model (bit-exact to src/dfxisp_rm.cpp), so SW mAP
    and HW C-sim share the exact same pixel transform.
  - Bayer packing: expects each sample as a 12-bit GRBG plane (HxW) in .npy or a
    raw loader you provide (see load_bayer). If your dataset stores sRGB, supply
    an unprocessing step to pseudo-RAW first (see refs: beyond-rgb, simrod).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import rm_model as M

VARIANTS = [M.VAR_STATIC, M.VAR_REG, M.VAR_BIN, M.VAR_FP]


def _require(mod):
    try:
        return __import__(mod)
    except Exception:
        print(f"[eval_map] missing dependency '{mod}'. Install: "
              "pip install numpy pillow torch torchvision ultralytics pycocotools",
              file=sys.stderr)
        raise SystemExit(3)


def load_bayer(path: Path):
    """Load one pseudo-RAW Bayer frame as a flat list of 12-bit ints + (w,h).
    Replace/extend for your dataset's actual storage (npy/raw/tiff)."""
    np = _require("numpy")
    if path.suffix == ".npy":
        a = np.load(path)
    else:
        raise SystemExit(f"[eval_map] unsupported raw format: {path.suffix}; add a loader.")
    a = a.astype("int64")
    h, w = a.shape[:2]
    return a.flatten().tolist(), w, h


def isp_to_rgb(raw, w, h, variant):
    """Apply variant ISP (bit-exact to C-sim) -> HxWx3 uint8 numpy array."""
    np = _require("numpy")
    out = M.variant_frame(raw, w, h, variant)
    a = np.array(out, dtype=np.int64)
    rgb = np.stack([(a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF], axis=-1)
    return rgb.reshape(h, w, 3).astype("uint8")


def run(dataset_dir: Path, ann_json: Path, model_name: str, limit: int):
    np = _require("numpy")
    Image = _require("PIL").Image  # noqa
    from ultralytics import YOLO  # type: ignore
    from pycocotools.coco import COCO  # type: ignore
    from pycocotools.cocoeval import COCOeval  # type: ignore

    coco = COCO(str(ann_json))
    img_ids = coco.getImgIds()[:limit] if limit else coco.getImgIds()
    model = YOLO(model_name)

    results = {}
    for variant in VARIANTS:
        dets = []
        for img_id in img_ids:
            info = coco.loadImgs(img_id)[0]
            raw_path = dataset_dir / (Path(info["file_name"]).stem + ".npy")
            if not raw_path.exists():
                continue
            raw, w, h = load_bayer(raw_path)
            rgb = isp_to_rgb(raw, w, h, variant)
            pred = model.predict(rgb, verbose=False)[0]
            for b in pred.boxes:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                dets.append({
                    "image_id": img_id,
                    "category_id": int(b.cls[0]) + 1,  # map to COCO cat ids as needed
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "score": float(b.conf[0]),
                })
        if not dets:
            results[variant] = float("nan")
            continue
        dt = coco.loadRes(dets)
        ev = COCOeval(coco, dt, "bbox")
        ev.params.imgIds = img_ids
        ev.evaluate(); ev.accumulate(); ev.summarize()
        results[variant] = float(ev.stats[0])  # mAP@[.5:.95]
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True, help="dir of pseudo-RAW .npy frames")
    ap.add_argument("--ann", required=True, help="COCO-style annotations json")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--limit", type=int, default=0, help="0 = all images")
    ap.add_argument("--tag", default="COCO", help="dataset tag for the output row")
    ap.add_argument("--out", default="results/map.csv")
    args = ap.parse_args()

    res = run(Path(args.dataset), Path(args.ann), args.model, args.limit)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out.exists()
    with out.open("a", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        if write_header:
            wr.writerow(["metric", "static", "reg_only", "dfx_bin", "dfx_fp", "unit", "notes"])
        wr.writerow([f"mAP_{args.tag}_pseudoRAW"] + [f"{res[v]:.4f}" for v in VARIANTS]
                    + ["mAP@[.5:.95]", f"model={args.model}"])
    print(f"wrote {out}: " + ", ".join(f"{M.VARIANT_NAMES[v]}={res[v]:.4f}" for v in VARIANTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
