"""Host INT8 (NNDCT quant_model, test mode) on the 400 pre-rendered TEST RGB images; dumps detections (board contract) for exact comparison with board DPU replay.
Runs inside vitis-ai-pytorch-cpu container. Reads only /work/test_rgb. Scorer = board eval_map. Never used for calibration or selection."""
import json, sys, io, contextlib, shutil, tempfile, time
from pathlib import Path
import numpy as np, torch
from PIL import Image
sys.argv = ["x", "test", "A_full_s0"]
src = open("/work/quant_v2.py").read(); ns = {}
exec(src[:src.index("def load(p)")], ns)
Raw = ns["Raw"]
sys.path.insert(0, "/work/vendor"); sys.path.insert(0, "/work/app")
import run_detector as RD, eval_map as EM
RD._have_cv2 = lambda: False
sd = torch.load("/work/A_full_s0_state.pt", map_location="cpu")["state_dict"]
model = Raw(sd).eval()
from pytorch_nndct.apis import torch_quantizer
q = torch_quantizer("test", model, (torch.zeros(1, 3, 640, 640),), output_dir="/work/quant_A_full_s0", device=torch.device("cpu"))
qm = q.quant_model.eval()
man = json.loads(Path("/work/test_rgb/manifest.json").read_text())
dets = {"normal": {}, "lowlight": {}}; t0 = time.time()
for i, r in enumerate(man):
    img = np.asarray(Image.open(Path("/work/test_rgb") / r["file"]).convert("RGB")); h, w = img.shape[:2]
    x = torch.from_numpy(RD.preprocess(img, 640, "unit")).permute(2, 0, 1)[None].float()
    with torch.no_grad(): outs = [v.detach().numpy() for v in qm(x)]
    oo = {f"cv{2 + (j % 2)}_{j // 2}": v.transpose(0, 2, 3, 1) for j, v in enumerate(outs)}
    d = RD.yolov8_postprocess(oo, 640, 3, 0.001, 0.45)
    dets[r["arm"]][r["key"]] = {"width": w, "height": h, "detections": [[float(b[0]*w/640), float(b[1]*h/640), float(b[2]*w/640), float(b[3]*h/640), float(b[4]), int(b[5])] for b in d]}
    if (i + 1) % 50 == 0: print("INT8", i + 1, round(time.time() - t0), "s", flush=True)
Path("/work/host_int8_test_dets.json").write_text(json.dumps(dets))
lab = {r["key"]: r["label"].replace("/home/mini/dfxisp_eval_20261007", "/hw") for r in man}
fr = {r["key"]: r for r in man}
def score(recs):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": recs}, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
res = {}
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    for kind in ("normal", "lowlight", "adaptive"):
        recs = {}
        for k in {r["key"] for r in man if r["split"] in parts}:
            chk = fr[k]["checker"] if kind == "adaptive" else None
            arm = kind if kind != "adaptive" else ("lowlight" if chk == "lowlight" else "normal")
            recs[k] = dets[arm][k]
        res[f"test_{sub}_{kind}"] = score(recs); print(f"test_{sub}_{kind}", res[f"test_{sub}_{kind}"], flush=True)
Path("/work/host_int8_test_scores.json").write_text(json.dumps(res, indent=1)); print("HOST_INT8_DONE")
