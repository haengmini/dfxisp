import os, sys, json
from pathlib import Path
import numpy as np
os.environ.setdefault("RESIZE", "pil")
H = Path.home() / "dfxisp_eval_20261007"; R = H / "sep_20261012"
sys.path.insert(0, str(H)); sys.path.insert(0, str(R)); sys.path.insert(0, str(Path.home() / "Desktop/dfxisp/isppipeline/sw"))
import lowlight_isp_pipeline as PW
import exp5_lowlight_wb as X5
G = PW.G
print("repo golden constants: BLC", G.BLC_LEVEL12, "mul", G.BLC_MUL_Q8, "WB", G.WB_R_Q8, G.WB_G_Q8, G.WB_B_Q8, "gain?", getattr(G, "GAIN_Q8", None))
tot = 0; diff = 0; mx = 0; per = []
for p in sorted((R / "ft_hw/val/raw_bin").glob("*.bin"))[:12]:
    raw = np.fromfile(p, dtype="<u2").reshape(912, 1368)
    a = PW.run_arm(raw.astype(np.uint16) << 4, 1368, 912, "lowlight_isp"); b = X5.render_one(raw, blc=16)
    d = np.abs(a.astype(int) - b.astype(int)); tot += d.size; diff += int((d > 0).sum()); mx = max(mx, int(d.max())); per.append(float((d > 0).mean() * 100))
print("frames 12 pixels differing %.4f%% max %d  per-frame pct range %.4f..%.4f" % (diff / tot * 100, mx, min(per), max(per)))
# which source is closer to the exp7 'board_blc16' emulation that was run on the board?
emu_dir = R / "board_blc16/raw_bin"
print("board_blc16 bins exist", len(list(emu_dir.glob("*.bin"))))
