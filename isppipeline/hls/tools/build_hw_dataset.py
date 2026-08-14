#!/usr/bin/env python3
"""build_hw_dataset.py -- CFA-preserving 4x reduction of the real-RAW test sets
(LOD .ARW / PASCALRAW .NEF) into a single FPGA-ingestable geometry.

Why this exists
---------------
The two real-RAW sets the campaign uses are far too large for the accelerator:
LOD is 5472x3648 and PASCALRAW 6034x4012, while dfxisp_accel.cpp:279 sizes its
low-light line buffers as `static uint16_t row_r[MAX_BINNED_W]` with
MAX_BINNED_W = 960 -- a hard array bound, i.e. raw width must stay <= 1920.
20 MPix/frame is also ~40 MB of DDR traffic per frame at uint16.

Contract produced here (both datasets, identical geometry):

    visible -> RGGB phase align -> even-offset CENTER CROP to 5472x3648
            -> same-colour 4x decimation           -> 1368x912
            -> per-channel BLC + white-level normalise -> 12-bit in uint16 LE

  * 1368x912 for BOTH sets, so the HW frame config, DDR footprint and
    per-frame timing are identical across datasets (the whole point: the
    two sets differ in scene content, not in pipeline geometry).
    LOD keeps 100% of its FOV; PASCAL is centre-cropped from 6034x4012 to
    5472x3648 (~82% of area) and its labels are re-derived accordingly.
  * low-light RM output is then 684x456, and 684 <= MAX_BINNED_W. OK.

Two deliberate choices (see the 2026-08-13 discussion):

1. Same-colour DECIMATION, not same-colour averaging. Averaging 4x4 blocks is
   the same operation RM_LOW_LIGHT already performs (2x2 binning), so it would
   pre-apply the effect under test and, by shrinking the noise, invalidate the
   2026-07-20 deployed calibration (BLC=2 / dark16 / DARK_RATIO_PCT=62), which
   was tuned on full-res per-pixel noise. Decimation keeps per-pixel noise
   statistics identical to the source sensor; the cost is aliasing, tolerable
   because the annotated classes (person/car/bicycle) are large.

2. 12-bit output, not the SW-eval shift8 convention. dfxisp_accel consumes
   12-bit (RAW12_MAX = 4095); shift8 values reach 65280 and would saturate
   every pixel. 12-bit also loses nothing: the shift8 view is recoverable as
   (v >> 4) << 8 (within +/-1 code of the old rounding), whereas the reverse
   is not true. Measured on the current shift8 LOD raw_bin, 99% of pixels sit
   in codes 0..6 of 255 -- 8-bit quantisation is where the low-light signal
   was being destroyed.

Bayer phase is verified analytically after decimation (the output's (0,0) must
still be R), not assumed.

Usage:
  python3 build_hw_dataset.py --selftest
  python3 build_hw_dataset.py --raw-dir dataset/LOD_test/raw \
      --labels-dir dataset/LOD_test/labels --out dataset/LOD_test_hw [--preview 3]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Target geometry, shared by every dataset this tool emits.
CROP_W, CROP_H = 5472, 3648          # even-offset centre crop of the visible area
DECIM = 4                            # same-colour reduction factor
OUT_W, OUT_H = CROP_W // DECIM, CROP_H // DECIM   # 1368 x 912
RAW12_MAX = 4095
RAW_EXTS = (".ARW", ".arw", ".NEF", ".nef", ".dng", ".DNG")


# ------------------------------------------------------------------- raw io --
def read_raw(path: Path):
    """(visible float64, colors uint8, color_desc, black_per_ch, white)."""
    import rawpy  # noqa: PLC0415  (optional dep, only needed for real ingest)
    with rawpy.imread(str(path)) as raw:
        visible = raw.raw_image_visible.astype(np.float64)
        colors = np.asarray(raw.raw_colors_visible, dtype=np.uint8)
        desc = raw.color_desc.decode() if isinstance(raw.color_desc, bytes) else str(raw.color_desc)
        black = [int(b) for b in raw.black_level_per_channel]
        white = int(np.ravel(raw.white_level)[0]) if raw.white_level is not None else int(visible.max())
    return visible, colors, desc, black, white


def rggb_phase(colors: np.ndarray, color_desc: str) -> tuple[int, int]:
    """Return the (dy, dx) in {0,1}^2 whose 2x2 quad reads R G / G B."""
    lut = {i: ch for i, ch in enumerate(color_desc)}
    for dy in (0, 1):
        for dx in (0, 1):
            quad = "".join(lut[int(colors[dy + a, dx + b])]
                           for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)))
            if quad == "RGGB":
                return dy, dx
    raise ValueError(f"no RGGB phase found for color_desc={color_desc!r}")


def center_crop_even(arr: np.ndarray, dy: int, dx: int, w: int, h: int):
    """Centre-crop to (h, w) starting from the RGGB-aligned origin (dy, dx).
    Offsets are forced even so the crop keeps the R G / G B phase."""
    src = arr[dy:, dx:]
    sh, sw = src.shape[:2]
    if sh < h or sw < w:
        raise ValueError(f"source {sw}x{sh} smaller than crop {w}x{h}")
    y0 = ((sh - h) // 2) & ~1
    x0 = ((sw - w) // 2) & ~1
    return src[y0:y0 + h, x0:x0 + w], (dx + x0, dy + y0)


def decimate_cfa(arr: np.ndarray, factor: int = DECIM) -> np.ndarray:
    """Same-colour decimation: keep the top-left quad of every factor x factor
    block of Bayer quads, so the output is still R G / G B at (0,0).
    out[py::2, px::2] = arr[py::2*factor, px::2*factor] for each colour phase."""
    step = 2 * factor
    h, w = arr.shape[0] // factor, arr.shape[1] // factor
    out = np.empty((h, w), dtype=arr.dtype)
    for py in (0, 1):
        for px in (0, 1):
            out[py::2, px::2] = arr[py::step, px::step]
    return out


def to_raw12(visible: np.ndarray, colors: np.ndarray, black: list[int], white: int) -> np.ndarray:
    """Per-channel black subtract -> normalise by (white - black) -> 12-bit.
    Same normalisation shape as the old to_shift8_bin, at 4 more bits."""
    blk = np.asarray(black, dtype=np.float64)[colors]
    denom = max(float(white) - float(np.median(blk)), 1.0)
    lin = np.clip((visible - blk) / denom, 0.0, 1.0)
    return np.round(lin * RAW12_MAX).astype("<u2")


# ------------------------------------------------------------------ labels --
def remap_labels(lines: list[str], vis_w: int, vis_h: int,
                 crop_x: int, crop_y: int, min_visible: float) -> tuple[list[str], int, int]:
    """YOLO labels are normalised against the full visible frame; re-normalise
    them against the crop, clipping partials. Returns (lines, clipped, dropped).

    A box is dropped when less than `min_visible` of its original area survives
    the crop -- a sliver of a person at the frame edge is not a detectable GT
    and would only manufacture false negatives."""
    out, clipped, dropped = [], 0, 0
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        cls, cx, cy, nw, nh = parts[0], *(float(v) for v in parts[1:])
        # normalised (visible frame) -> pixel (visible frame)
        px1, px2 = (cx - nw / 2) * vis_w, (cx + nw / 2) * vis_w
        py1, py2 = (cy - nh / 2) * vis_h, (cy + nh / 2) * vis_h
        area0 = max(px2 - px1, 0.0) * max(py2 - py1, 0.0)
        # -> pixel (crop frame), clipped
        qx1, qx2 = np.clip([px1 - crop_x, px2 - crop_x], 0, CROP_W)
        qy1, qy2 = np.clip([py1 - crop_y, py2 - crop_y], 0, CROP_H)
        area1 = max(qx2 - qx1, 0.0) * max(qy2 - qy1, 0.0)
        if area0 <= 0 or area1 / area0 < min_visible:
            dropped += 1
            continue
        if area1 < area0 - 1e-6:
            clipped += 1
        out.append("{} {:.6f} {:.6f} {:.6f} {:.6f}".format(
            cls, (qx1 + qx2) / 2 / CROP_W, (qy1 + qy2) / 2 / CROP_H,
            (qx2 - qx1) / CROP_W, (qy2 - qy1) / CROP_H))
    return out, clipped, dropped


# ----------------------------------------------------------------- preview --
def write_preview(raw12: np.ndarray, path: Path) -> None:
    """Nearest-neighbour RGGB demosaic + gamma 2.0, for eyeballing that the
    CFA phase survived. Not part of the contract -- verification aid only."""
    from PIL import Image  # noqa: PLC0415
    r = raw12[0::2, 0::2].astype(np.float32)
    g = (raw12[0::2, 1::2].astype(np.float32) + raw12[1::2, 0::2]) / 2
    b = raw12[1::2, 1::2].astype(np.float32)
    rgb = np.stack([r, g, b], -1) / RAW12_MAX
    rgb = np.sqrt(np.clip(rgb * 8.0, 0, 1))          # 8x gain so LOD is visible
    Image.fromarray((rgb * 255).astype(np.uint8)).save(path, quality=88)


# -------------------------------------------------------------------- main --
def convert_one(raw_path: Path, label_path: Path | None, out_dir: Path,
                min_visible: float, preview: bool) -> dict:
    visible, colors, desc, black, white = read_raw(raw_path)
    vis_h, vis_w = visible.shape
    dy, dx = rggb_phase(colors, desc)
    vis_c, (crop_x, crop_y) = center_crop_even(visible, dy, dx, CROP_W, CROP_H)
    col_c, _ = center_crop_even(colors, dy, dx, CROP_W, CROP_H)

    dec_v, dec_c = decimate_cfa(vis_c), decimate_cfa(col_c)
    lut = {i: ch for i, ch in enumerate(desc)}
    quad = "".join(lut[int(dec_c[a, b])] for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)))
    if quad != "RGGB":
        raise AssertionError(f"{raw_path.name}: phase broken by decimation -> {quad}")
    if dec_v.shape != (OUT_H, OUT_W):
        raise AssertionError(f"{raw_path.name}: got {dec_v.shape}, want {(OUT_H, OUT_W)}")

    raw12 = to_raw12(dec_v, dec_c, black, white)
    raw12.tofile(out_dir / "raw_bin" / f"{raw_path.stem}.bin")
    if preview:
        write_preview(raw12, out_dir / "preview" / f"{raw_path.stem}.jpg")

    clipped = dropped = kept = 0
    if label_path is not None and label_path.exists():
        src = [ln for ln in label_path.read_text().splitlines() if ln.strip()]
        lines, clipped, dropped = remap_labels(src, vis_w, vis_h, crop_x, crop_y, min_visible)
        kept = len(lines)
        (out_dir / "labels" / f"{raw_path.stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""))
    return {"stem": raw_path.stem, "visible": [vis_w, vis_h], "phase": [dx, dy],
            "crop_origin": [crop_x, crop_y], "black": black, "white": white,
            "boxes_kept": kept, "boxes_clipped": clipped, "boxes_dropped": dropped,
            "raw12_max": int(raw12.max()), "raw12_mean": round(float(raw12.mean()), 2)}


def selftest() -> int:
    """Pure-logic checks; no dataset needed."""
    # 1. decimation keeps the colour phase and picks the expected source pixels
    h, w = 3648, 5472
    ramp = (np.arange(h)[:, None] * 10000 + np.arange(w)[None, :]).astype(np.float64)
    dec = decimate_cfa(ramp)
    assert dec.shape == (OUT_H, OUT_W), dec.shape
    # each kept quad is taken whole (co-sited R/G/G/B), one per 4x4 block of quads
    assert dec[0, 0] == ramp[0, 0] and dec[0, 1] == ramp[0, 1]
    assert dec[1, 0] == ramp[1, 0] and dec[1, 1] == ramp[1, 1]
    assert dec[0, 2] == ramp[0, 8] and dec[2, 0] == ramp[8, 0]
    assert dec[2, 2] == ramp[8, 8] and dec[3, 3] == ramp[9, 9]
    colors = np.tile(np.array([[0, 1], [3, 2]], np.uint8), (h // 2, w // 2))
    dc = decimate_cfa(colors)
    assert dc[0, 0] == 0 and dc[0, 1] == 1 and dc[1, 0] == 3 and dc[1, 1] == 2

    # 2. even-offset centre crop on an odd-margin source (PASCAL geometry)
    src = np.zeros((4012, 6034))
    _, (cx, cy) = center_crop_even(src, 0, 0, CROP_W, CROP_H)
    assert (cx, cy) == (280, 182), (cx, cy)

    # 3. 12-bit normalisation endpoints
    v = np.array([[800.0, 16380.0], [800.0, 16380.0]])
    c = np.array([[0, 1], [3, 2]], np.uint8)
    q = to_raw12(v, c, [800] * 4, 16380)
    assert q[0, 0] == 0 and q[0, 1] == RAW12_MAX, q

    # 4. label remap: identity crop is a no-op; edge box is dropped
    ident, cl, dr = remap_labels(["1 0.5 0.5 0.2 0.2"], CROP_W, CROP_H, 0, 0, 0.25)
    assert ident == ["1 0.500000 0.500000 0.200000 0.200000"] and (cl, dr) == (0, 0), ident
    _, _, dr = remap_labels(["1 0.01 0.5 0.04 0.2"], 6034, 4012, 280, 182, 0.25)
    assert dr == 1
    kept, cl, _ = remap_labels(["1 0.5 0.5 1.0 1.0"], 6034, 4012, 280, 182, 0.25)
    assert len(kept) == 1 and cl == 1
    print("selftest OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path)
    ap.add_argument("--labels-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--preview", type=int, default=0, help="write N preview JPEGs")
    ap.add_argument("--min-visible", type=float, default=0.25,
                    help="drop a box when less than this fraction survives the crop")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.raw_dir and a.out):
        ap.error("--raw-dir and --out are required")

    raws = sorted(p for p in a.raw_dir.iterdir() if p.suffix in RAW_EXTS)
    if a.limit:
        raws = raws[:a.limit]
    for sub in ("raw_bin", "labels", "preview"):
        (a.out / sub).mkdir(parents=True, exist_ok=True)

    frames, errors = [], []
    for i, p in enumerate(raws):
        lab = (a.labels_dir / f"{p.stem}.txt") if a.labels_dir else None
        try:
            frames.append(convert_one(p, lab, a.out, a.min_visible, i < a.preview))
        except Exception as exc:                     # noqa: BLE001 -- log and continue
            errors.append(f"{p.name}: {type(exc).__name__}: {exc}")
            print(f"  ! {p.name}: {exc}", file=sys.stderr)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(raws)}", flush=True)

    meta = {"out_width": OUT_W, "out_height": OUT_H, "crop": [CROP_W, CROP_H],
            "decimation": DECIM, "method": "same-colour decimation (no averaging)",
            "bayer": "RGGB", "raw_format": "12-bit in uint16 LE (0..4095)",
            "min_visible": a.min_visible, "source_raw_dir": str(a.raw_dir),
            "frames": frames, "errors": errors}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=2))
    kept = sum(f["boxes_kept"] for f in frames)
    print(f"{len(frames)} frames -> {a.out}  ({OUT_W}x{OUT_H}, 12-bit)  "
          f"boxes kept={kept} clipped={sum(f['boxes_clipped'] for f in frames)} "
          f"dropped={sum(f['boxes_dropped'] for f in frames)} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
