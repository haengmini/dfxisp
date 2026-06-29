#!/usr/bin/env python3
"""E2 (real) — pseudo-RAW COCO mAP for the 4 RM variants using ultralytics.

Dataset: DFXISP/dataset/COCO_5000_raw  (RGGB Bayer, 16-bit/shift8, headerless
.bin of H*W uint16; dims taken from the matching processed jpg). YOLO-format
labels. Pipeline per variant:

  raw .bin (RGGB16) -> demosaic -> variant ISP (numpy, vectorized) -> RGB ->
  yolov8n -> mAP vs YOLO labels (ultralytics val).

The variant semantics mirror tools/rm_model.py (reg gain / 2x2 binning /
FP base-detail add-back); demosaic is RGGB here (dataset) vs GRBG in the C-sim
golden — relative variant behaviour is what E2 compares.

Usage:
  python3 tools/eval_map_coco.py --root <coco_val_dir> --limit 150 --out results/map_real.csv
  (coco_val_dir contains raw_bin/, labels/, images/)
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np

VARIANTS = [("static", 0), ("reg_only", 1), ("dfx_bin", 2), ("dfx_fp", 3)]

# ExDark (12 classes, alphabetical) -> COCO80 id, so a COCO-pretrained detector
# can be scored against ExDark ground truth.
EXDARK_TO_COCO = {0: 1, 1: 8, 2: 39, 3: 5, 4: 2, 5: 15, 6: 56, 7: 41, 8: 16, 9: 3, 10: 0, 11: 60}

# Parameters mirror rm_model.py
GAIN_NUM, GAIN_DEN, LIFT = 3, 2, 8
KNEE, KNEE_LIFT = 128, 40
FP_NOISE_T = 2
SHIFT = 8  # 16-bit -> 8-bit (meta.json scale=shift8)


def jpg_dims(p: Path):
    import struct
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


def demosaic_rggb(bayer16, w, h):
    """Bilinear-ish RGGB demosaic -> uint8 RGB (H,W,3). bayer16: (H,W) uint16."""
    b = (bayer16 >> SHIFT).astype(np.int32)  # to 8-bit domain
    R = np.zeros((h, w), np.int32); G = np.zeros((h, w), np.int32); B = np.zeros((h, w), np.int32)
    # RGGB: (0,0)=R (0,1)=G (1,0)=G (1,1)=B
    def avg(*a): return sum(a) // len(a)
    yy, xx = np.mgrid[0:h, 0:w]
    def shift(arr, dy, dx):
        return np.roll(np.roll(arr, -dy, axis=0), -dx, axis=1)
    # nearest-neighbor fill per Bayer position (simple, fast, adequate for mAP proxy)
    even_y = (yy % 2 == 0); even_x = (xx % 2 == 0)
    # R at even,even
    R[even_y & even_x] = b[even_y & even_x]
    R[even_y & ~even_x] = shift(b, 0, -1)[even_y & ~even_x]
    R[~even_y & even_x] = shift(b, -1, 0)[~even_y & even_x]
    R[~even_y & ~even_x] = shift(b, -1, -1)[~even_y & ~even_x]
    # B at odd,odd
    B[~even_y & ~even_x] = b[~even_y & ~even_x]
    B[~even_y & even_x] = shift(b, 0, 1)[~even_y & even_x]
    B[even_y & ~even_x] = shift(b, 1, 0)[even_y & ~even_x]
    B[even_y & even_x] = shift(b, 1, 1)[even_y & even_x]
    # G at even,odd and odd,even ; interpolate elsewhere
    G[(even_y & ~even_x) | (~even_y & even_x)] = b[(even_y & ~even_x) | (~even_y & even_x)]
    gmiss = (even_y & even_x) | (~even_y & ~even_x)
    G[gmiss] = avg(shift(b, 0, 1), shift(b, 0, -1), shift(b, 1, 0), shift(b, -1, 0))[gmiss]
    return np.clip(np.stack([R, G, B], -1), 0, 255).astype(np.uint8)


def box3(ch):  # 3x3 mean (replicate border), integer floor
    p = np.pad(ch.astype(np.int32), 1, mode="edge")
    s = sum(p[1 + dy:1 + dy + ch.shape[0], 1 + dx:1 + dx + ch.shape[1]]
            for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    return s // 9


def soft_knee(base):
    out = base.copy()
    m = base < KNEE
    out[m] = base[m] + (KNEE_LIFT * (KNEE - base[m])) // KNEE
    return np.clip(out, 0, 255)


def reg_gain(x):
    return np.clip((x * GAIN_NUM) // GAIN_DEN + LIFT, 0, 255)


def apply_variant(rgb, variant):
    rgb = rgb.astype(np.int32)
    if variant == 0:
        return rgb.astype(np.uint8)
    if variant == 1:
        return reg_gain(rgb).astype(np.uint8)
    if variant == 2:  # 2x2 binning (denoise) + gain, upsample back to full res
        import os
        mode = os.environ.get("DFXBIN_UPSAMPLE", "bilinear")  # nearest|bilinear
        h, w, _ = rgb.shape
        h2, w2 = h - h % 2, w - w % 2
        out = reg_gain(rgb.copy())  # border (odd last row/col) falls back to reg gain
        blk = rgb[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2, 3)
        binned = reg_gain(blk.sum(axis=(1, 3)) // 4).astype(np.uint8)  # (h2/2,w2/2,3)
        if mode == "nearest":
            up = np.repeat(np.repeat(binned, 2, axis=0), 2, axis=1)
        else:
            from PIL import Image
            up = np.asarray(Image.fromarray(binned).resize((w2, h2), Image.BILINEAR))
        out[:h2, :w2] = up
        return np.clip(out, 0, 255).astype(np.uint8)
    if variant == 3:  # FP base/detail add-back, green-guided
        ch = [rgb[..., c] for c in range(3)]
        base = [box3(c) for c in ch]
        detail = [ch[c] - base[c] for c in range(3)]
        gd = np.abs(detail[1])
        num = np.where(gd <= FP_NOISE_T, 1, 3)
        den = np.where(gd <= FP_NOISE_T, 1, 2)
        out = []
        for c in range(3):
            add = np.floor_divide(num * detail[c], den)
            out.append(np.clip(soft_knee(base[c]) + add, 0, 255))
        return np.stack(out, -1).astype(np.uint8)
    raise ValueError(variant)


def _write_label(src: Path, dst: Path, remap):
    if remap is None:
        shutil.copy(src, dst); return
    lines = []
    for ln in src.read_text().splitlines():
        p = ln.split()
        if not p:
            continue
        c = int(p[0])
        if c not in remap:
            continue
        lines.append(" ".join([str(remap[c])] + p[1:]))
    dst.write_text("\n".join(lines) + ("\n" if lines else ""))


def build_variant_images(root: Path, work: Path, limit: int, remap=None):
    from PIL import Image
    raw_dir = root / "raw_bin"; lab_dir = root / "labels"; img_dir = root / "images"
    stems = sorted(p.stem for p in raw_dir.glob("*.bin")
                   if (img_dir / f"{p.stem}.jpg").exists() and (lab_dir / f"{p.stem}.txt").exists())
    if limit:
        stems = stems[:limit]
    for name, vid in VARIANTS:
        (work / name / "images").mkdir(parents=True, exist_ok=True)
        (work / name / "labels").mkdir(parents=True, exist_ok=True)
    built = 0
    for stem in stems:
        w, h = jpg_dims(img_dir / f"{stem}.jpg")
        bayer = np.fromfile(raw_dir / f"{stem}.bin", dtype="<u2")
        if bayer.size != w * h:
            continue
        bayer = bayer.reshape(h, w)
        rgb = demosaic_rggb(bayer, w, h)
        for name, vid in VARIANTS:
            out = apply_variant(rgb, vid)
            Image.fromarray(out).save(work / name / "images" / f"{stem}.jpg", quality=95)
            lab = lab_dir / f"{stem}.txt"
            if lab.exists():
                _write_label(lab, work / name / "labels" / f"{stem}.txt", remap)
        built += 1
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="dir with raw_bin/ labels/ images/")
    ap.add_argument("--work", default="data/_variant_work")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--out", default="results/map_real.csv")
    ap.add_argument("--tag", default="COCO")
    ap.add_argument("--remap", choices=["none", "exdark"], default="none",
                    help="remap GT class ids (exdark: 12-class -> COCO80)")
    args = ap.parse_args()

    remap = EXDARK_TO_COCO if args.remap == "exdark" else None
    root = Path(args.root); work = Path(args.work)
    n = build_variant_images(root, work, args.limit, remap)
    print(f"built variant images for {n} frames")

    from ultralytics import YOLO
    import yaml  # type: ignore
    model = YOLO(args.model)
    res = {}
    for name, _ in VARIANTS:
        ds = work / name
        yml = ds / "data.yaml"
        yml.write_text(yaml.safe_dump({
            "path": str(ds.resolve()), "train": "images", "val": "images", "nc": 80,
            "names": [str(i) for i in range(80)],
        }))
        m = model.val(data=str(yml), imgsz=640, verbose=False, save_json=False)
        res[name] = float(m.box.map)   # mAP@[.5:.95]
        print(f"{name}: mAP={res[name]:.4f}")

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["metric", "static", "reg_only", "dfx_bin", "dfx_fp", "unit", "notes"])
        wr.writerow([f"mAP_{args.tag}_pseudoRAW"] + [f"{res[nm]:.4f}" for nm, _ in VARIANTS]
                    + ["mAP@[.5:.95]", f"model={args.model} n={n}"])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
