"""Smoke: does a Hardswish-swapped model survive Ultralytics trainer build + 1 iteration of training? Uses 24 existing night images (tmp data), CPU/GPU, no repo/test data."""
import sys, torch, torch.nn as nn, shutil, random
from pathlib import Path
sys.path.insert(0, "/tmp")
import importlib.util
H = Path.home() / "dfxisp_eval_20261007"
from ultralytics import YOLO
from ultralytics.nn.modules.conv import Conv
Conv.default_act = nn.Hardswish()
def swap(m):
    n = 0
    for name, c in list(m.named_children()):
        if isinstance(c, nn.SiLU): setattr(m, name, nn.Hardswish(inplace=True)); n += 1
        else: n += swap(c)
    return n
y = YOLO("/home/mini/Desktop/dfxisp/hw/ai/models/yolov8n/yolov8n.pt"); n = swap(y.model); print("swapped", n)
tmp = Path("/tmp/hs_smoke"); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
torch.save({"model": y.model, "train_args": {}, "epoch": -1}, tmp / "init.pt")
y2 = YOLO(str(tmp / "init.pt")); print("after reload SiLU", sum(isinstance(x, nn.SiLU) for x in y2.model.modules()), "Hardswish", sum(isinstance(x, nn.Hardswish) for x in y2.model.modules()))
src = H / "sep_20261012/ft_img/normal"; (tmp / "i").mkdir(); (tmp / "l").mkdir()
ims = sorted((src / "train/images").glob("*.png"))[:24]; L = []
for p in ims:
    (tmp / "i" / p.name).symlink_to(p); L.append(str(tmp / "i" / p.name))
    (tmp / "l").joinpath(p.stem + ".txt").write_text((src / "train/labels" / (p.stem + ".txt")).read_text())
# labels must be at .../labels/<name>.txt relative to images dir swap: build proper layout
shutil.rmtree(tmp / "i"); shutil.rmtree(tmp / "l")
(tmp / "images").mkdir(); (tmp / "labels").mkdir()
for p in ims:
    (tmp / "images" / p.name).symlink_to(p); (tmp / "labels" / (p.stem + ".txt")).write_text((src / "train/labels" / (p.stem + ".txt")).read_text())
(tmp / "d.yaml").write_text(f"path: {tmp}\ntrain: images\nval: images\nnames:\n  0: person\n  1: car\n  2: bicycle\n")
r = y2.train(data=str(tmp / "d.yaml"), epochs=1, imgsz=640, batch=8, workers=0, device=0, amp=False, plots=False, project=str(tmp), name="r", exist_ok=True, val=False, verbose=False)
m = torch.load(tmp / "r/weights/last.pt", map_location="cpu", weights_only=False)["model"]
s = sum(isinstance(x, nn.SiLU) for x in m.modules()); h = sum(isinstance(getattr(x, "act", None), nn.Hardswish) for x in m.modules() if hasattr(x, "conv"))
print("after train SiLU", s, "Hardswish", h); assert s == 0 and h > 50; print("HSWISH_SURVIVES_TRAINING")
