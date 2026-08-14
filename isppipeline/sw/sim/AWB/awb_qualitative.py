#!/usr/bin/env python3
# =============================================================================
# File   : isppipeline/sw/sim/AWB/awb_qualitative.py
# Date   : 2026-08-13
# Function: F6 -- render the same frames through the low-light arm at three WB
#           settings (off / deployed / gray-world), overlay YOLOv8n detections,
#           and assemble one montage. The point of the figure: the colour
#           changes obviously, the boxes do not.
# Renderer: the canonical low_light_isp_pipeline.run_lowlight(..., wb=) from
#           the hw-interface-prompt worktree, called in place (AWB_report.md 3's
#           "run it where it lives, don't copy" rule). Nothing is written to
#           dataset/ -- inputs come from an eval root built elsewhere.
# Usage:
#   python3 awb_qualitative.py --root <LOD_test_eval root> [--stems A,B,C]
# =============================================================================
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
WORKTREE = (HERE.parents[3] / ".claude/worktrees/hw-interface-prompt"
            / "isppipeline/hls/tools")

WB_SETTINGS = [("WB off", (256, 256, 256)),
               ("deployed 286/256/307", (286, 256, 307)),
               ("gray-world 479/256/686", (479, 256, 686))]
CLASS_NAMES = {0: "person", 1: "bicycle", 2: "car"}
BOX_COLOR, TXT_BG = (255, 60, 40), (255, 60, 40)


def font(size: int):
    """matplotlib ships DejaVu; PIL's bitmap default is unreadable at figure scale."""
    import matplotlib  # noqa: PLC0415
    from PIL import ImageFont  # noqa: PLC0415
    ttf = (Path(matplotlib.__file__).parent / "mpl-data/fonts/ttf/DejaVuSans.ttf")
    try:
        return ImageFont.truetype(str(ttf), size)
    except OSError:
        return ImageFont.load_default()


def load_pipeline():
    sys.path.insert(0, str(WORKTREE))
    import low_light_isp_pipeline as P  # noqa: PLC0415
    return P


def render(P, raw_path: Path, w: int, h: int, wb) -> np.ndarray:
    bayer = np.fromfile(raw_path, dtype="<u2")
    if bayer.size != w * h:
        raise ValueError(f"{raw_path.name}: {bayer.size} != {w}*{h}")
    return P.run_lowlight(bayer.reshape(h, w), w, h, wb=wb)


def detect_and_draw(img: np.ndarray, model, scale: int = 2):
    """Run the detector on the rendered frame, draw boxes, return a preview."""
    res = model.predict(img, imgsz=640, verbose=False, conf=0.25)[0]
    pil = Image.fromarray(img)
    pil = pil.resize((pil.width // scale, pil.height // scale), Image.BILINEAR)
    d = ImageDraw.Draw(pil)
    n = 0
    for b in res.boxes:
        cls = int(b.cls.item())
        if cls not in CLASS_NAMES:
            continue
        x1, y1, x2, y2 = (v / scale for v in b.xyxy[0].tolist())
        d.rectangle([x1, y1, x2, y2], outline=BOX_COLOR, width=3)
        d.text((x1 + 3, max(0, y1 - 21)),
               f"{CLASS_NAMES[cls]} {b.conf.item():.2f}", fill=TXT_BG,
               font=font(17))
        n += 1
    return pil, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="eval root with raw_bin/ + images/")
    ap.add_argument("--stems", default="", help="comma-separated; default: first 3")
    ap.add_argument("--width", type=int, default=5472)
    ap.add_argument("--height", type=int, default=3648)
    ap.add_argument("--scale", type=int, default=4, help="preview downscale")
    ap.add_argument("--out", default=str(HERE / "figures" / "F6_qualitative_wb.png"))
    a = ap.parse_args()

    from ultralytics import YOLO  # noqa: PLC0415
    P = load_pipeline()
    root = Path(a.root)
    stems = ([s.strip() for s in a.stems.split(",") if s.strip()]
             or sorted(p.stem for p in (root / "raw_bin").glob("*.bin"))[:3])
    model = YOLO(str(WORKTREE / "yolov8n.pt"))

    tiles, counts = [], {}
    for stem in stems:
        row = []
        for label, wb in WB_SETTINGS:
            img = render(P, root / "raw_bin" / f"{stem}.bin", a.width, a.height, wb)
            pil, n = detect_and_draw(img, model, scale=a.scale)
            counts[(stem, label)] = n
            row.append(pil)
            print(f"  {stem:14} {label:24} detections={n}", flush=True)
        tiles.append(row)

    tw, th = tiles[0][0].size
    pad, top = 8, 44
    hdr, sub = font(26), font(19)
    sheet = Image.new("RGB", (3 * tw + 4 * pad, len(tiles) * (th + pad) + top + pad),
                      (252, 252, 251))
    d = ImageDraw.Draw(sheet)
    for c, (label, _) in enumerate(WB_SETTINGS):
        d.text((pad + c * (tw + pad) + 4, 9), label, fill=(11, 11, 11), font=hdr)
    for r, (row, stem) in enumerate(zip(tiles, stems)):
        for c, pil in enumerate(row):
            x, y = pad + c * (tw + pad), top + r * (th + pad)
            sheet.paste(pil, (x, y))
            n = counts[(stem, WB_SETTINGS[c][0])]
            d.text((x + 8, y + th - 26), f"{stem}   detections: {n}",
                   fill=(255, 255, 255), font=sub)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=92)
    print(f"\nwrote {out}")
    for stem in stems:
        print(f"  {stem}: " + "  ".join(
            f"{lab.split()[0]}={counts[(stem, lab)]}" for lab, _ in WB_SETTINGS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
