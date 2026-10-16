"""v2 balanced training (laptop GPU). One shared detector for BOTH ISPs, Hardswish applied BEFORE training, board geometry (640 stretch pre-applied).
Arms (same data/seed/steps unless noted):
  base_hswish        : reference only, no training (eval via eval_v2.py)
  A_full             : all params, SGD lr0=0.002, 30 ep
  B_freeze10         : freeze backbone layers 0-9, SGD lr0=0.002, 30 ep (preserve pretrained features)
Data per epoch: night Normal + night Lowlight(BLC16) of the SAME frames (2 views) + day replay. Held-out val = new-val night (both ISPs) + day-val.
Usage: train_v2.py <arm> <seed> [epochs]"""
import os, sys, json, random, shutil
from pathlib import Path
import torch, torch.nn as nn
H = Path.home() / "dfxisp_eval_20261007"; D = H / "v2_data"; RUNS = H / "v2_runs"
arm, seed = sys.argv[1], int(sys.argv[2]); epochs = int(sys.argv[3]) if len(sys.argv) > 3 else 30
assert arm in ("A_full", "B_freeze10", "smoke")
BASE = "/home/mini/Desktop/dfxisp/hw/ai/models/yolov8n/yolov8n.pt"

def build_lists(root):
    """train/val image list files (Ultralytics accepts txt lists of image paths; labels resolved by images->labels path swap)."""
    lists = {}
    for sp in ("train", "val"):
        L = []
        for a in ("normal", "lowlight"):
            L += sorted(str(p) for p in (D / "night" / a / "images" / sp).glob("*.png"))
        L += sorted(str(p) for p in (D / "day/images" / sp).glob("*.png"))
        f = root / f"{sp}.txt"; f.write_text("\n".join(L) + "\n"); lists[sp] = (f, len(L))
    return lists

def hswish_swap(m):
    n = 0
    for name, c in list(m.named_children()):
        if isinstance(c, nn.SiLU): setattr(m, name, nn.Hardswish(inplace=True)); n += 1
        else: n += hswish_swap(c)
    return n

if __name__ == "__main__":
    from ultralytics import YOLO
    from ultralytics.nn.modules.conv import Conv
    out = RUNS / f"{arm}_s{seed}"; out.mkdir(parents=True, exist_ok=True)
    Conv.default_act = nn.Hardswish()             # new Conv blocks (e.g. rebuilt head) use Hardswish too
    lists = build_lists(out)
    (out / "data.yaml").write_text(f"path: {D}\ntrain: {lists['train'][0]}\nval: {lists['val'][0]}\nnames:\n  0: person\n  1: car\n  2: bicycle\n")
    y = YOLO(BASE); swapped = hswish_swap(y.model)
    assert swapped > 50, swapped
    assert not any(isinstance(m, nn.SiLU) for m in y.model.modules()), "SiLU left"
    # Ultralytics re-reads the checkpoint model when train() builds the trainer via self.model; keep our swapped module by passing it through a temp ckpt
    tmp = out / "init_hswish.pt"; torch.save({"model": y.model, "train_args": {}, "epoch": -1}, tmp)
    y = YOLO(str(tmp)); assert not any(isinstance(m, nn.SiLU) for m in y.model.modules()), "SiLU after reload"
    print("train images", lists["train"][1], "val images", lists["val"][1], "hardswish layers", swapped, flush=True)
    freeze = 10 if arm == "B_freeze10" else None
    if arm == "smoke": epochs = 1
    y.train(data=str(out / "data.yaml"), epochs=epochs, imgsz=640, batch=16, seed=seed, deterministic=True, project=str(RUNS), name=f"{arm}_s{seed}", exist_ok=True,
            pretrained=True, optimizer="SGD", lr0=0.002, lrf=0.1, warmup_epochs=1, close_mosaic=5, workers=4, device=0, amp=False, plots=False, val=True, patience=0,
            freeze=freeze, hsv_h=0.015, hsv_s=0.7, hsv_v=0.4, mosaic=1.0, fliplr=0.5, scale=0.5, erasing=0.4, cache=False, fraction=1.0, save_period=-1)
    ck = out / "weights/last.pt"; assert ck.exists()
    m = torch.load(ck, map_location="cpu", weights_only=False)["model"]
    silu = sum(isinstance(x, nn.SiLU) for x in m.modules()); hs = sum(isinstance(getattr(x, "act", None), nn.Hardswish) for x in m.modules() if hasattr(x, "conv"))
    print("final: SiLU", silu, "Conv blocks with Hardswish act", hs); assert silu == 0 and hs >= 56, (silu, hs)
    print("TRAIN_DONE", arm, seed)
