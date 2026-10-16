#!/bin/bash
# SSD seeds: equiv gate -> calib -> dev-eval+export -> compile -> host INT8 on 400 test PNGs. Stops on first failure.
set -eu
cd /home/mini/dfxisp_eval_20261007/v2_quant
run() { docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=6 -v $PWD:/work -v /home/mini/dfxisp_eval_20261007/v2_data:/work/v2_data:ro -v /home/mini/dfxisp_eval_20261007/hw1368:/hw:ro -v /home/mini/dfxisp_eval_20261007/common_dpu_pilot/compiled/arch.json:/arch.json:ro --entrypoint /bin/bash xilinx/vitis-ai-pytorch-cpu:latest -lc "source /opt/vitis_ai/conda/etc/profile.d/conda.sh; conda activate vitis-ai-pytorch; cd /work && PYTHONPATH=/work/vendor $1"; }
for S in "$@"; do
  T=SSD_A_full_s$S
  run "python quant_ssd_v2.py equiv $T" > qs_${T}_equiv.log 2>&1; grep -q EQUIV_PASS qs_${T}_equiv.log || { echo "EQUIV_FAILED $T"; cat qs_${T}_equiv.log | tail -5; exit 1; }
  run "python quant_ssd_v2.py calib $T" > qs_${T}_calib.log 2>&1; grep -q CALIB_DONE qs_${T}_calib.log || { echo "CALIB_FAILED $T"; exit 2; }
  run "python quant_ssd_v2.py test $T" > qs_${T}_test.log 2>&1; grep -q EXPORT_DONE qs_${T}_test.log || { echo "EXPORT_FAILED $T"; exit 3; }
  mkdir -p compiled_$T
  X=$(ls quant_$T/*_int.xmodel | head -1)
  run "vai_c_xir -x $X -a /arch.json -o compiled_$T -n v2_ssd_$T" > qs_${T}_compile.log 2>&1; [ -f compiled_$T/v2_ssd_$T.xmodel ] || { echo "COMPILE_FAILED $T"; exit 4; }
  run "python host_int8_ssd.py $T" > qs_${T}_host.log 2>&1; grep -q HOST_INT8_DONE qs_${T}_host.log || { echo "HOST_FAILED $T"; exit 5; }
  echo "SEED_DONE $T"
done
echo SSD_QUANT_COMPLETE
