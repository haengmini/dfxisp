#!/bin/bash
# prefix stages: calib -> export -> compile -> golden int (deploy_check) for diag images 0 and 2. Stops on first failure.
set -u
cd /home/mini/dfxisp_eval_20261007/v2_quant
D() { docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=6 -v $PWD:/work -v /home/mini/dfxisp_eval_20261007/v2_data:/work/v2_data:ro -v /home/mini/dfxisp_eval_20261007/common_dpu_pilot/compiled/arch.json:/arch.json:ro --entrypoint /bin/bash xilinx/vitis-ai-pytorch-cpu:latest -lc "source /opt/vitis_ai/conda/etc/profile.d/conda.sh; conda activate vitis-ai-pytorch; cd /work && PYTHONPATH=/work/vendor $1"; }
for S in "$@"; do
  rm -rf quant_pre_$S quant_pre_${S}_dc0 quant_pre_${S}_dc2 compiled_pre_$S; mkdir -p compiled_pre_$S
  D "python quant_ssd_prefix.py calib $S" > pre_${S}_calib.log 2>&1; grep -q CALIB_DONE pre_${S}_calib.log || { echo "CALIB_FAILED $S"; exit 1; }
  D "python quant_ssd_prefix.py export $S" > pre_${S}_export.log 2>&1; grep -q EXPORT_DONE pre_${S}_export.log || { echo "EXPORT_FAILED $S"; exit 2; }
  X=$(ls quant_pre_$S/*_int.xmodel | head -1)
  D "vai_c_xir -x $X -a /arch.json -o compiled_pre_$S -n pre_$S" > pre_${S}_compile.log 2>&1; [ -f compiled_pre_$S/pre_$S.xmodel ] || { echo "COMPILE_FAILED $S"; exit 3; }
  for I in 0 2; do D "python quant_ssd_prefix.py dc $S $I" > pre_${S}_dc$I.log 2>&1; grep -q DC_DONE pre_${S}_dc$I.log || { echo "DC_FAILED $S $I"; exit 4; }; done
  echo "STAGE_DONE $S"
done
echo PREFIX_COMPLETE
