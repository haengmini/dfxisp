"""PREFIX variant: the deployed s0 backbone truncated after a given stage, with that stage's tensor as the ONLY network output (so the compiler must keep it as a DPU output).
Same weights, same calibration (the 128 deployed calib files), same quantizer settings. Used to find the first stage where board DPU != NNDCT golden integer.
stages: f0 (features[0] end, 20x20x672) | d0 (features[1][0][0]) | se0 (features[1][0][1]) | p0 (features[1][0][2]) | b1 | b2 | c3 (10x10x480) | e0 | e1 | e2 | e3
modes (container): calib <stage> | export <stage> | dc <stage> <i>"""
import json, shutil, sys
from pathlib import Path
import numpy as np, torch
from torch import nn
mode, stage = sys.argv[1], sys.argv[2]; di = int(sys.argv[3]) if len(sys.argv) > 3 else 0
sys.argv = ["x", "test", "SSD_A_full_s0"]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); load = ns["load"]
from torchvision.models.detection import ssdlite320_mobilenet_v3_large
class Prefix(nn.Module):
    def __init__(self, sd, stage):
        super().__init__()
        m = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=4); m.load_state_dict(sd); self.bb = m.backbone; self.stage = stage
    def forward(self, x):
        bb, s = self.bb, self.stage; f0 = bb.features[0](x)
        if s == "f0": return f0
        b = bb.features[1]; blk0 = b[0]; d0 = blk0[0](f0)
        if s == "d0": return d0
        se0 = blk0[1](d0)
        if s == "se0": return se0
        p0 = blk0[2](se0)
        if s == "p0": return p0
        blk = b[1].block
        if s == "b1_exp": return blk[0](p0)
        if s == "b1_dw": return blk[1](blk[0](p0))
        if s.startswith("b1_se_"):
            x = blk[1](blk[0](p0)); se = blk[2]; sc = se.avgpool(x)
            if s == "b1_se_pool": return sc
            sc = se.fc1(sc)
            if s == "b1_se_fc1": return sc
            sc = se.activation(sc)
            if s == "b1_se_relu": return sc
            sc = se.fc2(sc)
            if s == "b1_se_fc2": return sc
            sc = se.scale_activation(sc)
            if s == "b1_se_hsig": return sc
            return sc * x
        if s == "b1_se": return blk[2](blk[1](blk[0](p0)))
        if s == "b1_proj": return blk[3](blk[2](blk[1](blk[0](p0))))
        b1 = b[1](p0)
        if s == "b1": return b1
        b2 = b[2](b1)
        if s == "b2": return b2
        c3 = b[3](b2)
        if s == "c3": return c3
        z = c3
        for k, blk in enumerate(bb.extra):
            z = blk(z)
            if s == f"e{k}": return z
        raise ValueError(s)
sd = torch.load("/work/SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Prefix(sd, stage).eval()
OUT = Path(f"/work/quant_pre_{stage}")
from pytorch_nndct.apis import torch_quantizer
if mode == "calib":
    files = [Path(p) for p in json.loads(Path("/work/quant_SSD_A_full_s0/calib_files.json").read_text())]; assert len(files) == 128 and all("/images/train/" in str(p) for p in files)
    q = torch_quantizer("calib", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
    with torch.no_grad():
        for p in files: qm(torch.from_numpy(load(p)))
    q.export_quant_config(); print("CALIB_DONE", stage); sys.exit(0)
X = np.load("/work/diag_fp32.npz")["X"]
if mode == "export":
    q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
    with torch.no_grad(): qm(torch.from_numpy(X[0:1]))
    q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE", stage); sys.exit(0)
if mode == "dc":
    out = Path(f"/work/quant_pre_{stage}_dc{di}")
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(OUT, out)
    for p in list(out.glob("*.xmodel")) + [out / "deploy_check_data_int"]:
        if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
    q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(out), device=torch.device("cpu")); qm = q.quant_model.eval()
    with torch.no_grad(): qm(torch.from_numpy(X[di:di + 1]))
    q.export_xmodel(output_dir=str(out), deploy_check=True); print("DC_DONE", stage, di)
