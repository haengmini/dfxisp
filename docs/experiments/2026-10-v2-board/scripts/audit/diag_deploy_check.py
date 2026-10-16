"""Golden integer reference for the compiled SSD: re-export the xmodel with deploy_check=True after ONE forward of a diagnostic image, so NNDCT dumps its integer (fixed-point) tensors
(deploy_check_data_int). Compare with the board DPU int8 outputs for the same image.
usage (container): python diag_deploy_check.py <image_index_in_diag_inputs>   -> /work/quant_dc_<i>/ ; needs /work/quant_SSD_A_full_s0 (calibrated) and /work/diag_fp32.npz (X)"""
import sys, shutil
from pathlib import Path
import numpy as np, torch
i = int(sys.argv[1]); sys.argv = ["x", "test", "SSD_A_full_s0"]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]
out = Path(f"/work/quant_dc_{i}")
if out.exists(): shutil.rmtree(out)
shutil.copytree("/work/quant_SSD_A_full_s0", out)
for p in list(out.glob("*.xmodel")) + [out / "deploy_check_data_int"]:
    if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
sd = torch.load("/work/SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Raw(sd).eval()
from pytorch_nndct.apis import torch_quantizer
q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(out), device=torch.device("cpu")); qm = q.quant_model.eval()
X = np.load("/work/diag_fp32.npz")["X"]
with torch.no_grad(): r, c = qm(torch.from_numpy(X[i:i + 1]))
np.savez(out / "sim_float_out.npz", reg=r.numpy(), cls=c.numpy())
q.export_xmodel(output_dir=str(out), deploy_check=True); print("DC_DONE", i)
