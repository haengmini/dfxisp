#!/usr/bin/env python3
"""aodraw_adapter.py -- ingest the AODRaw dataset into the dfxisp SW-eval
layout (images/ + labels/ + raw_bin/ + meta.json), PLUS a per-frame metadata
table that the checker #4 (oracle relabeling) and #1 (sensor-adaptive tau)
campaigns need.

Campaign : checker-sota #4-1 (2026-07-09), branch exp/principled-checker-rm-2026-07-05.
Track    : checker-strengthening-2026-07-10.md item #4 step 1 ("AODRaw adapter,
           the critical-path prerequisite for #4 and #1"). Pre-written while the
           dataset is still downloading; the ONLY unverifiable path is the real
           .ARW decode (reuses the proven rawpy path from build_sonynod_dataset.py).

AODRaw (Li et al., CVPR 2025 Highlight; github.com/lzyhha/AODRaw):
  * Real Sony .ARW RAW, original 6000x4000; also images_downsampled_raw
    (2000x1333) and images_slice_raw (1280x1280) variants.
  * COCO-format annotations; each image record carries a `tag` list encoding
    the light/weather condition (e.g. ["low_light"], ["daylight","fog"]).
    This is the illumination axis #4 needs and a first-cut illum label.
  * 62 categories -> remapped to COCO-80 ids by NAME (overlap only; others
    dropped) so the existing yolov8 eval (eval_map_newrm.py) consumes it.

Contract this must satisfy (see build_sonynod_dataset.py / SPEC.md s2):
  raw_bin/<stem>.bin : little-endian uint16, "shift8" convention
      value = round(linear*255) << 8, RGGB phase at (0,0), even dims, so the
      unmodified baseline core / newrm_pipeline.py (bayer16 >> 8) and
      checker_stat_sweep.py (raw>>8) consume it drop-in.
  images/<stem>.jpg  : sRGB preview (loaders recover W,H from this).
  labels/<stem>.txt  : YOLO cx cy w h (normalized), COCO-80 0-indexed ids.
  meta.json          : dataset-level provenance.
  frames_meta.csv    : NEW -- per-frame {stem,w,h,tag,light,weather,iso,
      exposure_s,f_number,black_level,white_level,bayer,dark16} for #4/#1.

KEY DIFFERENCE from the single-body sonynod adapter: AODRaw spans conditions,
so black level / white level / Bayer phase are read PER FILE from rawpy
(black_level_per_channel, white_level, raw_colors_visible) rather than
hardcoded. Per-channel black subtraction + RGGB phase alignment are computed
from raw_colors_visible so any orientation lands as RGGB.

Usage:
  # dry checks with no dataset present:
  python3 tools/aodraw_adapter.py --selftest
  # real ingest once the download finishes:
  python3 tools/aodraw_adapter.py \\
      --ann  <AODRaw>/annotations/test_annotations_downsample_scale3_bbox_min_size32.json \\
      --raw-dir <AODRaw>/images_downsampled_raw \\
      --out  ../../data/aodraw_test \\
      [--limit N] [--exiftool /usr/bin/exiftool]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------- COCO-80 --
# 0-indexed COCO-80 class names, in canonical order (matches ultralytics
# yolov8 .names and the ids the existing eval expects, see build_sonynod).
COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]
COCO80_ID = {n: i for i, n in enumerate(COCO80)}
# A few AODRaw<->COCO name aliases (extend as the real categories are seen).
NAME_ALIASES = {
    "aeroplane": "airplane", "motorbike": "motorcycle", "sofa": "couch",
    "pottedplant": "potted plant", "diningtable": "dining table",
    "tvmonitor": "tv", "cellphone": "cell phone", "trafficlight": "traffic light",
}

KNOWN_LIGHT = {"daylight", "low_light", "lowlight", "night", "dark"}
KNOWN_WEATHER = {"clear", "rain", "fog", "cloudy", "snow"}


# ---------------------------------------------------------------- raw decode --
def read_raw(path: Path):
    """Return (visible_bayer float64, colors uint8, color_desc str, meta dict).
    THE single point to adapt for non-.ARW variants. .ARW is TIFF-based Sony
    RAW; rawpy handles original + downsampled_raw (still .ARW). If a variant
    ships as a plain packed array, replace only this function's body."""
    import rawpy  # noqa: PLC0415  (optional dep; only needed for real ingest)
    with rawpy.imread(str(path)) as raw:
        visible = raw.raw_image_visible.astype(np.float64)
        colors = np.asarray(raw.raw_colors_visible, dtype=np.uint8)
        color_desc = (raw.color_desc.decode() if isinstance(raw.color_desc, bytes)
                      else str(raw.color_desc))            # e.g. "RGBG"
        blc = list(raw.black_level_per_channel)            # per pattern index
        white = int(np.ravel(raw.white_level)[0]) if raw.white_level is not None \
            else int(visible.max())
        meta = {"black_level_per_channel": blc, "white_level": white}
    return visible, colors, color_desc, meta


def rggb_align_crop(visible: np.ndarray, colors: np.ndarray, color_desc: str):
    """Even-crop so the top-left 2x2 quad is exactly R,G / G,B (the pipeline's
    RGGB assumption in demosaic_rggb12). color_desc maps pattern index->letter;
    we search the 4 phase offsets for the one whose quad reads R G / G B."""
    letters = np.array(list(color_desc))                   # index -> 'R'/'G'/'B'
    lut = {i: letters[i] for i in range(len(letters))}
    def q(y, x):
        return "".join(lut[int(colors[y, x])] for y, x in
                       ((y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)))
    for dy in (0, 1):
        for dx in (0, 1):
            if q(dy, dx) == "RGGB":
                v = visible[dy:, dx:]
                c = colors[dy:, dx:]
                h, w = v.shape
                h, w = h - h % 2, w - w % 2
                return v[:h, :w], c[:h, :w]
    raise ValueError(f"no RGGB phase found for color_desc={color_desc!r}")


def to_shift8_bin(visible: np.ndarray, colors: np.ndarray,
                  blc_per_ch: list[int], white: int) -> np.ndarray:
    """Per-channel black subtract -> normalize to [0,1] by (white-black) ->
    quantize to 8-bit -> shift8 uint16, matching the existing pseudo-RAW scale
    (round(linear*255) << 8). Per-channel black uses the pattern index map."""
    black = np.asarray(blc_per_ch, dtype=np.float64)[colors]     # per-pixel BLC
    denom = max(float(white) - float(np.median(black)), 1.0)
    lin = np.clip((visible - black) / denom, 0.0, 1.0)
    u8 = np.round(lin * 255.0).astype(np.uint16)
    return (u8 << 8).astype("<u2")


# ------------------------------------------------------------------- labels --
def build_category_map(coco: dict) -> dict[int, int]:
    """AODRaw category_id -> COCO-80 0-indexed id, matched by (normalized)
    name. Categories with no COCO-80 counterpart are dropped."""
    out: dict[int, int] = {}
    for c in coco.get("categories", []):
        name = str(c["name"]).strip().lower()
        name = NAME_ALIASES.get(name, name)
        if name in COCO80_ID:
            out[c["id"]] = COCO80_ID[name]
    return out


def coco_to_yolo(annos: list, w: int, h: int, catmap: dict[int, int]) -> list[str]:
    lines = []
    for a in annos:
        cls = catmap.get(a["category_id"])
        if cls is None:
            continue
        x, y, bw, bh = a["bbox"]
        cx, cy, nw, nh = (x + bw / 2) / w, (y + bh / 2) / h, bw / w, bh / h
        cx, cy, nw, nh = (max(0.0, min(1.0, v)) for v in (cx, cy, nw, nh))
        if nw <= 0 or nh <= 0:
            continue
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
    return lines


def parse_tag(tag) -> tuple[str, str]:
    """AODRaw `tag` list -> (light, weather). Unknown tokens ignored; missing
    light defaults to 'daylight' (dataset convention: low_light is tagged)."""
    toks = [str(t).strip().lower() for t in (tag or [])]
    light = next((t for t in toks if t in KNOWN_LIGHT), "daylight")
    weather = next((t for t in toks if t in KNOWN_WEATHER), "clear")
    if light in ("lowlight", "night", "dark"):
        light = "low_light"
    return light, weather


# --------------------------------------------------------------------- EXIF --
def extract_exif(path: Path, exiftool: str | None) -> dict:
    """Best-effort ISO / exposure / f-number for #1's tau(exposure,gain).
    Tries exiftool (-j) if given/available, then falls back to the pure-python
    `exifread` package (found missing the exiftool CLI binary during the
    PASCALRAW ingest, 2026-07-15 -- every one of 4259 frames came back null;
    exifread reads the same TIFF/EXIF IFD that ARW/NEF both embed, no
    subprocess needed). Records nulls only if BOTH fail. rawpy does NOT
    expose these, so this stays a separate, optional pass."""
    out = {"iso": None, "exposure_s": None, "f_number": None}
    tool = exiftool or "exiftool"
    try:
        r = subprocess.run([tool, "-j", "-n", "-ISO", "-ExposureTime",
                            "-FNumber", str(path)], capture_output=True,
                           text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)[0]
            out["iso"] = d.get("ISO")
            out["exposure_s"] = d.get("ExposureTime")
            out["f_number"] = d.get("FNumber")
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError,
            IndexError):
        pass
    try:
        import exifread  # noqa: PLC0415  (optional dep; exiftool-CLI fallback)
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        if "EXIF ISOSpeedRatings" in tags:
            out["iso"] = float(str(tags["EXIF ISOSpeedRatings"]))
        if "EXIF ExposureTime" in tags:
            out["exposure_s"] = float(tags["EXIF ExposureTime"].values[0])
        if "EXIF FNumber" in tags:
            out["f_number"] = float(tags["EXIF FNumber"].values[0])
    except Exception:  # noqa: BLE001  (missing dep, corrupt tags, etc.)
        pass
    return out


# ------------------------------------------------------------------ preview --
def raw_to_preview(path: Path):
    import rawpy  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False,
                              output_bps=8)
    return Image.fromarray(rgb)


# ------------------------------------------------------------------- ingest --
def ingest(ann: Path, raw_dir: Path, out: Path, limit: int | None,
           exiftool: str | None) -> None:
    coco = json.loads(ann.read_text())
    images = coco["images"] if isinstance(coco["images"], list) else \
        list(coco["images"].values())
    annos_by_img: dict[int, list] = {}
    for a in coco["annotations"]:
        annos_by_img.setdefault(a["image_id"], []).append(a)
    catmap = build_category_map(coco)
    print(f"category map: {len(catmap)}/{len(coco.get('categories', []))} "
          f"AODRaw categories -> COCO-80", file=sys.stderr)

    for sub in ("images", "labels", "raw_bin"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    n_ok = n_skip = n_noanno = 0
    errors: list[str] = []
    meta_rows: list[dict] = []
    for im in sorted(images, key=lambda x: x["id"]):
        if limit and n_ok >= limit:
            break
        fn = im["file_name"]
        stem = Path(fn).stem
        rp = raw_dir / fn
        if not rp.exists():
            n_skip += 1
            errors.append(f"missing RAW: {fn}")
            continue
        light, weather = parse_tag(im.get("tag"))
        lines = coco_to_yolo(annos_by_img.get(im["id"], []),
                             im["width"], im["height"], catmap)
        if not lines:
            n_noanno += 1
            continue
        try:
            visible, colors, cdesc, smeta = read_raw(rp)
            vis, col = rggb_align_crop(visible, colors, cdesc)
            raw_bin = to_shift8_bin(vis, col, smeta["black_level_per_channel"],
                                    smeta["white_level"])
            preview = raw_to_preview(rp)
        except Exception as e:  # noqa: BLE001
            n_skip += 1
            errors.append(f"decode failed {fn}: {e}")
            continue
        h, w = raw_bin.shape if raw_bin.ndim == 2 else (vis.shape)
        raw_bin.tofile(out / "raw_bin" / f"{stem}.bin")
        preview.save(out / "images" / f"{stem}.jpg", quality=95)
        (out / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")
        exif = extract_exif(rp, exiftool)
        dark16 = float((((raw_bin >> 8) < 16).mean()))       # #4 illum proxy
        meta_rows.append({
            "stem": stem, "w": vis.shape[1], "h": vis.shape[0],
            "light": light, "weather": weather,
            "iso": exif["iso"], "exposure_s": exif["exposure_s"],
            "f_number": exif["f_number"],
            "black_level": int(np.median(smeta["black_level_per_channel"])),
            "white_level": smeta["white_level"], "bayer": "RGGB",
            "dark16": round(dark16, 5),
            "illum_label": 1 if light == "low_light" else 0,
        })
        n_ok += 1
        if n_ok % 100 == 0:
            print(f"  converted {n_ok}", file=sys.stderr)

    (out / "convert_errors.log").write_text("\n".join(errors) + ("\n" if errors else ""))
    if meta_rows:
        with (out / "frames_meta.csv").open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(meta_rows[0].keys()))
            wr.writeheader()
            wr.writerows(meta_rows)
    (out / "meta.json").write_text(json.dumps({
        "source_annotations": str(ann), "raw_dir": str(raw_dir),
        "dataset": "AODRaw (Li et al., CVPR2025)",
        "scale": "shift8 (round(linear*255)<<8); per-file black/white/bayer "
                 "from rawpy; RGGB phase-aligned",
        "n_images_total": len(images), "n_converted": n_ok,
        "n_skipped": n_skip, "n_no_gt": n_noanno,
        "n_categories_mapped": len(catmap),
        "exif": "exiftool best-effort (iso/exposure/f_number may be null)",
    }, indent=2))
    print(f"converted={n_ok} skipped={n_skip} no_gt={n_noanno} "
          f"total={len(images)}")


# ----------------------------------------------------------------- selftest --
def _selftest() -> int:
    """Exercise every pure-logic path (align, per-channel BLC/shift8, label +
    category remap, tag parse) with synthetic data. The only thing NOT covered
    is the real rawpy .ARW decode (needs a real file); that path reuses the
    proven build_sonynod_dataset.py idiom."""
    ok = True

    # (1) RGGB alignment from a BGGR-phase sensor: top-left must become R.
    #     color_desc "RGBG": 0=R,1=G,2=B,3=G. Build a 4x4 whose (0,0)=B(=idx2).
    cd = "RGBG"
    base = np.array([[2, 1, 2, 1],   # B G B G
                     [1, 0, 1, 0],   # G R G R  <- R at (1,1)
                     [2, 1, 2, 1],
                     [1, 0, 1, 0]], dtype=np.uint8)
    vis = (base.astype(np.float64) + 1) * 100  # arbitrary values
    v2, c2 = rggb_align_crop(vis, base, cd)
    letters = np.array(list(cd))
    q = "".join(letters[c2[y, x]] for y, x in ((0, 0), (0, 1), (1, 0), (1, 1)))
    assert q == "RGGB", f"align produced {q}"
    print(f"[ok] rggb_align_crop: BGGR->crop-> quad={q}, shape {vis.shape}->{v2.shape}")

    # (2) per-channel black subtract + shift8 scale.
    colors = np.array([[0, 1], [1, 2]], dtype=np.uint8)   # R G / G B
    blc = [512, 512, 512, 512]
    white = 512 + 255                                     # so linear=1.0 at +255
    visible = np.array([[512.0, 512 + 128], [512 + 64, 767]])
    b = to_shift8_bin(visible, colors, blc, white)
    exp = (np.round(np.array([[0, 128], [64, 255]]) / 255 * 255).astype(np.uint16) << 8)
    assert np.array_equal(b, exp.astype("<u2")), f"shift8 got {b} exp {exp}"
    assert b.dtype == np.dtype("<u2")
    assert int((b[0, 0] >> 8)) == 0 and int((b[1, 1] >> 8)) == 255
    print(f"[ok] to_shift8_bin: per-channel BLC + shift8, raw>>8 in [0,255]")

    # (3) category remap by name + alias, and label conversion.
    coco = {"categories": [{"id": 5, "name": "person"},
                           {"id": 9, "name": "aeroplane"},   # alias->airplane
                           {"id": 12, "name": "sofa"},        # alias->couch
                           {"id": 40, "name": "widget"}]}     # no COCO match
    cm = build_category_map(coco)
    assert cm == {5: 0, 9: 4, 12: 57}, cm
    lines = coco_to_yolo([{"category_id": 5, "bbox": [10, 20, 40, 60]},
                          {"category_id": 40, "bbox": [0, 0, 5, 5]}],  # dropped
                         w=100, h=100, catmap=cm)
    assert lines == ["0 0.300000 0.500000 0.400000 0.600000"], lines
    print(f"[ok] category remap {cm} + coco_to_yolo drops unmapped")

    # (4) tag parsing.
    assert parse_tag(["low_light"]) == ("low_light", "clear")
    assert parse_tag(["daylight", "fog"]) == ("daylight", "fog")
    assert parse_tag(["night", "rain"]) == ("low_light", "rain")
    assert parse_tag(None) == ("daylight", "clear")
    print("[ok] parse_tag light/weather extraction")

    # (5) EXIF fallback must not raise when the tool is absent.
    e = extract_exif(Path("/nonexistent.ARW"), exiftool="definitely-not-a-tool")
    assert e == {"iso": None, "exposure_s": None, "f_number": None}
    print("[ok] extract_exif graceful fallback (no tool)")

    print("\nselftest: ALL PASS" if ok else "selftest: FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ann", type=Path, help="AODRaw COCO annotations json")
    ap.add_argument("--raw-dir", type=Path, help="dir with the referenced RAW files")
    ap.add_argument("--out", type=Path, help="output dataset dir")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--exiftool", default=None, help="path to exiftool binary")
    ap.add_argument("--selftest", action="store_true",
                    help="run pure-logic self-tests (no dataset needed)")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if not (args.ann and args.raw_dir and args.out):
        ap.error("--ann, --raw-dir, --out required (or use --selftest)")
    ingest(args.ann, args.raw_dir, args.out, args.limit, args.exiftool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
