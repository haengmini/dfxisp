"""Exact-name comparison of board prefix output vs golden: the golden file is the one whose name equals the DPU output tensor name of the compiled prefix xmodel (not 'closest by size').
Reads the board output tensor name from compiled_pre_<stage>/pre_<stage>.xmodel via xir (container) -> names.json, then compares here.
usage: cmp_prefix_exact.py <stage> ..."""
import json, sys, glob
from pathlib import Path
import numpy as np
Q = Path("/home/mini/dfxisp_eval_20261007/v2_quant"); names = json.loads((Q / "prefix_out_names.json").read_text())
B = {}
for f in sorted(glob.glob(str(Q / "diag_prefix_*.npz"))):
    z = np.load(f)
    for k in z.files: B[k] = z[k]
for st in sys.argv[1:]:
    tname = names[st]
    for i in (0, 2):
        R = Q / f"quant_pre_{st}_dc{i}/deploy_check_data_int/Prefix"
        hit = [p for p in R.glob("*_fix.bin") if p.name.endswith(tname.split("Prefix__")[-1]) or tname in p.name or p.name == tname + ".bin"]
        assert len(hit) == 1, (st, tname, [h.name for h in hit])
        g = np.fromfile(hit[0], dtype=np.int8); board = B[f"{st}_{i}"].astype(int); assert g.size == board.size
        d = np.abs(g.astype(int).reshape(board.shape) - board)
        print(f"{st:4s} img{i} golden={hit[0].name[-52:]} exact={(d==0).mean():.4f} mean|d|={d.mean():.3f} max|d|={int(d.max())}")
