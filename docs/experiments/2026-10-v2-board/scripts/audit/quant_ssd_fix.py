"""Candidate fix 1: cap the fixed-point position of the two SE fc2 outputs that feed hard-sigmoid with hsigmoid_in=11.
Edits a COPY of the calibrated quant_info.json (quant_SSD_A_full_s0 -> quant_fix_<K>), then runs test-mode forward + export (+ deploy_check on diag images) so the result can be compared with the board.
The calibration data / weights are unchanged. Only the nodes that the board gets wrong are touched.
usage (container): python quant_ssd_fix.py <K> <mode>    K = target fix point (e.g. 8, 7) for nndct_conv2d_117 and nndct_conv2d_129;  mode: devexport | dc <i>"""
import json, shutil, sys
from pathlib import Path
import numpy as np, torch
K = int(sys.argv[1]); mode = sys.argv[2]; di = int(sys.argv[3]) if len(sys.argv) > 3 else 0
sys.argv = ["x", "test", "SSD_A_full_s0"]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]
OUT = Path(f"/work/quant_fix_{K}")
if mode == "devexport" and OUT.exists(): shutil.rmtree(OUT)
if not OUT.exists():
    shutil.copytree("/work/quant_SSD_A_full_s0", OUT)
    for p in list(OUT.glob("*.xmodel")) + [OUT / "deploy_check_data_int"]:
        if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
    qi = json.loads((OUT / "quant_info.json").read_text()); before = {n: qi["output"][n] for n in ("Raw::nndct_conv2d_117", "Raw::nndct_conv2d_129")}
    for n in before: qi["output"][n] = [[8, K]]
    (OUT / "quant_info.json").write_text(json.dumps(qi)); print("edited", before, "->", K)
sd = torch.load("/work/SSD_A_full_s0_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Raw(sd).eval()
from pytorch_nndct.apis import torch_quantizer
odir = OUT if mode == "devexport" else Path(f"/work/quant_fix_{K}_dc{di}")
if mode == "dc":
    if odir.exists(): shutil.rmtree(odir)
    shutil.copytree(OUT, odir)
    for p in list(odir.glob("*.xmodel")) + [odir / "deploy_check_data_int"]:
        if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(odir), device=torch.device("cpu")); qm = q.quant_model.eval()
if mode == "devexport":
    import contextlib, io, os, tempfile
    from PIL import Image
    sys.path.insert(0, "/work/vendor"); sys.path.insert(0, "/work/app")
    import run_detector as RD, eval_map as EM
    RD._have_cv2 = lambda: False; ANC = np.load("/work/app/ssdlite_anchors.npy"); D = Path("/work/v2_data")
    def detect(img):
        h, w = img.shape[:2]; x = RD.preprocess(img, 320, "pm1").transpose(2, 0, 1)[None].copy()
        with torch.no_grad(): reg, cls = qm(torch.from_numpy(x))
        d = RD.ssdlite_postprocess({"classification": cls.numpy(), "regression": reg.numpy()}, ANC, 320, 0.001, 0.55)
        return {"width": w, "height": h, "detections": [[float(b[0]*w/320), float(b[1]*h/320), float(b[2]*w/320), float(b[3]*h/320), float(b[4]), int(b[5])] for b in d]}
    res = {}
    for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
        for p, kind in spec:
            td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
            for im in sorted((D / p / "images/val").glob("*.png")):
                data["images"][im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); shutil.copyfile(D / p / "labels/val" / (im.stem + ".txt"), f"{td}/{im.stem}.txt")
            with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate(data, td)
            shutil.rmtree(td); res[f"dev_{sub}_{kind}"] = {"mAP50_95": a, "mAP50": a50, "n": len(data["images"])}; print(f"dev_{sub}_{kind}", "%.4f" % a, flush=True)
    (OUT / "dev_scores_int8.json").write_text(json.dumps(res, indent=1))
    q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE fix", K)
else:
    X = np.load("/work/diag_fp32.npz")["X"]
    with torch.no_grad(): qm(torch.from_numpy(X[di:di + 1]))
    q.export_xmodel(output_dir=str(odir), deploy_check=True); print("DC_DONE fix", K, di)
