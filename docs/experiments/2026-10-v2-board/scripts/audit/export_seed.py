"""Per seed: export state_dict (float32) and 8-image reference tensors (trained 8.4 model, Hardswish, raw head outputs) for the container equivalence gate."""
import sys, torch, numpy as np, torch.nn as nn
from pathlib import Path
from PIL import Image
from ultralytics import YOLO
H = Path.home() / "dfxisp_eval_20261007"; D = H / "v2_data"; Q = H / "v2_quant"
for tag in sys.argv[1:]:
    y = YOLO(str(H / f"v2_runs/{tag}/weights/last.pt")).model.float().eval()
    torch.save({"state_dict": {k: v.float() for k, v in y.state_dict().items()}, "names": y.names, "nc": 3}, Q / f"{tag}_state.pt")
    def swap(m):
        for n, c in list(m.named_children()):
            if isinstance(c, nn.SiLU): setattr(m, n, nn.Hardswish(inplace=False))
            else: swap(c)
    swap(y); h = y.model[-1]; h.export = True; raw = {}
    for i in range(h.nl):
        h.cv2[i].register_forward_hook(lambda m, a, o, i=i: raw.__setitem__(("b", i), o)); h.cv3[i].register_forward_hook(lambda m, a, o, i=i: raw.__setitem__(("c", i), o))
    ps = sorted((D / "night/lowlight/images/val").glob("*.png"))[:3] + sorted((D / "night/normal/images/val").glob("*.png"))[:3] + sorted((D / "day/images/val").glob("*.png"))[:2]
    ref = []
    for p in ps:
        x = torch.from_numpy(np.asarray(Image.open(p).convert("RGB")).astype(np.float32).transpose(2, 0, 1)[None] / 255.0)
        with torch.no_grad(): y(x)
        ref.append((p.name, x, [raw[(k, i)].clone() for i in range(3) for k in ("b", "c")]))
    torch.save(ref, Q / f"equiv_ref_{tag}.pt"); print("EXPORTED", tag, len(ref))
