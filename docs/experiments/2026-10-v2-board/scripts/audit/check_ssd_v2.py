"""Pre-training checks for train_ssd_v2.py (no training):
1) The deployed checkpoint loads and our transform edit makes torchvision's own transform a no-op: model(x_pm1) equals the raw backbone/head path used by the DPU export (SSDLiteMobileNetDPU), after decode.
2) Our dataset item == run_detector.preprocess(...,'pm1') (the board contract), labels convert correctly (spot check vs YOLO txt).
3) Baseline (no training) dev score of the deployed SSD on the v2 val sets through the BOARD contract path (raw outputs -> run_detector.ssdlite_postprocess -> eval_map) -- the reference for 'does fine-tuning help'."""
import sys, json, io, contextlib, os, shutil, tempfile
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).parent))
import train_ssd_v2 as T
from PIL import Image
RD = T.RD; H = T.H
m = T.build().eval()
ds = T.DS("val", False); x, tg = ds[0]
p, lf, _ = ds.L[0]; img = np.asarray(Image.open(p).convert("RGB")); ref = RD.preprocess(img, 320, "pm1")
print("item == board preprocess:", bool(np.array_equal(x.numpy().transpose(1, 2, 0), ref)), "range", float(x.min()), float(x.max()))
a = np.loadtxt(lf, ndmin=2).reshape(-1, 5); print("labels", a.shape[0], "->", tg["labels"].tolist()[:5], "boxes0", tg["boxes"][:1].tolist(), "yolo0", a[:1].tolist())
# (1) torchvision full model path vs raw head path
full = T.build().eval()
with torch.no_grad():
    o = full.head(list(full.backbone(x[None]).values())); raw_reg, raw_cls = o["bbox_regression"], o["cls_logits"]
    img_list, _ = full.transform([x], None); print("transform output equals input:", bool(torch.allclose(img_list.tensors[0], x, atol=1e-6)), tuple(img_list.tensors.shape))
anc = np.load(H / "../Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app/ssdlite_anchors.npy") if False else np.load("/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app/ssdlite_anchors.npy")
print("anchors", anc.shape, "raw reg", tuple(raw_reg.shape), "cls", tuple(raw_cls.shape))
assert raw_reg.shape[1] == anc.shape[0]
# torchvision own anchors vs deployed anchors
with torch.no_grad():
    from torchvision.models.detection.image_list import ImageList
    il = ImageList(x[None], [(320, 320)]); feats = list(full.backbone(x[None]).values()); tva = full.anchor_generator(il, feats)[0].numpy()
print("anchor max abs diff vs deployed anchors:", float(np.abs(tva - anc).max()))
# (3) baseline dev score via board path
def detect(img_u8):
    xx = RD.preprocess(img_u8, 320, "pm1")
    with torch.no_grad():
        o = m.head(list(m.backbone(torch.from_numpy(xx.transpose(2, 0, 1))[None]).values()))
    outs = {"bbox_regression": o["bbox_regression"].numpy(), "cls_logits": o["cls_logits"].numpy()}
    d = RD.ssdlite_postprocess({"classification": outs["cls_logits"], "regression": outs["bbox_regression"]}, anc, 320, 0.001, 0.55)
    h, w = img_u8.shape[:2]
    return {"width": w, "height": h, "detections": [[float(b[0] * w / 320), float(b[1] * h / 320), float(b[2] * w / 320), float(b[3] * h / 320), float(b[4]), int(b[5])] for b in d]}
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
D = T.D; sub = int(sys.argv[1]) if len(sys.argv) > 1 else 60
for name, spec in (("night_normal", "night/normal"), ("night_lowlight", "night/lowlight"), ("day", "day")):
    ims = sorted((D / spec / "images/val").glob("*.png"))[:sub]; td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
    for p in ims:
        data["images"][p.stem] = detect(np.asarray(Image.open(p).convert("RGB"))); shutil.copyfile(D / spec / "labels/val" / (p.stem + ".txt"), f"{td}/{p.stem}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a95 = EM.evaluate(data, td)
    shutil.rmtree(td); print(f"deployed SSD (no training) dev {name} n={len(ims)} mAP50-95 {a95:.4f} mAP50 {a50:.4f}")
