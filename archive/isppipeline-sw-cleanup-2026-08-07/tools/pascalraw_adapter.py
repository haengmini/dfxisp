#!/usr/bin/env python3
"""pascalraw_adapter.py -- ingest the PASCALRAW dataset into the same
dfxisp SW-eval layout aodraw_adapter.py produces (images/ + labels/ +
raw_bin/ + meta.json + frames_meta.csv).

Campaign : checker-sota #4/#1 real-data track, pre-written 2026-07-13 while
           the dataset is still downloading (same precedent as
           aodraw-adapter-2026-07-09.md -- write the adapter against the
           documented format, verify pure logic with synthetic data, leave
           only the real-file decode path for once files exist).

Why PASCALRAW specifically: results/checker-status-2026-07-10.md SS4 and
results/checker-adaptive-tau-realdata-2026-07-13.md SS0 both flag the same
gap -- SonyNOD/RAW-NOD is 100% evening/night, so recall (LOW_LIGHT correctly
triggered) is all that's been measurable so far. checker's OTHER failure
mode, false-trigger (a normal-light scene wrongly routed to LOW_LIGHT), has
no daylight real-RAW comparison group yet. PASCALRAW is exactly that:
4,259 annotated RAW images, ALL DAYTIME, Nikon D3200, person/car/bicycle
labels drawn to PASCAL VOC guidelines (Omid-Zohoor et al., Stanford Digital
Repository purl.stanford.edu/hq050zr7488). Once ingested this becomes the
"should stay NORMAL" ground truth checker_status.md SS0 says SonyNOD cannot
supply -- run analyze_adaptive_tau_sonynod.py's checker logic against this
adapter's output and every LOW_LIGHT verdict is by definition a false
trigger.

Dataset facts confirmed from the official Stanford record + paper (see
module docstring footer for sources -- NOT independently re-verified since
the files aren't local yet; recheck against the actual README.txt on first
real run, same caveat aodraw_adapter.py's read_raw() carries):
  * RAW format: Nikon .NEF, 12-bit, Bayer RGGB, Nikon D3200, 6034x4012 full
    res (rawpy/libraw decodes .NEF natively -- same idiom as .ARW).
  * Annotations: one PASCAL VOC-style XML per image (<annotation><object>
    <name>...</name><bndbox><xmin>/<ymin>/<xmax>/<ymax></bndbox></object>...
    </annotation>), 3 classes: person, car, bicycle -- all three are
    COCO-80 names verbatim, so no alias table is needed (contrast AODRaw's
    62-category remap).
  * 100% daylight captures (Palo Alto / San Francisco streets) -- there is
    no per-image light/weather tag to parse; light is hardcoded "daylight",
    illum_label=0 for every frame. This is the intentional complement to
    AODRaw/SonyNOD's low-light-only coverage.
  * Black level / white level / Bayer phase: NOT hardcoded, read per-file
    from rawpy exactly like aodraw_adapter.py, even though every frame
    shares one camera body -- keeps the two adapters' contracts identical
    and costs nothing.

Directory layout is NOT assumed (the official archive's exact folder names
weren't confirmed pre-download -- a third-party derivative repo uses
Annotations/*.xml + JPEGImages/*.png, which is a *converted* copy, not the
raw .NEF originals we want). This adapter instead takes --ann-dir and
--raw-dir as plain directories and matches files by stem, so it is robust
to whatever the real archive's folder names turn out to be.

Contract (identical to aodraw_adapter.py -- see that module for the
rationale): raw_bin/<stem>.bin (shift8 uint16 RGGB), images/<stem>.jpg,
labels/<stem>.txt (YOLO, COCO-80 0-indexed), meta.json, frames_meta.csv.

Usage:
  python3 tools/pascalraw_adapter.py --selftest        # no dataset needed
  python3 tools/pascalraw_adapter.py \\
      --ann-dir <PASCALRAW>/Annotations \\
      --raw-dir <PASCALRAW>/NEF \\
      --out ../../data/pascalraw_test [--limit N] [--exiftool /usr/bin/exiftool]

Sources: purl.stanford.edu/hq050zr7488 (PASCALRAW: Raw Image Database for
Object Detection, Omid-Zohoor/Ta/Murmann, Stanford Digital Repository);
tools/aodraw_adapter.py (shared read_raw/rggb_align_crop/to_shift8_bin/
extract_exif -- imported, not duplicated).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aodraw_adapter import (  # noqa: E402
    COCO80_ID, extract_exif, raw_to_preview, read_raw, rggb_align_crop,
    to_shift8_bin,
)

# PASCALRAW's 3 classes are COCO-80 names verbatim; kept as a table (not a
# bare set) so a future 4th class or a naming quirk found on the real README
# is a one-line fix, same posture as aodraw_adapter.NAME_ALIASES.
NAME_ALIASES = {"pedestrian": "person"}

# Nikon .NEF is the only variant PASCALRAW ships in; if the real archive
# turns out to use a different extension, add it here (mirrors
# aodraw_adapter.read_raw's "single point to adapt" note).
RAW_EXTS = (".NEF", ".nef")


# ------------------------------------------------------------------- labels --
def parse_voc_xml(path: Path) -> tuple[int, int, list[tuple[str, float, float, float, float]]]:
    """Parse one PASCAL VOC-style annotation file -> (width, height, objects),
    objects = [(class_name_lower, xmin, ymin, xmax, ymax), ...] in pixel
    coords (VOC bboxes are 1-indexed inclusive pixel corners per the
    standard devkit convention; treated as plain pixel coords here since a
    +/-1px offset is far below this pipeline's bbox-normalization precision)."""
    root = ET.parse(path).getroot()
    size = root.find("size")
    w = int(size.findtext("width")) if size is not None else None
    h = int(size.findtext("height")) if size is not None else None
    objs = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip().lower()
        bb = obj.find("bndbox")
        if bb is None:
            continue
        xmin, ymin = float(bb.findtext("xmin")), float(bb.findtext("ymin"))
        xmax, ymax = float(bb.findtext("xmax")), float(bb.findtext("ymax"))
        objs.append((name, xmin, ymin, xmax, ymax))
    return w, h, objs


def voc_to_yolo(objs: list, w: int, h: int) -> list[str]:
    lines = []
    for name, xmin, ymin, xmax, ymax in objs:
        name = NAME_ALIASES.get(name, name)
        cls = COCO80_ID.get(name)
        if cls is None:
            continue
        bw, bh = xmax - xmin, ymax - ymin
        cx, cy = xmin + bw / 2, ymin + bh / 2
        cx, cy, nw, nh = cx / w, cy / h, bw / w, bh / h
        cx, cy, nw, nh = (max(0.0, min(1.0, v)) for v in (cx, cy, nw, nh))
        if nw <= 0 or nh <= 0:
            continue
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
    return lines


def find_raw_file(raw_dir: Path, stem: str) -> Path | None:
    for ext in RAW_EXTS:
        p = raw_dir / f"{stem}{ext}"
        if p.exists():
            return p
    return None


# ------------------------------------------------------------------- ingest --
def ingest(ann_dir: Path, raw_dir: Path, out: Path, limit: int | None,
           exiftool: str | None) -> None:
    xml_files = sorted(ann_dir.glob("*.xml"))
    for sub in ("images", "labels", "raw_bin"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    n_ok = n_skip = n_noanno = 0
    errors: list[str] = []
    meta_rows: list[dict] = []
    for xp in xml_files:
        if limit and n_ok >= limit:
            break
        stem = xp.stem
        rp = find_raw_file(raw_dir, stem)
        if rp is None:
            n_skip += 1
            errors.append(f"missing RAW: {stem}")
            continue
        try:
            xw, xh, objs = parse_voc_xml(xp)
        except ET.ParseError as e:
            n_skip += 1
            errors.append(f"xml parse failed {xp.name}: {e}")
            continue
        try:
            visible, colors, cdesc, smeta = read_raw(rp)
            vis, col = rggb_align_crop(visible, colors, cdesc)
            raw_bin = to_shift8_bin(vis, col, smeta["black_level_per_channel"],
                                    smeta["white_level"])
            preview = raw_to_preview(rp)
        except Exception as e:  # noqa: BLE001
            n_skip += 1
            errors.append(f"decode failed {stem}: {e}")
            continue
        h, w = vis.shape
        # Prefer the XML's declared size for bbox normalization (matches the
        # coordinate space the annotator actually drew in); fall back to the
        # decoded raw's own dims if the XML omitted <size>.
        lw, lh = (xw, xh) if (xw and xh) else (w, h)
        lines = voc_to_yolo(objs, lw, lh)
        if not lines:
            n_noanno += 1
            continue
        raw_bin.tofile(out / "raw_bin" / f"{stem}.bin")
        preview.save(out / "images" / f"{stem}.jpg", quality=95)
        (out / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")
        exif = extract_exif(rp, exiftool)
        dark16 = float((((raw_bin >> 8) < 16).mean()))
        meta_rows.append({
            "stem": stem, "w": w, "h": h,
            "light": "daylight", "weather": "clear",
            "iso": exif["iso"], "exposure_s": exif["exposure_s"],
            "f_number": exif["f_number"],
            "black_level": int(np.median(smeta["black_level_per_channel"])),
            "white_level": smeta["white_level"], "bayer": "RGGB",
            "dark16": round(dark16, 5),
            "illum_label": 0,  # PASCALRAW is 100% daylight, by dataset construction
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
        "source_ann_dir": str(ann_dir), "raw_dir": str(raw_dir),
        "dataset": "PASCALRAW (Omid-Zohoor/Ta/Murmann, Stanford Digital Repository)",
        "scale": "shift8 (round(linear*255)<<8); per-file black/white/bayer "
                 "from rawpy; RGGB phase-aligned",
        "light": "daylight (100%, by dataset construction -- false-trigger "
                 "ground truth complement to SonyNOD/AODRaw low-light coverage)",
        "n_xml_total": len(xml_files), "n_converted": n_ok,
        "n_skipped": n_skip, "n_no_gt": n_noanno,
        "exif": "exiftool best-effort (iso/exposure/f_number may be null)",
    }, indent=2))
    print(f"converted={n_ok} skipped={n_skip} no_gt={n_noanno} "
          f"total={len(xml_files)}")


# ----------------------------------------------------------------- selftest --
def _selftest() -> int:
    """Pure-logic paths only (VOC XML parse + label conversion + raw-file
    matching); RGGB align / shift8 / EXIF are exercised (and proven against
    a real .ARW) in aodraw_adapter.py's own selftest -- imported here, not
    re-tested, to avoid duplicate logic. The only path this adapter adds
    that AODRaw's selftest doesn't cover is VOC XML parsing + the .NEF file
    matcher, both real-file-free."""
    import tempfile

    voc_xml = """<annotation>
  <filename>test001.NEF</filename>
  <size><width>200</width><height>100</height><depth>3</depth></size>
  <object><name>person</name>
    <bndbox><xmin>10</xmin><ymin>20</ymin><xmax>50</xmax><ymax>80</ymax></bndbox>
  </object>
  <object><name>car</name>
    <bndbox><xmin>100</xmin><ymin>10</ymin><xmax>180</xmax><ymax>60</ymax></bndbox>
  </object>
  <object><name>traffic_cone</name>
    <bndbox><xmin>0</xmin><ymin>0</ymin><xmax>5</xmax><ymax>5</ymax></bndbox>
  </object>
</annotation>"""
    with tempfile.TemporaryDirectory() as td:
        xp = Path(td) / "test001.xml"
        xp.write_text(voc_xml)
        w, h, objs = parse_voc_xml(xp)
        assert (w, h) == (200, 100), (w, h)
        assert len(objs) == 3, objs
        print(f"[ok] parse_voc_xml: {len(objs)} objects, size {w}x{h}")

        lines = voc_to_yolo(objs, w, h)
        # person -> COCO80_ID["person"]=0, car -> 2; traffic_cone unmapped, dropped.
        assert len(lines) == 2, lines
        assert lines[0].startswith("0 "), lines
        assert lines[1].startswith("2 "), lines
        cx, cy, nw, nh = (float(x) for x in lines[0].split()[1:])
        assert abs(cx - 0.15) < 1e-6 and abs(cy - 0.5) < 1e-6, lines[0]
        assert abs(nw - 0.20) < 1e-6 and abs(nh - 0.60) < 1e-6, lines[0]
        print(f"[ok] voc_to_yolo: {lines} (traffic_cone correctly dropped)")

        # (3) raw-file matcher: only the correctly-extensioned sibling matches.
        (Path(td) / "test001.NEF").write_bytes(b"\x00")
        (Path(td) / "test002.nef").write_bytes(b"\x00")
        assert find_raw_file(Path(td), "test001") == Path(td) / "test001.NEF"
        assert find_raw_file(Path(td), "test002") == Path(td) / "test002.nef"
        assert find_raw_file(Path(td), "test003") is None
        print("[ok] find_raw_file: matches .NEF/.nef, None when absent")

        # (4) alias table: pedestrian -> person.
        assert voc_to_yolo([("pedestrian", 0, 0, 10, 10)], 100, 100) == \
            voc_to_yolo([("person", 0, 0, 10, 10)], 100, 100)
        print("[ok] NAME_ALIASES: pedestrian -> person")

    print("\nselftest: ALL PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ann-dir", type=Path, help="dir of PASCAL VOC-style .xml annotations")
    ap.add_argument("--raw-dir", type=Path, help="dir with the referenced .NEF files")
    ap.add_argument("--out", type=Path, help="output dataset dir")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--exiftool", default=None, help="path to exiftool binary")
    ap.add_argument("--selftest", action="store_true",
                    help="run pure-logic self-tests (no dataset needed)")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if not (args.ann_dir and args.raw_dir and args.out):
        ap.error("--ann-dir, --raw-dir, --out required (or use --selftest)")
    ingest(args.ann_dir, args.raw_dir, args.out, args.limit, args.exiftool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
