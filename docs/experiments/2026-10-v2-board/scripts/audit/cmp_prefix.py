"""Compare board int8 output of each prefix stage with the NNDCT golden integer (deploy_check) for diag images 0 and 2. Golden layout from deploy_check is NCHW? -> try both and report which matches.
usage: python cmp_prefix.py <stage> ..."""
import sys
from pathlib import Path
import numpy as np
Q = Path("/home/mini/dfxisp_eval_20261007/v2_quant")
b = np.load(next(Q.glob("diag_prefix_*.npz"))) if False else None
import glob
files = sorted(glob.glob(str(Q / "diag_prefix_*.npz"))); B = {}
for f in files:
    z = np.load(f)
    for k in z.files: B[k] = z[k]
for st in sys.argv[1:]:
    for i in (0, 2):
        R = Q / f"quant_pre_{st}_dc{i}/deploy_check_data_int"
        cands = [p for p in R.rglob("*_fix.bin") if "weight" not in p.name and "bias" not in p.name and "input_0" not in p.name]
        board = B[f"{st}_{i}"].astype(int)       # (H, W, C) NHWC from DPU
        inq = B[f"{st}_in{i}"].astype(np.int8).ravel(); inref = np.fromfile(R / "Prefix/Prefix__input_0_fix.bin", dtype=np.int8) if (R / "Prefix/Prefix__input_0_fix.bin").exists() else None
        best = None
        for p in cands:
            g = np.fromfile(p, dtype=np.int8)
            if g.size != board.size: continue
            d = np.abs(g.astype(int).reshape(board.shape) - board)
            if best is None or d.mean() < best[1]: best = (p.name[-60:], float(d.mean()), float((d == 0).mean()), int(d.max()))
        print(f"{st:4s} img{i} input_equal={None if inref is None else bool(np.array_equal(inq, inref))} golden={best[0] if best else None} exact={best[2]:.4f} mean|d|={best[1]:.3f} max|d|={best[3]}" if best else f"{st} img{i}: no golden of matching size ({board.size}) among {len(cands)}")
