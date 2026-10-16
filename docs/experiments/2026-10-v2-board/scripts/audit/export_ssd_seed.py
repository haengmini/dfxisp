"""Per SSD seed: export state_dict and 8-image reference tensors (trained torchvision model, raw head outputs) for the container equivalence gate."""
import sys, torch, numpy as np
from pathlib import Path
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"; D = H / "v2_data"
sys.path.insert(0, str(H)); import train_ssd_v2 as T
RD = T.RD
for s in sys.argv[1:]:
    tag = f"SSD_A_full_s{s}"; ck = torch.load(H / f"v2_runs/{tag}/last.pt", map_location="cpu", weights_only=False)
    torch.save({"model_state_dict": ck["model_state_dict"], "seed": int(s)}, Q / f"{tag}_ssd_state.pt")
    m = T.build(); m.load_state_dict(ck["model_state_dict"]); m.eval()
    ps = sorted((D / "night/lowlight/images/val").glob("*.png"))[:3] + sorted((D / "night/normal/images/val").glob("*.png"))[:3] + sorted((D / "day/images/val").glob("*.png"))[:2]
    ref = []
    for p in ps:
        x = torch.from_numpy(RD.preprocess(np.asarray(Image.open(p).convert("RGB")), 320, "pm1").transpose(2, 0, 1)[None].copy()).float()
        with torch.no_grad(): o = m.head(list(m.backbone(x).values()))
        ref.append((p.name, x, [o["bbox_regression"].clone(), o["cls_logits"].clone()]))
    torch.save(ref, Q / f"{tag}_ssd_ref.pt"); print("EXPORTED", tag, len(ref))
