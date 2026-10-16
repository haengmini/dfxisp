#!/bin/bash
# SSD A_full seeds: train 30 epochs (last only) -> eval dev+test. Stops on first failure. Usage: queue_ssd.sh 0 1 2
set -eu
cd /home/mini/dfxisp_eval_20261007
PY=sep_20261012/venv_gpu/bin/python
for S in "$@"; do
  $PY -u train_ssd_v2.py $S 30 0.002 > v2_runs_SSD_train_s$S.log 2>&1; grep -q "TRAIN_DONE SSD $S" v2_runs_SSD_train_s$S.log || { echo "TRAIN_FAILED $S"; exit 1; }
  $PY -u eval_ssd_v2.py SSD_A_full_s$S v2_runs/SSD_A_full_s$S/last.pt both > v2_runs_SSD_eval_s$S.log 2>&1; grep -q "EVAL_DONE" v2_runs_SSD_eval_s$S.log || { echo "EVAL_FAILED $S"; exit 2; }
  echo "DONE SSD $S"
done
echo SSD_QUEUE_COMPLETE
