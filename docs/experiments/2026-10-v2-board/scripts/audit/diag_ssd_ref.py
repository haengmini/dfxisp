"""Diagnostic (no scoring): raw head outputs of the SAME 4 test PNGs through (a) FP32 new s0, (b) FP32 deployed(old) SSD, (c) host NNDCT INT8 sim of new s0. Saved as npz for comparison with board DPU raw outputs.
mode 'fp32' runs in the GPU venv; mode 'sim' runs in the vitis-ai container (writes /work/diag_sim.npz). Inputs = RD.preprocess(png,320,'pm1')."""
import sys, json
from pathlib import Path
import numpy as np, torch
from PIL import Image
mode = sys.argv[1]
Q = Path("/home/mini/dfxisp_eval_20261007/v2_quant") if mode == "fp32" else Path("/work")
man = json.loads((Q / "test_rgb/manifest.json").read_text())
pick = [("night_lowlight", lambda r: r["split"] == "night" and r["arm"] == "lowlight"), ("night_normal", lambda r: r["split"] == "night" and r["arm"] == "normal"),
        ("day_normal", lambda r: r["split"] == "day" and r["arm"] == "normal"), ("day_lowlight", lambda r: r["split"] == "day" and r["arm"] == "lowlight")]
files = [(n, next(r for r in man if f(r))) for n, f in pick]
sys.path.insert(0, "/work/app" if mode == "sim" else "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app")
import run_detector as RD
RD._have_cv2 = lambda: False
X = np.stack([RD.preprocess(np.asarray(Image.open(Q / "test_rgb" / r["file"]).convert("RGB")), 320, "pm1").transpose(2, 0, 1) for _, r in files]).astype(np.float32)
if mode == "fp32":
    sys.path.insert(0, "/home/mini/dfxisp_eval_20261007"); import train_ssd_v2 as T
    out = {"X": X, "names": np.array([n for n, _ in files]), "keys": np.array([r["key"] + ":" + r["arm"] for _, r in files])}
    for tag, sd in (("new_s0", torch.load(Q / "SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]), ("old", torch.load(T.CK, map_location="cpu", weights_only=False)["model_state_dict"])):
        m = T.build(); m.load_state_dict(sd); m.eval()
        with torch.no_grad(): o = m.head(list(m.backbone(torch.from_numpy(X)).values()))
        out[f"fp32_{tag}_reg"] = o["bbox_regression"].numpy(); out[f"fp32_{tag}_cls"] = o["cls_logits"].numpy()
    np.savez(Q / "diag_fp32.npz", **out); print("FP32_DIAG_DONE")
else:
    sys.argv = ["x", "test", "SSD_A_full_s0"]
    src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]
    sd = torch.load("/work/SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Raw(sd).eval()
    from pytorch_nndct.apis import torch_quantizer
    q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir="/work/quant_SSD_A_full_s0", device=torch.device("cpu")); qm = q.quant_model.eval()
    reg, cls = [], []
    for i in range(len(X)):
        with torch.no_grad(): r_, c_ = qm(torch.from_numpy(X[i:i + 1]))
        reg.append(r_.numpy()[0]); cls.append(c_.numpy()[0])
    np.savez("/work/diag_sim.npz", sim_reg=np.stack(reg), sim_cls=np.stack(cls)); print("SIM_DIAG_DONE")
