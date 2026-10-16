#!/bin/bash
# v2 training queue: sequential (single 8GB GPU). Stops immediately on any failure. Evaluates LAST weights only (no test-based checkpoint selection).
set -eu
cd /home/mini/dfxisp_eval_20261007
PY=/home/mini/dfxisp_eval_20261007/sep_20261012/venv_gpu/bin/python
for SEED in "$@"; do
  for ARM in A_full B_freeze10; do
    LOG=v2_runs_${ARM}_s${SEED}.log
    if [ -f v2_runs/${ARM}_s${SEED}/weights/last.pt ] && grep -q TRAIN_DONE "$LOG" 2>/dev/null; then echo "skip $ARM $SEED"; continue; fi
    $PY -u train_v2.py $ARM $SEED 30 > "$LOG" 2>&1
    grep -q TRAIN_DONE "$LOG" || { echo "TRAIN_FAILED $ARM $SEED"; exit 1; }
    $PY -u eval_v2.py ${ARM}_s${SEED} v2_runs/${ARM}_s${SEED}/weights/last.pt both > v2_eval_${ARM}_s${SEED}.log 2>&1
    grep -q EVAL_DONE v2_eval_${ARM}_s${SEED}.log || { echo "EVAL_FAILED $ARM $SEED"; exit 2; }
    echo "DONE $ARM $SEED"
  done
done
echo QUEUE_COMPLETE
