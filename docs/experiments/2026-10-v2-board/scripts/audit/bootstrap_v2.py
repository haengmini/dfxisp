"""Paired frame bootstrap for v2 results (board eval_map scorer). Test frames only. Uses dets dumped by eval_v2.py (dets_test_<tag>.json).
Comparisons: (a) trained seed-mean-free per-seed model vs base on the SAME frames, same ISP arm; (b) Lowlight - Normal within each model (the ISP question).
This quantifies TEST-FRAME sampling uncertainty only. Training-seed variation is reported separately as the sd across the three seeds."""
import contextlib, io, json, os, shutil, sys, tempfile
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
NB = int(sys.argv[1]) if len(sys.argv) > 1 else 200
fr = json.loads((H / "phaseA_pil/frames.json").read_text()); LAB = {}
for r in fr:
    d = "LOD" if r["split"] == "night" else "PASCAL"; LAB[f"{r['split']}_{r['stem']}"] = str(H / "hw1368" / d / "labels" / f"{r['stem']}.txt")
chk = {f"{r['split']}_{r['stem']}": r["checker"] for r in fr}
def ev(recs, idx):
    td = tempfile.mkdtemp(); data = {"classes": ["person", "car", "bicycle"], "images": {}}
    for j, i in enumerate(idx):
        k = keys[i]; kk = f"{k}#{j}"; data["images"][kk] = recs[k]; Path(td, kk + ".txt").write_text(Path(LAB[k]).read_text())
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate(data, td)
    shutil.rmtree(td); return a
D = {t: json.loads((H / "v2_eval" / f"dets_test_{t}.json").read_text()) for t in ["base_hswish", "A_full_s0", "A_full_s1", "A_full_s2"]}
rng = np.random.default_rng(20261014); out = {}
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    keys = [k for k in D["base_hswish"]["normal"] if k.split("_")[0] in parts]
    idxs = [rng.integers(0, len(keys), len(keys)) for _ in range(NB)]
    full = np.arange(len(keys))
    def curve(tag, arm):
        recs = D[tag]["normal"] if arm == "normal" else D[tag]["lowlight"]
        if arm == "adaptive": recs = {k: D[tag]["lowlight" if chk[k] == "lowlight" else "normal"][k] for k in keys}
        return recs
    res = {}
    for tag in ["A_full_s0", "A_full_s1", "A_full_s2"]:
        for arm in ("normal", "lowlight", "adaptive"):
            a, b = curve(tag, arm), curve("base_hswish", arm)
            pt = ev(a, full) - ev(b, full); bs = [ev(a, ix) - ev(b, ix) for ix in idxs]
            res[f"{tag}:{arm}:model_minus_base"] = (pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
        a, b = curve(tag, "lowlight"), curve(tag, "normal")
        pt = ev(a, full) - ev(b, full); bs = [ev(a, ix) - ev(b, ix) for ix in idxs]
        res[f"{tag}:lowlight_minus_normal"] = (pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
    a, b = curve("base_hswish", "lowlight"), curve("base_hswish", "normal"); pt = ev(a, full) - ev(b, full); bs = [ev(a, ix) - ev(b, ix) for ix in idxs]
    res["base:lowlight_minus_normal"] = (pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
    out[sub] = res
    for k, (p, lo, hi) in res.items(): print(f"{sub:6s} {k:42s} {p:+.4f} [{lo:+.4f}, {hi:+.4f}]", flush=True)
(H / "v2_eval" / "bootstrap_v2.json").write_text(json.dumps(out, indent=1)); print("BOOT_DONE", NB)
