#!/bin/bash
# Seeds 1,2: calib -> dev-eval+export -> compile -> host-INT8 on 400 test PNGs. Stops on first failure.
set -eu
cd /home/mini/dfxisp_eval_20261007/v2_quant
run() { docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=6 -v $PWD:/work -v /home/mini/dfxisp_eval_20261007/v2_data:/work/v2_data:ro -v /home/mini/dfxisp_eval_20261007/hw1368:/hw:ro -v /home/mini/dfxisp_eval_20261007/common_dpu_pilot/compiled/arch.json:/arch.json:ro --entrypoint /bin/bash xilinx/vitis-ai-pytorch-cpu:latest -lc "source /opt/vitis_ai/conda/etc/profile.d/conda.sh; conda activate vitis-ai-pytorch; cd /work && PYTHONPATH=/work/vendor $1"; }
for T in "$@"; do
  run "python quant_v2.py calib $T" > q_${T}_calib.log 2>&1; grep -q CALIB_DONE q_${T}_calib.log || { echo "CALIB_FAILED $T"; exit 1; }
  run "python quant_v2.py test $T" > q_${T}_test.log 2>&1; grep -q EXPORT_DONE q_${T}_test.log || { echo "EXPORT_FAILED $T"; exit 2; }
  mkdir -p compiled_$T
  run "vai_c_xir -x quant_$T/Raw_int.xmodel -a /arch.json -o compiled_$T -n v2_yolo_$T" > q_${T}_compile.log 2>&1; [ -f compiled_$T/v2_yolo_$T.xmodel ] || { echo "COMPILE_FAILED $T"; exit 3; }
  sed -e "s#A_full_s0#$T#g" host_int8_test.py > host_int8_test_$T.py
  sed -i -e "s#/work/host_int8_test_dets.json#/work/host_int8_test_dets_$T.json#" -e "s#/work/host_int8_test_scores.json#/work/host_int8_test_scores_$T.json#" -e 's#r\["label"\]\.replace("/home/mini/dfxisp_eval_20261007", "/hw")#r["label"].replace("/home/mini/dfxisp_eval_20261007/hw1368", "/hw")#' host_int8_test_$T.py
  run "python host_int8_test_$T.py" > q_${T}_host.log 2>&1; grep -q HOST_INT8_DONE q_${T}_host.log || { echo "HOST_FAILED $T"; exit 4; }
  echo "SEED_DONE $T"
done
echo QUANT_QUEUE_COMPLETE
