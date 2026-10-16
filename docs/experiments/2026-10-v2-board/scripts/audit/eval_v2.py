"""Evaluate ONE detector on BOTH ISPs under the board contract. Board scorer eval_map.py is primary.
Test: night100 (LOD) + day100 (PASCAL) from hw1368 bins (never trained on) -> NormalISP / LowlightISP BLC16 (repo golden) -> PIL BILINEAR 640 stretch
-> hardswish FP32 -> run_detector.yolov8_postprocess(conf .001, iou .45) -> scaled to ISP output size -> eval_map. Adaptive = same checker verdict as phaseA frames.json.
Dev: v2_data val (night normal/lowlight new-val + day val), already 640-stretched.
Usage: eval_v2.py <tag> <weights.pt|base> [dev|test|both]"""
import contextlib, io, json, os, sys, shutil, tempfile
from pathlib import Path
import numpy as np, torch, torch.nn as nn
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"
sys.path.insert(0, str(Path.home() / "Desktop/dfxisp/isppipeline/sw"))
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app")
import default_isp_pipeline as PD
import lowlight_isp_pipeline as PW
import run_detector as RD
import eval_map as EM
RD._have_cv2 = lambda: False                         # board rootfs: PIL BILINEAR
assert PW.G.BLC_LEVEL12 == 16 and PW.G.BLC_MUL_Q8 == 257
BASE = "/home/mini/Desktop/dfxisp/hw/ai/models/yolov8n/yolov8n.pt"
tag, wpath = sys.argv[1], sys.argv[2]; mode = sys.argv[3] if len(sys.argv) > 3 else "both"
from ultralytics import YOLO
y = YOLO(BASE if wpath == "base" else wpath).model.eval().float()
def swap(m):
    for n, c in list(m.named_children()):
        if isinstance(c, nn.SiLU): setattr(m, n, nn.Hardswish(inplace=True))
        else: swap(c)
swap(y)
assert not any(isinstance(x, nn.SiLU) for x in y.modules())
det = y.model[-1]; det.export = True; raw = {}
for i in range(det.nl):
    det.cv2[i].register_forward_hook(lambda m, a, o, i=i: raw.__setitem__(f"cv2_{i}", o)); det.cv3[i].register_forward_hook(lambda m, a, o, i=i: raw.__setitem__(f"cv3_{i}", o))
y = y.cuda()
def detect(img):
    h, w = img.shape[:2]; x = RD.preprocess(img, 640, "unit")
    with torch.no_grad(): y(torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float().cuda())
    outs = {k: v.permute(0, 2, 3, 1).cpu().numpy() for k, v in raw.items()}
    d = RD.yolov8_postprocess(outs, 640, 3, 0.001, 0.45)
    return {"width": w, "height": h, "detections": [[float(b[0] * w / 640), float(b[1] * h / 640), float(b[2] * w / 640), float(b[3] * h / 640), float(b[4]), int(b[5])] for b in d]}
def score(recs, labdir):
    td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
    for k, r in recs.items():
        data["images"][k] = r; shutil.copyfile(os.path.join(labdir[k]), os.path.join(td, k + ".txt"))
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate(data, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
res = {"tag": tag, "weights": wpath}
if mode in ("test", "both"):
    fr = json.loads((H / "phaseA_pil/frames.json").read_text()); dets = {}; labs = {}
    for r in fr:
        d = "LOD" if r["split"] == "night" else "PASCAL"; k = f"{r['split']}_{r['stem']}"
        r12 = np.fromfile(H / "hw1368" / d / "raw_bin" / f"{r['stem']}.bin", dtype="<u2").reshape(912, 1368); r16 = r12.astype(np.uint16) << 4
        for arm, name in (("normal", "default_isp"), ("lowlight", "lowlight_isp")):
            fn = PD if arm == "normal" else PW
            dets.setdefault(arm, {})[k] = detect(fn.run_arm(r16, 1368, 912, name))
        labs[k] = str(H / "hw1368" / d / "labels" / f"{r['stem']}.txt")
    for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
        for kind in ("normal", "lowlight", "adaptive"):
            recs = {}
            for r in fr:
                if r["split"] not in parts: continue
                k = f"{r['split']}_{r['stem']}"; arm = kind if kind != "adaptive" else ("lowlight" if r["checker"] == "lowlight" else "normal"); recs[k] = dets[arm][k]
            res[f"test_{sub}_{kind}"] = score(recs, labs)
    (H / "v2_eval").mkdir(exist_ok=True); (H / "v2_eval" / f"dets_test_{tag}.json").write_text(json.dumps(dets))
if mode in ("dev", "both"):
    D = H / "v2_data"
    for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
        for p, kind in spec:
            recs, labs = {}, {}
            for im in sorted((D / p / "images/val").glob("*.png")):
                recs[im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); labs[im.stem] = str(D / p / "labels/val" / (im.stem + ".txt"))
            res[f"dev_{sub}_{kind}"] = score(recs, labs)
(H / "v2_eval").mkdir(exist_ok=True); (H / "v2_eval" / f"scores_{tag}.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    if isinstance(v, dict): print(k, "mAP50-95 %.4f mAP50 %.4f n=%d" % (v["mAP50_95"], v["mAP50"], v["n"]))
print("EVAL_DONE", tag)
