"""SSDLite-MobileNetV3 v2 balanced fine-tuning (laptop GPU). One shared detector for BOTH ISPs, Hardswish kept as in the deployed model (torchvision SSDLite uses Hardswish natively),
same data/split/protocol as the YOLO v2 A_full arm: night Normal + night Lowlight(BLC16) views of the SAME 1,335 frames + day replay 899; val = new-val night (both ISPs) + day val.
Init: the deployed project checkpoint (ssdlite-mobilenetv3.pt, epoch 64). Input contract: 640x640 stretched PNG -> 320x320 (same resize as run_detector.resize_rgb) -> (x/255-0.5)/0.5.
Labels: YOLO txt (0 person,1 car,2 bicycle) -> torchvision labels 1..3 (0 = background), boxes xyxy in 320 coords.
Selection: last epoch only (no checkpoint chosen by test). Test frames never touched here.
Usage: train_ssd_v2.py <seed> [epochs] [lr]"""
import sys, json, random, time
from pathlib import Path
import numpy as np, torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision.models.detection import ssdlite320_mobilenet_v3_large
H = Path.home() / "dfxisp_eval_20261007"; D = H / "v2_data"; RUNS = H / "v2_runs"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app")
import run_detector as RD
RD._have_cv2 = lambda: False
CK = "/home/mini/Desktop/dfxisp/hw/ai/models/mobilenet/ssdlite-mobilenetv3.pt"

def items(split):
    L = []
    for a in ("normal", "lowlight"):
        for p in sorted((D / "night" / a / "images" / split).glob("*.png")): L.append((p, D / "night" / a / "labels" / split / (p.stem + ".txt"), "night"))
    for p in sorted((D / "day/images" / split).glob("*.png")): L.append((p, D / "day/labels" / split / (p.stem + ".txt"), "day"))
    return L

def read_labels(f):
    a = np.loadtxt(f, ndmin=2) if Path(f).stat().st_size else np.zeros((0, 5))
    return a.reshape(-1, 5)

class DS(Dataset):
    def __init__(self, split, train):
        self.L = items(split); self.train = train
    def __len__(self): return len(self.L)
    def __getitem__(self, i):
        p, lf, _ = self.L[i]; img = np.asarray(Image.open(p).convert("RGB"))                  # 640x640 uint8 (already stretched)
        x = RD.preprocess(img, 320, "pm1")                                                     # (320,320,3) float, board resize + [-1,1]
        a = read_labels(lf); cls = a[:, 0].astype(np.int64) + 1; cx, cy, w, h = a[:, 1] * 320, a[:, 2] * 320, a[:, 3] * 320, a[:, 4] * 320
        b = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 1).astype(np.float32) if len(a) else np.zeros((0, 4), np.float32)
        b = np.clip(b, 0, 320)
        if self.train:
            if random.random() < 0.5: x = x[:, ::-1].copy(); b = b.copy(); b[:, [0, 2]] = 320 - b[:, [2, 0]]
            # photometric jitter in the image domain (brightness/contrast), mild; keeps the ISP-output statistics of each view
            g = 1 + random.uniform(-.25, .25); o = random.uniform(-.1, .1); x = np.clip(x * g + o, -1, 1)
        keep = (b[:, 2] - b[:, 0] > 1) & (b[:, 3] - b[:, 1] > 1); b, cls = b[keep], cls[keep]
        return torch.from_numpy(x.transpose(2, 0, 1).copy()).float(), {"boxes": torch.from_numpy(b), "labels": torch.from_numpy(cls)}

def collate(b): return tuple(zip(*b))

def build():
    m = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=4)
    m.load_state_dict(torch.load(CK, map_location="cpu", weights_only=False)["model_state_dict"])
    # inputs are already normalized by us ([-1,1]); disable torchvision's internal transform scaling (mean .5/std .5 would double-normalize) and resize (already 320)
    m.transform.image_mean = [0.0, 0.0, 0.0]; m.transform.image_std = [1.0, 1.0, 1.0]; m.transform.min_size = (320,); m.transform.max_size = 320
    return m

if __name__ == "__main__":
    seed = int(sys.argv[1]); epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 30; lr0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.002
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    out = RUNS / f"SSD_A_full_s{seed}"; out.mkdir(parents=True, exist_ok=True)
    m = build().cuda(); params = [p for p in m.parameters() if p.requires_grad]
    opt = torch.optim.SGD(params, lr=lr0, momentum=0.9, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr0, total_steps=epochs * (len(DS("train", True)) // 16), pct_start=0.05, anneal_strategy="cos", final_div_factor=10)
    g = torch.Generator(); g.manual_seed(seed)
    dl = DataLoader(DS("train", True), batch_size=16, shuffle=True, num_workers=4, collate_fn=collate, generator=g, drop_last=True)
    vdl = DataLoader(DS("val", False), batch_size=16, shuffle=False, num_workers=4, collate_fn=collate)
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    log = []
    print("train items", len(dl.dataset), "val items", len(vdl.dataset), "lr0", lr0, "epochs", epochs, flush=True)
    for ep in range(epochs):
        m.train(); t0 = time.time(); tot = 0.0; n = 0
        for imgs, tg in dl:
            imgs = [i.cuda() for i in imgs]; tg = [{k: v.cuda() for k, v in t.items()} for t in tg]
            loss = sum(m(imgs, tg).values()); opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 10.0); opt.step(); sched.step()
            tot += float(loss); n += 1
        m.eval(); vloss = 0.0; vn = 0
        m.train()                                              # val loss needs train-mode loss dict; BN uses batch stats -> use eval for BN only
        for mod in m.modules():
            if isinstance(mod, torch.nn.modules.batchnorm._BatchNorm): mod.eval()
        with torch.no_grad():
            for imgs, tg in vdl:
                imgs = [i.cuda() for i in imgs]; tg = [{k: v.cuda() for k, v in t.items()} for t in tg]; vloss += float(sum(m(imgs, tg).values())); vn += 1
        log.append({"epoch": ep + 1, "train_loss": tot / n, "val_loss": vloss / vn, "sec": time.time() - t0}); print(json.dumps(log[-1]), flush=True)
    torch.save({"model_state_dict": m.state_dict(), "seed": seed, "epochs": epochs, "lr0": lr0, "log": log}, out / "last.pt")
    (out / "log.json").write_text(json.dumps(log, indent=1)); print("TRAIN_DONE SSD", seed)
