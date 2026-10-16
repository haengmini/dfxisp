"""Quantize a v2 SSDLite-MobileNetV3 (4-class incl. background) with Vitis AI NNDCT inside vitis-ai-pytorch-cpu. Same protocol as quant_v2.py (YOLO):
- calibration = 128 images from v2 TRAIN only (seeded; 32 night-normal, 32 night-lowlight, 32 day-replay, 32 night lowlight/normal other frames)
- dev eval on v2 val (never test), then export xmodel batch 1
Input contract: v2_data 640x640 PNG -> board resize to 320 (PIL BILINEAR via run_detector.resize_rgb) -> (x/255-.5)/.5.
Outputs of the DPU model: (bbox_regression (1,3234,4), cls_logits (1,3234,4)); anchors, softmax, decode and NMS stay on CPU as in the deployed model.
modes inside container: equiv <tag> | calib <tag> | test <tag>   (equiv: compare container model with trained-model reference tensors from <tag>_ssd_ref.pt)"""
import json, random, sys
from pathlib import Path
import numpy as np, torch
from torch import nn
from PIL import Image
mode, tag = sys.argv[1], sys.argv[2]
W = Path("/work"); D = Path("/work/v2_data"); OUT = W / f"quant_{tag}"
sys.path.insert(0, "/work/vendor"); sys.path.insert(0, "/work/app")
import run_detector as RD
RD._have_cv2 = lambda: False
from torchvision.models.detection import ssdlite320_mobilenet_v3_large

class Raw(nn.Module):
    def __init__(self, sd):
        super().__init__()
        m = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=4)
        m.load_state_dict(sd); self.backbone = m.backbone; self.head = m.head
    def forward(self, x):
        o = self.head(list(self.backbone(x).values())); return o["bbox_regression"], o["cls_logits"]

def load(p): return RD.preprocess(np.asarray(Image.open(p).convert("RGB")), 320, "pm1").transpose(2, 0, 1)[None].copy()

def calib_files():
    rnd = random.Random(20261015); tr = lambda s: sorted((D / s / "images/train").glob("*.png"))
    nn_, nl, dd = tr("night/normal"), tr("night/lowlight"), tr("day")
    a = rnd.sample(nn_, 32); b = rnd.sample(nl, 32); c = rnd.sample(dd, 32)
    rest = [p for p in nn_ + nl if p not in set(a + b)]; d = rnd.sample(rest, 32)
    return a + b + c + d

if __name__ == "__main__":
    sd = torch.load(f"/work/{tag}_ssd_state.pt", map_location="cpu")["model_state_dict"]
    model = Raw(sd).eval()
    if mode == "equiv":
        ref = torch.load(f"/work/{tag}_ssd_ref.pt"); worst = 0.0
        for name, x, outs in ref:
            with torch.no_grad(): got = model(x)
            for g, r in zip(got, outs): worst = max(worst, float((g - r).abs().max()))
        print("max abs diff over", len(ref), "images x 2 tensors:", worst); print("EQUIV_PASS" if worst < 1e-4 else "EQUIV_FAIL"); sys.exit(0 if worst < 1e-4 else 1)
    from pytorch_nndct.apis import torch_quantizer
    q = torch_quantizer(mode, model, (torch.zeros(1, 3, 320, 320),), output_dir=str(OUT), device=torch.device("cpu"))
    qm = q.quant_model.eval()
    if mode == "calib":
        files = calib_files(); assert len(files) == 128 and len(set(files)) == 128
        assert all("/images/train/" in str(p) for p in files)
        with torch.no_grad():
            for p in files: qm(torch.from_numpy(load(p)))
        q.export_quant_config(); (OUT / "calib_files.json").write_text(json.dumps([str(p) for p in files])); print("CALIB_DONE", tag, len(files)); sys.exit(0)
    import contextlib, io, os, shutil, tempfile
    import eval_map as EM
    ANC = np.load("/work/app/ssdlite_anchors.npy")
    def detect(img):
        h, w = img.shape[:2]; x = RD.preprocess(img, 320, "pm1").transpose(2, 0, 1)[None].copy()
        with torch.no_grad(): reg, cls = qm(torch.from_numpy(x))
        d = RD.ssdlite_postprocess({"classification": cls.numpy(), "regression": reg.numpy()}, ANC, 320, 0.001, 0.55)
        return {"width": w, "height": h, "detections": [[float(b[0] * w / 320), float(b[1] * h / 320), float(b[2] * w / 320), float(b[3] * h / 320), float(b[4]), int(b[5])] for b in d]}
    res = {}
    for sub, spec in (("night_newval", [("night/normal", "normal"), ("night/lowlight", "lowlight")]), ("day_val", [("day", "day")])):
        for p, kind in spec:
            td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
            for im in sorted((D / p / "images/val").glob("*.png")):
                data["images"][im.stem] = detect(np.asarray(Image.open(im).convert("RGB"))); shutil.copyfile(D / p / "labels/val" / (im.stem + ".txt"), f"{td}/{im.stem}.txt")
            with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate(data, td)
            shutil.rmtree(td); res[f"dev_{sub}_{kind}"] = {"mAP50_95": a, "mAP50": a50, "n": len(data["images"])}; print(f"dev_{sub}_{kind}", "%.4f" % a, flush=True)
    (OUT / "dev_scores_int8.json").write_text(json.dumps(res, indent=1))
    q.export_xmodel(output_dir=str(OUT), deploy_check=False); print("EXPORT_DONE", tag)
