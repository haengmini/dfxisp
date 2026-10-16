"""Which quantizer-golden intermediate tensors does the board reproduce bit-exactly? The DPU runner only exposes the 2 output tensors, so instead we compare the golden (NNDCT deploy_check) head tensors
by level and report, per detection-head level, which backbone stage feeds it. Output level split of the 3234 anchors: 20x20 (2400), 10x10 (600), 5x5 (150), 3x3 (54), 2x2 (24), 1x1 (6).
Also quantifies the effect on mAP of reverting the diverging levels to golden values: score the golden-int output (what a bit-exact board WOULD output) vs the board output on the same image set is not possible for 400 images
(golden needs the container per image) -- so here: per-level error statistics for ALL 4 diag images with the golden recomputed per image in the container (diag_deploy_check.py for i=0..3)."""
import numpy as np, json, sys
from pathlib import Path
Q = Path("/home/mini/dfxisp_eval_20261007/v2_quant"); b = np.load(Q / "diag_int.npz")
sizes = [2400, 600, 150, 54, 24, 6]; names = ["20x20", "10x10", "5x5", "3x3", "2x2", "1x1"]
def rd(i, key):
    R = Q / f"quant_dc_{i}/deploy_check_data_int/Raw"
    nm = {"cls": "Raw__Raw_SSDLiteHead_head__SSDLiteClassificationHead_classification_head__ret_fix.bin", "reg": "Raw__Raw_SSDLiteHead_head__SSDLiteRegressionHead_regression_head__ret_387_fix.bin"}[key]
    return np.fromfile(R / nm, dtype=np.int8).reshape(3234, 4)
rows = []
for i in range(4):
    if not (Q / f"quant_dc_{i}").exists(): continue
    inp_ok = bool(np.array_equal(np.fromfile(Q / f"quant_dc_{i}/deploy_check_data_int/Raw/Raw__input_0_fix.bin", dtype=np.int8), b[f"in_{i}"].astype(np.int8).ravel()))
    for key in ("cls", "reg"):
        ref = rd(i, key).astype(int); bo = b[f"{key}_{i}"].astype(int); o = 0
        for nm, s in zip(names, sizes):
            d = np.abs(ref[o:o + s] - bo[o:o + s]); rows.append((i, key, nm, inp_ok, float((d == 0).mean()), float(d.mean()), int(d.max()))); o += s
print("img key level input_equal exact_frac mean|d| max|d|")
for r in rows: print(r[0], r[1], r[2], r[3], "%.3f %.2f %d" % r[4:])
