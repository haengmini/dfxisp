#!/bin/bash
# Batch-convert a directory of camera RAWs to NormalISP 12-bit RGGB Bayer .bin files.
#   ./batch_raw_to_bayer.sh <raw_dir> <out_dir> [max_w] [max_h] [jobs]
# Wraps tools/raw_to_bayer_bin.py (which appends the real _WxH to each filename).
set -u
RAW_DIR=$1; OUT_DIR=$2; MAXW=${3:-640}; MAXH=${4:-480}; JOBS=${5:-8}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT_DIR"
ls "$RAW_DIR" | grep -iE '\.(nef|arw|cr2|dng)$' | \
  xargs -P "$JOBS" -I{} sh -c \
  'f="$1"; b="${f%.*}"; python3 "$2/raw_to_bayer_bin.py" "$3/$f" "$4/${b}_raw12.bin" --max-width "$5" --max-height "$6" >/dev/null 2>&1 || echo "FAIL $f"' \
  _ {} "$HERE" "$RAW_DIR" "$OUT_DIR" "$MAXW" "$MAXH"
echo "$OUT_DIR: $(ls "$OUT_DIR" | wc -l) files, $(du -sh "$OUT_DIR" | cut -f1)"
