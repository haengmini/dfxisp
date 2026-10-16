"""Quantize the v2 project YOLO (3-class, Hardswish) with Vitis AI NNDCT inside the vitis-ai-pytorch-cpu container (Python 3.8, torch 1.x NNDCT).
Calibration = 128 images drawn ONLY from v2 TRAIN: 32 night-normal + 32 night-lowlight(BLC16) of the same frames' mix + 32 day-replay + 32 night-lowlight/normal other frames. Seeded.
Val-mode accuracy is measured on v2 DEV val (not test). Test frames are never read here.
modes: calib | test(dev eval, then export xmodel batch1)
usage inside container: python quant_v2.py <calib|test> <tag>"""
import json, random, sys
from pathlib import Path
import numpy as np, torch
from torch import nn
from PIL import Image
mode, tag = sys.argv[1], sys.argv[2]
W = Path("/work"); D = Path("/work/v2_data"); OUT = W / f"quant_{tag}"
sys.path.insert(0, "/work/vendor")
class Raw(nn.Module):
    """YOLO backbone+neck+head up to the six raw conv outputs (cv2_i box, cv3_i cls); DFL/decode/NMS stay on CPU as in the deployed model.
    Structure is rebuilt as the deployed (Conv-Conv, non-DW) head: the deployed yolov8n.pt and the v2 trained model have identical 355 state_dict keys,
    while the container's ultralytics 8.3.0 default head differs, so the module tree is copied from the deployed checkpoint's own class layout."""
    def __init__(self, state):
        super().__init__()
        from ultralytics.nn.tasks import DetectionModel
        net = DetectionModel("yolov8n.yaml", nc=3, verbose=False)
        head = net.model[-1]
        from ultralytics.nn.modules.conv import Conv
        c3 = max(head.cv3[0][0][1].conv.out_channels if hasattr(head.cv3[0][0], "__getitem__") else 64, 3)
        ch = [m[0][0].conv.in_channels if isinstance(m[0], nn.Sequential) else m[0].conv.in_channels for m in head.cv3]
        head.cv3 = nn.ModuleList(nn.Sequential(Conv(x, c3, 3), Conv(c3, c3, 3), nn.Conv2d(c3, head.nc, 1)) for x in ch)
        for mod in net.modules():
            if isinstance(mod, nn.BatchNorm2d): mod.eps, mod.momentum = 1e-3, 0.03   # Ultralytics training convention; Conv() in this container defaults differ
        def rep(m):
            for n, c in m.named_children():
                if isinstance(c, nn.SiLU): setattr(m, n, nn.Hardswish(inplace=False))
                else: rep(c)
        rep(net); net.load_state_dict(state); self.net = net.eval(); head.export = True
    def forward(self, x):
        y = []
        for m in self.net.model[:-1]:
            if m.f != -1: x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
            x = m(x); y.append(x if m.i in self.net.save else None)
        head = self.net.model[-1]; xs = [y[j] for j in head.f]
        return tuple(v for i in range(head.nl) for v in (head.cv2[i](xs[i]), head.cv3[i](xs[i])))
def load(p): return torch.from_numpy(np.asarray(Image.open(p).convert("RGB")).astype(np.float32).transpose(2, 0, 1)[None] / 255.0)
state = torch.load(W / f"{tag}_state.pt", map_location="cpu")["state_dict"]
model = Raw(state).eval()
from pytorch_nndct.apis import torch_quantizer
q = torch_quantizer(mode, model, (torch.zeros(1, 3, 640, 640),), output_dir=str(OUT), device=torch.device("cpu"))
qm = q.quant_model.eval()
if mode == "calib":
    rnd = random.Random(20261014); sel = []
    for pat, n in (("night/normal/images/train", 40), ("night/lowlight/images/train", 40), ("day/images/train", 48)):
        ps = sorted((D / pat).glob("*.png")); rnd.shuffle(ps); sel += ps[:n]
    assert all("train" in str(p) for p in sel) and len(sel) == 128
    (OUT / "calib_files.json").write_text(json.dumps([str(p.relative_to(D)) for p in sel]))
    with torch.no_grad():
        for i, p in enumerate(sel):
            qm(load(p))
            if (i + 1) % 32 == 0: print("CALIB", i + 1, flush=True)
    q.export_quant_config(); print("CALIB_DONE", len(sel)); sys.exit(0)
sys.path.insert(0, "/work/app")
import run_detector as RD, eval_map as EM
RD._have_cv2 = lambda: False
import io, contextlib, shutil, tempfile
res = {}
def detect(img):
    h, w = img.shape[:2]; x = torch.from_numpy(RD.preprocess(img, 640, "unit")).permute(2, 0, 1)[None].float()
    with torch.no_grad(): outs = [v.detach().numpy() for v in qm(x)]
    oo = {f"cv{2 + (j % 2)}_{j // 2}": v.transpose(0, 2, 3, 1) for j, v in enumerate(outs)}
    d = RD.yolov8_postprocess(oo, 640, 3, 0.001, 0.45)
    return {"width": w, "height": h, "detections": [[float(b[0]*w/640), float(b[1]*h/640), float(b[2]*w/640), float(b[3]*h/640), float(b[4]), int(b[5])] for b in d]}
def score(recs, labs):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(labs[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": recs}, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
    for p, kind in spec:
        recs, labs = {}, {}
        for im in sorted((D / p / "images/val").glob("*.png"))[:int(sys.argv[3]) if len(sys.argv) > 3 else 10**9]:
            recs[im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); labs[im.stem] = str(D / p / "labels/val" / (im.stem + ".txt"))
        res[f"dev_{sub}_{kind}"] = score(recs, labs); print(f"dev_{sub}_{kind}", res[f"dev_{sub}_{kind}"], flush=True)
(OUT / "dev_scores_int8.json").write_text(json.dumps(res, indent=1))
q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE")
