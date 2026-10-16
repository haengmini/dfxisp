#!/bin/bash
# usage: run_gen.sh <tag>:<K> ...   (K=0 control without fix, K=8 fix). calib once per tag.
set -u
cd /home/mini/dfxisp_eval_20261007/v2_quant
D() { docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=6 -v $PWD:/work -v /home/mini/dfxisp_eval_20261007/v2_data:/work/v2_data:ro -v /home/mini/dfxisp_eval_20261007/hw1368:/hw:ro -v /home/mini/dfxisp_eval_20261007/common_dpu_pilot/compiled/arch.json:/arch.json:ro --entrypoint /bin/bash xilinx/vitis-ai-pytorch-cpu:latest -lc "source /opt/vitis_ai/conda/etc/profile.d/conda.sh; conda activate vitis-ai-pytorch; cd /work && PYTHONPATH=/work/vendor $1"; }
for SPEC in "$@"; do
  T=${SPEC%%:*}; K=${SPEC#*:}
  if [ ! -d quantg_${T}_calib ]; then D "python quant_ssd_gen.py calib $T" > g_${T}_calib.log 2>&1; grep -q CALIB_DONE g_${T}_calib.log || { echo "CALIB_FAILED $T"; tail -3 g_${T}_calib.log; exit 1; }; fi
  rm -rf quantg_${T}_k$K compiledg_${T}_k$K; mkdir -p compiledg_${T}_k$K
  D "python quant_ssd_gen.py fixexport $T $K" > g_${T}_k${K}_export.log 2>&1; grep -q EXPORT_DONE g_${T}_k${K}_export.log || { echo "EXPORT_FAILED $T $K"; tail -3 g_${T}_k${K}_export.log; exit 2; }
  grep -E "^edited|^UNCHANGED|^dev_" g_${T}_k${K}_export.log
  X=$(ls quantg_${T}_k$K/*_int.xmodel | head -1)
  D "vai_c_xir -x $X -a /arch.json -o compiledg_${T}_k$K -n g_${T}_k$K" > g_${T}_k${K}_compile.log 2>&1; [ -f compiledg_${T}_k$K/g_${T}_k$K.xmodel ] || { echo "COMPILE_FAILED $T $K"; exit 3; }
  D "python quant_ssd_gen.py host $T $K" > g_${T}_k${K}_host.log 2>&1; grep -q HOST_DONE g_${T}_k${K}_host.log || { echo "HOST_FAILED $T $K"; exit 4; }
  echo "GEN_DONE $T $K"
done
echo GEN_COMPLETE
