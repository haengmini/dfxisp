"""Numerical equivalence gate: container-side Raw (8.3.0 + patched head) vs the trained Ultralytics 8.4 model on the same 8 dev images. Run in the container; reference tensors come from a host file."""
import sys, numpy as np, torch
from pathlib import Path
from PIL import Image
sys.argv = ["x", "none", "A_full_s0"]
src = open("/work/quant_v2.py").read(); ns = {}; exec(src[:src.index("def load(p)")], ns)
sd = torch.load("/work/A_full_s0_state.pt")["state_dict"]
m = ns["Raw"](sd)
ref = torch.load("/work/equiv_ref.pt")
worst = 0.0
for name, x, outs in ref:
    with torch.no_grad(): got = m(x)
    for g, r in zip(got, outs): worst = max(worst, float((g - r).abs().max()))
print("max abs diff over", len(ref), "images x 6 tensors:", worst)
assert worst < 1e-3, worst
print("EQUIV_PASS")
