"""Generalized SSD quantization with the SE fix (cap fix-point of the two SE fc2 outputs that otherwise get 11 -> K=8). Container.
Weights: <tag> in {old, SSD_A_full_s0, s1, s2}; 'old' loads the deployed project checkpoint (/work/old_ssd_state.pt exported beforehand).
Calibration: the SAME 128 files as the deployed s0 quantization (train split only) for every tag, so the old model's calibration is also train-only v2 data (NOT the original project calibration).
modes: calib <tag> | fixexport <tag> <K> (edit quant_info, dev eval, export) | host <tag>"""
import json, shutil, sys, contextlib, io, tempfile
from pathlib import Path
import numpy as np, torch
mode, tag = sys.argv[1], sys.argv[2]; K = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sys.argv = ["x", "test", "SSD_A_full_s0"]
src = open("/work/quant_ssd_v2.py").read(); ns = {}; exec(src[:src.index('if __name__ == "__main__":')], ns); Raw = ns["Raw"]; load = ns["load"]
sd = torch.load(f"/work/{'old' if tag == 'old' else tag}_ssd_state.pt", map_location="cpu")["model_state_dict"]; model = Raw(sd).eval()
OUT = Path(f"/work/quantg_{tag}_k{K}"); from pytorch_nndct.apis import torch_quantizer
if mode == "calib":
    OUT = Path(f"/work/quantg_{tag}_calib")
    files = [Path(p) for p in json.loads(Path("/work/quant_SSD_A_full_s0/calib_files.json").read_text())]; assert len(files) == 128 and all("/images/train/" in str(p) for p in files)
    q = torch_quantizer("calib", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
    with torch.no_grad():
        for p in files: qm(torch.from_numpy(load(p)))
    q.export_quant_config(); print("CALIB_DONE", tag); sys.exit(0)
sys.path.insert(0, "/work/vendor"); sys.path.insert(0, "/work/app")
import run_detector as RD, eval_map as EM
from PIL import Image
RD._have_cv2 = lambda: False; ANC = np.load("/work/app/ssdlite_anchors.npy")
if mode == "fixexport":
    if not OUT.exists(): shutil.copytree(Path(f"/work/quantg_{tag}_calib"), OUT)
    qi = json.loads((OUT / "quant_info.json").read_text()); hits = [n for n, v in qi["output"].items() if "conv2d" in n and v[0][1] >= 11]
    assert K == 0 or len(hits) == 2, hits
    if K != 0:   # K=0 -> keep the calibrated values unchanged (control: same calibration, no SE fix)
        for n in hits: qi["output"][n] = [[8, K]]
        (OUT / "quant_info.json").write_text(json.dumps(qi))
    print("edited" if K else "UNCHANGED(control)", hits, "->", K if K else qi["output"][hits[0]])
q = torch_quantizer("test", model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu")); qm = q.quant_model.eval()
def detect(img):
    h, w = img.shape[:2]; x = RD.preprocess(img, 320, "pm1").transpose(2, 0, 1)[None].copy()
    with torch.no_grad(): reg, cls = qm(torch.from_numpy(x))
    d = RD.ssdlite_postprocess({"classification": cls.numpy(), "regression": reg.numpy()}, ANC, 320, 0.001, 0.55)
    return {"width": w, "height": h, "detections": [[float(b[0]*w/320), float(b[1]*h/320), float(b[2]*w/320), float(b[3]*h/320), float(b[4]), int(b[5])] for b in d]}
def score(recs, lab):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": recs}, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
if mode == "fixexport":
    D = Path("/work/v2_data"); res = {}
    for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
        for p, kind in spec:
            recs = {}; lab = {}
            for im in sorted((D / p / "images/val").glob("*.png")): recs[im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); lab[im.stem] = str(D / p / "labels/val" / (im.stem + ".txt"))
            res[f"dev_{sub}_{kind}"] = score(recs, lab); print(f"dev_{sub}_{kind}", "%.4f" % res[f"dev_{sub}_{kind}"]["mAP50_95"], flush=True)
    (OUT / "dev_scores_int8.json").write_text(json.dumps(res, indent=1)); q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE", tag); sys.exit(0)
if mode == "host":
    man = json.loads(Path("/work/test_rgb/manifest.json").read_text()); dets = {"normal": {}, "lowlight": {}}
    for r in man: dets[r["arm"]][r["key"]] = detect(np.asarray(Image.open(Path("/work/test_rgb") / r["file"]).convert("RGB")))
    Path(f"/work/hostg_dets_{tag}_k{K}.json").write_text(json.dumps(dets))
    lab = {r["key"]: r["label"].replace("/home/mini/dfxisp_eval_20261007/hw1368", "/hw") for r in man}; fr = {r["key"]: r for r in man}; res = {}
    for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
        for kind in ("normal", "lowlight", "adaptive"):
            recs = {}
            for k in {r["key"] for r in man if r["split"] in parts}:
                arm = kind if kind != "adaptive" else ("lowlight" if fr[k]["checker"] == "lowlight" else "normal"); recs[k] = dets[arm][k]
            res[f"test_{sub}_{kind}"] = score(recs, lab)
    Path(f"/work/hostg_scores_{tag}_k{K}.json").write_text(json.dumps(res, indent=1)); print("HOST_DONE", tag)
