"""Paired comparison on the board: EXISTING deployed INT8 (yolov8n_dpu.xmodel) vs NEW v2 INT8 (seed0), same 400 lossless PNGs, same DPU path, same postprocess/scorer.
Reports mAP50-95/mAP50, per-class AP, and a paired frame bootstrap (new - old) per subset and ISP arm, plus Lowlight-Normal within each model. Test-frame sampling uncertainty only (one seed)."""
import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
sys.path.insert(0, str(H)); import bootstrap_fast as BF
man = json.loads((Q / "test_rgb/manifest.json").read_text()); lab = {r["key"]: r["label"] for r in man}
def load(p):
    d = {}
    for l in Path(p).read_text().splitlines():
        r = json.loads(l); d.setdefault(r["arm"], {})[r["key"]] = r
    return d
OLD = load(Q / "old_board/old_yolo_board.jsonl"); NEW = load(Q / "board_v2/v2_yolo_board.jsonl")
for D in (OLD, NEW): assert len(D["normal"]) == 200 and len(D["lowlight"]) == 200
assert set(OLD["normal"]) == set(NEW["normal"])
chk = BF.CHK; keys_all = sorted(OLD["normal"])
def rec(D, arm, k): a = arm if arm != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); r = D[a][k]; return {"width": r["width"], "height": r["height"], "detections": r["detections"]}
CACHE = {}
def items(tag, D, arm, ks):
    out = []
    for k in ks:
        key = (tag, arm, k)
        if key not in CACHE: CACHE[key] = BF.per_image(rec(D, arm, k), k)
        out.append(CACHE[key])
    return out
def full_score(D, arm, ks):
    td = tempfile.mkdtemp()
    for k in ks: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": {k: rec(D, arm, k) for k in ks}}, td)
    shutil.rmtree(td); return a, a50
rng = np.random.default_rng(20261015); NB = 400; res = {}
print("%-16s %9s %9s %9s  %-26s" % ("BOARD INT8", "old", "new", "new-old", "paired 95% CI (frames)"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    ks = [k for k in keys_all if k.split("_")[0] in parts]; idx = [rng.integers(0, len(ks), len(ks)) for _ in range(NB)]
    for arm in ("normal", "lowlight", "adaptive"):
        o, o50 = full_score(OLD, arm, ks); n, n50 = full_score(NEW, arm, ks)
        io_, in_ = items("old", OLD, arm, ks), items("new", NEW, arm, ks)
        pt = BF.agg(in_) - BF.agg(io_); bs = np.array([BF.agg([in_[i] for i in ix]) - BF.agg([io_[i] for i in ix]) for ix in idx]); lo, hi = np.percentile(bs, [2.5, 97.5])
        res[f"{sub}_{arm}"] = {"old": o, "new": n, "old50": o50, "new50": n50, "diff": n - o, "ci": [float(lo), float(hi)]}
        print("%-16s %9.4f %9.4f %+9.4f  [%+.4f, %+.4f]" % (f"{sub}_{arm}", o, n, n - o, lo, hi), flush=True)
    for name, D, tag in (("old", OLD, "old"), ("new", NEW, "new")):
        a_, b_ = items(tag, D, "lowlight", ks), items(tag, D, "normal", ks)
        pt = BF.agg(a_) - BF.agg(b_); bs = np.array([BF.agg([a_[i] for i in ix]) - BF.agg([b_[i] for i in ix]) for ix in idx]); lo, hi = np.percentile(bs, [2.5, 97.5])
        res[f"{sub}_lowlight_minus_normal_{name}"] = {"diff": float(pt), "ci": [float(lo), float(hi)]}
        print("   %s Lowlight-Normal (%s model): %+.4f [%+.4f, %+.4f]" % (sub, name, pt, lo, hi), flush=True)
# per-class AP, night lowlight
def per_class(D, arm, ks):
    it = items("pc", D, arm, ks) if False else [BF.per_image(rec(D, arm, k), k) for k in ks]; out = []
    for c in range(3):
        n_gt = sum(i[c][2] for i in it); tp = np.concatenate([i[c][0] for i in it], axis=1); conf = np.concatenate([i[c][1] for i in it])
        out.append(float(np.mean([EM.average_precision(tp[t], conf, n_gt) for t in range(len(BF.THR))])))
    return out
nk = [k for k in keys_all if k.startswith("night")]
for arm in ("normal", "lowlight"):
    po, pn = per_class(OLD, arm, nk), per_class(NEW, arm, nk); res[f"night_{arm}_perclass"] = {"old": po, "new": pn}
    print("night %-8s AP50-95 person/car/bicycle  old %s  new %s" % (arm, " ".join("%.3f" % x for x in po), " ".join("%.3f" % x for x in pn)))
tm = lambda D: {a: float(np.mean([r["dpu_ms"] for r in D[a].values()])) for a in D}
res["dpu_ms_mean"] = {"old": tm(OLD), "new": tm(NEW)}; print("mean runner.run ms/frame old", {a: round(v, 1) for a, v in tm(OLD).items()}, "new", {a: round(v, 1) for a, v in tm(NEW).items()})
(Q / "old_board/compare_old_new.json").write_text(json.dumps(res, indent=1)); print("COMPARE_DONE")
