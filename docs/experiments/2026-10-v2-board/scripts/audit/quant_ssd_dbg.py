"""DEBUG variant of the v2 SSD s0 model that EXPOSES intermediate tensors as DPU outputs, to find the first layer where the board DPU stops matching the NNDCT golden integer reference.
Not a deployment model. Same weights, same calibration files (calib_files.json of the deployed s0 quantization), same input contract.
Outputs: (reg, cls, f0, d0, se0, p0, b1, b2, c3, e0, e1, e2, e3):
  f0 = features[0] out (20x20x672, feeds head level 0)      d0 = features[1][0][0] (dw stride-2 conv+BN+hswish)  se0 = features[1][0][1] (SqueezeExcitation)  p0 = features[1][0][2] (project)
  b1/b2 = features[1][1], [2] (InvertedResidual)             c3 = features[1][3] (last 1x1 conv, 10x10x480 = head level 1 input)
  e0..e3 = extra blocks (5x5, 3x3, 2x2, 1x1)
modes (container): struct | equiv | calib | export | dc <i>
  equiv : fp32 (reg,cls) of this debug model equals the deployed Raw model (sanity)
  export: quantized (test mode) one forward then export_xmodel (no deploy_check)
  dc i  : quantized forward on diag image i then export with deploy_check=True into /work/quant_dbg_dc_<i>"""
import json, random, shutil, sys
from pathlib import Path
import numpy as np, torch
from torch import nn
mode = sys.argv[1]; arg = sys.argv[2] if len(sys.argv) > 2 else None
sys.argv = ["x", "test", "SSD_A_full_s0"]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]; load = ns["load"]
from torchvision.models.detection import ssdlite320_mobilenet_v3_large
class RawDbg(nn.Module):
    def __init__(self, sd):
        super().__init__()
        m = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=4); m.load_state_dict(sd); self.backbone = m.backbone; self.head = m.head
    def forward(self, x):
        bb = self.backbone; f0 = bb.features[0](x); b = bb.features[1]
        y = f0; blk0 = b[0]; d0 = blk0[0](y); se0 = blk0[1](d0); p0 = blk0[2](se0)
        b1 = b[1](p0); b2 = b[2](b1); c3 = b[3](b2)
        z = c3; e = []
        for blk in bb.extra: z = blk(z); e.append(z)
        o = self.head([f0, c3] + e)
        return (o["bbox_regression"], o["cls_logits"], f0, d0, se0, p0, b1, b2, c3) + tuple(e)
NAMES = ["reg", "cls", "f0", "d0", "se0", "p0", "b1", "b2", "c3", "e0", "e1", "e2", "e3"]
sd = torch.load("/work/SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = RawDbg(sd).eval()
OUT = Path("/work/quant_dbg")
if mode == "struct":
    x = torch.zeros(1, 3, 320, 320)
    with torch.no_grad(): o = model(x)
    print([(n, tuple(t.shape)) for n, t in zip(NAMES, o)]); sys.exit(0)
if mode == "equiv":
    ref = Raw(sd).eval(); X = np.load("/work/diag_fp32.npz")["X"]; worst = 0.0
    for i in range(len(X)):
        x = torch.from_numpy(X[i:i + 1])
        with torch.no_grad(): a = model(x)[:2]; b = ref(x)
        worst = max(worst, float((a[0] - b[0]).abs().max()), float((a[1] - b[1]).abs().max()))
    print("debug vs deployed Raw fp32 max abs diff:", worst); print("EQUIV_PASS" if worst == 0.0 else "EQUIV_FAIL"); sys.exit(0 if worst == 0.0 else 1)
from pytorch_nndct.apis import torch_quantizer
if mode == "calib":
    files = [Path(p) for p in json.loads(Path("/work/quant_SSD_A_full_s0/calib_files.json").read_text())]; assert len(files) == 128 and all("/images/train/" in str(p) for p in files)
    q = torch_quantizer("calib", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
    with torch.no_grad():
        for p in files: qm(torch.from_numpy(load(p)))
    q.export_quant_config(); print("CALIB_DONE dbg"); sys.exit(0)
if mode == "export":
    q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
    X = np.load("/work/diag_fp32.npz")["X"]
    with torch.no_grad(): qm(torch.from_numpy(X[0:1]))
    q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE dbg"); sys.exit(0)
if mode == "dc":
    i = int(arg); out = Path(f"/work/quant_dbg_dc_{i}")
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(OUT, out)
    for p in list(out.glob("*.xmodel")) + [out / "deploy_check_data_int"]:
        if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
    q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(out), device=torch.device("cpu")); qm = q.quant_model.eval()
    X = np.load("/work/diag_fp32.npz")["X"]
    with torch.no_grad(): qm(torch.from_numpy(X[i:i + 1]))
    q.export_xmodel(output_dir=str(out), deploy_check=True); print("DC_DONE", i); sys.exit(0)
