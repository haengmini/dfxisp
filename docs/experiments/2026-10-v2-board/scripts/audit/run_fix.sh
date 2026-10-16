#!/bin/bash
# fix candidates: K in args. For each K: edit quant_info, dev-eval + export, compile, golden int for diag 0/2. Stops on first failure.
set -u
cd /home/mini/dfxisp_eval_20261007/v2_quant
D() { docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=6 -v $PWD:/work -v /home/mini/dfxisp_eval_20261007/v2_data:/work/v2_data:ro -v /home/mini/dfxisp_eval_20261007/common_dpu_pilot/compiled/arch.json:/arch.json:ro --entrypoint /bin/bash xilinx/vitis-ai-pytorch-cpu:latest -lc "source /opt/vitis_ai/conda/etc/profile.d/conda.sh; conda activate vitis-ai-pytorch; cd /work && PYTHONPATH=/work/vendor $1"; }
for K in "$@"; do
  rm -rf quant_fix_$K quant_fix_${K}_dc0 quant_fix_${K}_dc2 compiled_fix_$K; mkdir -p compiled_fix_$K
  D "python quant_ssd_fix.py $K devexport" > fix_${K}_dev.log 2>&1; grep -q EXPORT_DONE fix_${K}_dev.log || { echo "EXPORT_FAILED $K"; tail -5 fix_${K}_dev.log; exit 1; }
  grep -E "^edited|^dev_" fix_${K}_dev.log
  X=$(ls quant_fix_$K/*_int.xmodel | head -1)
  D "vai_c_xir -x $X -a /arch.json -o compiled_fix_$K -n fix_$K" > fix_${K}_compile.log 2>&1; [ -f compiled_fix_$K/fix_$K.xmodel ] || { echo "COMPILE_FAILED $K"; exit 2; }
  for I in 0 2; do D "python quant_ssd_fix.py $K dc $I" > fix_${K}_dc$I.log 2>&1; grep -q DC_DONE fix_${K}_dc$I.log || { echo "DC_FAILED $K $I"; exit 3; }; done
  echo "FIX_DONE $K"
done
echo FIX_COMPLETE
