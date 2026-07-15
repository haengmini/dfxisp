#!/usr/bin/env python3
"""materialize_split.py -- turn a build_matched_splits.py manifest CSV
(lod_split/pascal_split/shuffle_split_2026-07-15.csv) into a flat
raw_bin/images/labels directory that eval_map_isp.py's --root can consume
directly, unmodified (it auto-discovers stems via raw_bin/*.bin glob and
has no concept of "which subset" a stem came from).

Default mode is symlink (cheap, no duplicate storage -- use for local runs
where source datasets are already on this machine). Use --mode copy to
produce a self-contained directory (e.g. before tar --dereference-free
packaging for transfer to a machine that won't have the source datasets).

shuffle_split mixes stems from two different source dirs -- resolved
per-row via the manifest's own `source` column (lod/pascal), not a
hardcoded path, so this same script handles all three manifests. Default
sources are the full original datasets (data/sonynod_test,
data/pascalraw_test); override with --source-dir for e.g. rebuilding
shuffle_split from already-unpacked lod_split/pascal_split directories on
a machine that doesn't have the full originals (see data/_transfer/README.md).

Usage (run from isppipeline/hls/tools/):
  python3 materialize_split.py --manifest ../results/pascal_split_2026-07-15.csv \\
      --out ../../../data/_transfer/pascal_split [--mode copy]

  # rebuild shuffle_split from unpacked split dirs (no full originals needed):
  python3 materialize_split.py --manifest shuffle_split_2026-07-15.csv \\
      --out data/shuffle_split \\
      --source-dir lod=data/lod_split --source-dir pascal=data/pascal_split
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

SOURCE_DIRS = {
    "lod": Path(__file__).resolve().parents[3] / "data" / "sonynod_test",
    "pascal": Path(__file__).resolve().parents[3] / "data" / "pascalraw_test",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mode", choices=("symlink", "copy"), default="symlink")
    ap.add_argument("--source-dir", action="append", default=[],
                     metavar="NAME=PATH",
                     help="override SOURCE_DIRS[NAME]=PATH, repeatable")
    args = ap.parse_args()

    source_dirs = dict(SOURCE_DIRS)
    for spec in args.source_dir:
        name, _, path = spec.partition("=")
        source_dirs[name] = Path(path)

    for sub in ("raw_bin", "images", "labels"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    n = 0
    missing = 0
    with args.manifest.open() as f:
        for row in csv.DictReader(f):
            src_root = source_dirs[row["source"]]
            stem = row["stem"]
            for sub, ext in (("raw_bin", ".bin"), ("images", ".jpg"), ("labels", ".txt")):
                s = (src_root / sub / f"{stem}{ext}").resolve()
                d = args.out / sub / f"{stem}{ext}"
                if not s.exists():
                    missing += 1
                    continue
                if d.exists() or d.is_symlink():
                    d.unlink()
                if args.mode == "symlink":
                    d.symlink_to(s)
                else:
                    shutil.copy2(s, d)
            n += 1
    print(f"materialized {n} frames into {args.out} (mode={args.mode}, {missing} missing files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
