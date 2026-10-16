"""Evaluate ONE SSDLite detector on BOTH ISPs under the board contract (mirror of eval_v2.py).
Test: night100 (LOD) + day100 (PASCAL) from hw1368 bins -> NormalISP / LowlightISP BLC16 (repo golden) -> board resize (PIL BILINEAR) to 320 -> (x/255-.5)/.5 -> FP32 raw head ->
run_detector.ssdlite_postprocess(conf .001, iou .55, deployed anchors) -> scaled to ISP output size -> eval_map. Adaptive = same checker verdict as phaseA frames.json.
Dev: v2_data val (night normal/lowlight new-val + day val), already 640-stretched (resized 640->320 with the board resize).
Usage: eval_ssd_v2.py <tag> <weights.pt|base> [dev|test|both]"""
import contextlib, io, json, os, sys, shutil, tempfile
from pathlib import Path
import numpy as np, torch
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"
sys.path.insert(0, str(Path.home() / "Desktop/dfxisp/isppipeline/sw")); sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); sys.path.insert(0, str(H))
import default_isp_pipeline as PD
import lowlight_isp_pipeline as PW
import run_detector as RD
import eval_map as EM
import train_ssd_v2 as T
RD._have_cv2 = lambda: False
assert PW.G.BLC_LEVEL12 == 16 and PW.G.BLC_MUL_Q8 == 257
tag, wpath = sys.argv[1], sys.argv[2]; mode = sys.argv[3] if len(sys.argv) > 3 else "both"
m = T.build()
if wpath != "base": m.load_state_dict(torch.load(wpath, map_location="cpu", weights_only=False)["model_state_dict"])
m = m.eval().cuda(); ANC = np.load("/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app/ssdlite_anchors.npy")
def detect(img):
    h, w = img.shape[:2]; x = RD.preprocess(img, 320, "pm1")
    with torch.no_grad(): o = m.head(list(m.backbone(torch.from_numpy(x.transpose(2, 0, 1)).float()[None].cuda()).values()))
    d = RD.ssdlite_postprocess({"classification": o["cls_logits"].cpu().numpy(), "regression": o["bbox_regression"].cpu().numpy()}, ANC, 320, 0.001, 0.55)
    return {"width": w, "height": h, "detections": [[float(b[0] * w / 320), float(b[1] * h / 320), float(b[2] * w / 320), float(b[3] * h / 320), float(b[4]), int(b[5])] for b in d]}
def score(recs, labdir):
    td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
    for k, r in recs.items(): data["images"][k] = r; shutil.copyfile(labdir[k], os.path.join(td, k + ".txt"))
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate(data, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
res = {"tag": tag, "weights": wpath}
if mode in ("test", "both"):
    fr = json.loads((H / "phaseA_pil/frames.json").read_text()); dets = {}; labs = {}
    for r in fr:
        d = "LOD" if r["split"] == "night" else "PASCAL"; k = f"{r['split']}_{r['stem']}"
        r12 = np.fromfile(H / "hw1368" / d / "raw_bin" / f"{r['stem']}.bin", dtype="<u2").reshape(912, 1368); r16 = r12.astype(np.uint16) << 4
        for arm, name in (("normal", "default_isp"), ("lowlight", "lowlight_isp")):
            fn = PD if arm == "normal" else PW; dets.setdefault(arm, {})[k] = detect(fn.run_arm(r16, 1368, 912, name))
        labs[k] = str(H / "hw1368" / d / "labels" / f"{r['stem']}.txt")
    for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
        for kind in ("normal", "lowlight", "adaptive"):
            recs = {}
            for r in fr:
                if r["split"] not in parts: continue
                k = f"{r['split']}_{r['stem']}"; arm = kind if kind != "adaptive" else ("lowlight" if r["checker"] == "lowlight" else "normal"); recs[k] = dets[arm][k]
            res[f"test_{sub}_{kind}"] = score(recs, labs)
    (H / "v2_eval").mkdir(exist_ok=True); (H / "v2_eval" / f"ssd_dets_test_{tag}.json").write_text(json.dumps(dets))
if mode in ("dev", "both"):
    D = H / "v2_data"
    for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
        for p, kind in spec:
            recs, labs = {}, {}
            for im in sorted((D / p / "images/val").glob("*.png")):
                recs[im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); labs[im.stem] = str(D / p / "labels/val" / (im.stem + ".txt"))
            res[f"dev_{sub}_{kind}"] = score(recs, labs)
(H / "v2_eval").mkdir(exist_ok=True); (H / "v2_eval" / f"ssd_scores_{tag}.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    if isinstance(v, dict): print(k, "mAP50-95 %.4f mAP50 %.4f n=%d" % (v["mAP50_95"], v["mAP50"], v["n"]))
print("EVAL_DONE", tag)
