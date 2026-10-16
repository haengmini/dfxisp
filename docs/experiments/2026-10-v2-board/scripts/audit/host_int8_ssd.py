"""Host INT8 (NNDCT test mode) of a v2 SSD on the 400 pre-rendered TEST RGB images; dumps detections in board-contract format. Inside vitis-ai-pytorch-cpu.
usage: python host_int8_ssd.py <tag>   (tag = SSD_A_full_sN; needs /work/<tag>_ssd_state.pt and /work/quant_<tag>)"""
import json, sys, io, contextlib, shutil, tempfile, time
from pathlib import Path
import numpy as np, torch
from PIL import Image
tag = sys.argv[1]; sys.argv = ["x", "test", tag]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]
sys.path.insert(0, "/work/vendor"); sys.path.insert(0, "/work/app")
import run_detector as RD, eval_map as EM
RD._have_cv2 = lambda: False
sd = torch.load(f"/work/{tag}_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Raw(sd).eval()
from pytorch_nndct.apis import torch_quantizer
q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=f"/work/quant_{tag}", device=torch.device("cpu")); qm = q.quant_model.eval()
ANC = np.load("/work/app/ssdlite_anchors.npy"); man = json.loads(Path("/work/test_rgb/manifest.json").read_text())
dets = {"normal": {}, "lowlight": {}}; t0 = time.time()
for i, r in enumerate(man):
    img = np.asarray(Image.open(Path("/work/test_rgb") / r["file"]).convert("RGB")); h, w = img.shape[:2]
    x = torch.from_numpy(RD.preprocess(img, 320, "pm1").transpose(2, 0, 1)[None].copy()).float()
    with torch.no_grad(): reg, cls = qm(x)
    d = RD.ssdlite_postprocess({"classification": cls.numpy(), "regression": reg.numpy()}, ANC, 320, 0.001, 0.55)
    dets[r["arm"]][r["key"]] = {"width": w, "height": h, "detections": [[float(b[0]*w/320), float(b[1]*h/320), float(b[2]*w/320), float(b[3]*h/320), float(b[4]), int(b[5])] for b in d]}
    if (i + 1) % 100 == 0: print("INT8", i + 1, round(time.time() - t0), "s", flush=True)
Path(f"/work/host_int8_ssd_dets_{tag}.json").write_text(json.dumps(dets))
lab = {r["key"]: r["label"].replace("/home/mini/dfxisp_eval_20261007/hw1368", "/hw") for r in man}; fr = {r["key"]: r for r in man}
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
            arm = kind if kind != "adaptive" else ("lowlight" if fr[k]["checker"] == "lowlight" else "normal"); recs[k] = dets[arm][k]
        res[f"test_{sub}_{kind}"] = score(recs); print(f"test_{sub}_{kind}", res[f"test_{sub}_{kind}"], flush=True)
Path(f"/work/host_int8_ssd_scores_{tag}.json").write_text(json.dumps(res, indent=1)); print("HOST_INT8_DONE", tag)
