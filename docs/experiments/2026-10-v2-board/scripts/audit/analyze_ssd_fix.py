"""SSD SE-fix board analysis. Board DPU replay of the SAME 400 PNGs with the SE fix (fc2 fix-point cap 8) vs the unfixed control (same calibration), old and 3 new seeds.
(1) board vs host INT8 (hostg_dets) agreement per config; (2) mAP50-95 per subset/arm; (3) new-old and Lowlight-Normal with paired frame bootstrap."""
import json, sys
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
sys.path.insert(0, str(H)); import bootstrap_fast as BF
def load(p):
    d = {}
    for l in Path(p).read_text().splitlines():
        r = json.loads(l); d.setdefault(r["arm"], {})[r["key"]] = r
    return d
TAGS = {"old0": "fix_old_k0", "old8": "fix_old_k8", "s0": "fix_s0_k8", "s1": "fix_s1_k8", "s2": "fix_s2_k8"}
HOST = {"old0": "old_k0", "old8": "old_k8", "s0": "SSD_A_full_s0_k8", "s1": "SSD_A_full_s1_k8", "s2": "SSD_A_full_s2_k8"}
B = {k: load(Q / f"ssd_fixboard/ssd_{v}_board.jsonl") for k, v in TAGS.items()}
for k, D in B.items(): assert len(D["normal"]) == 200 and len(D["lowlight"]) == 200, k
print("board vs host INT8 detections (same xmodel recipe):")
for k in TAGS:
    h = json.loads((Q / f"hostg_dets_{HOST[k]}.json").read_text()); ident = tot = 0; md = 0.0
    for arm in ("normal", "lowlight"):
        for key, r in B[k][arm].items():
            b = np.array(r["detections"], dtype=np.float64).reshape(-1, 6); x = np.array(h[arm][key]["detections"], dtype=np.float64).reshape(-1, 6); tot += 1
            if len(b) == len(x):
                if len(b) == 0: ident += 1
                else:
                    o1 = np.lexsort((b[:, 0], -b[:, 4])); o2 = np.lexsort((x[:, 0], -x[:, 4])); d = float(np.abs(b[o1] - x[o2]).max()); md = max(md, d); ident += int(d < 1e-3)
    print(f"  {k:5s}: identical images {ident}/{tot}; max abs diff {md:.4f}")
chk = BF.CHK; keys_all = sorted(B["old0"]["normal"])
def rec(D, arm, k): a = arm if arm != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); r = D[a][k]; return {"width": r["width"], "height": r["height"], "detections": r["detections"]}
CACHE = {}
def items(tag, arm, ks):
    out = []
    for k in ks:
        key = (tag, arm, k)
        if key not in CACHE: CACHE[key] = BF.per_image(rec(B[tag], arm, k), k)
        out.append(CACHE[key])
    return out
rng = np.random.default_rng(20261017); NB = 400; res = {}
print("\n%-15s %8s %8s | %8s %8s %8s | %8s %8s | new(fixed)-old(fixed) 95%% CI per seed" % ("SSD BOARD", "old-nofix", "old-fix", "s0", "s1", "s2", "mean", "sd"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    ks = [k for k in keys_all if k.split("_")[0] in parts]; idx = [rng.integers(0, len(ks), len(ks)) for _ in range(NB)]
    for arm in ("normal", "lowlight", "adaptive"):
        sc = {t: BF.agg(items(t, arm, ks)) for t in B}; sd_ = [sc["s0"], sc["s1"], sc["s2"]]; cis = []
        for t in ("s0", "s1", "s2"):
            n_, o_ = items(t, arm, ks), items("old8", arm, ks); bs = np.array([BF.agg([n_[i] for i in ix]) - BF.agg([o_[i] for i in ix]) for ix in idx]); cis.append((sc[t] - sc["old8"], *np.percentile(bs, [2.5, 97.5])))
        res[f"{sub}_{arm}"] = {"old_nofix": sc["old0"], "old_fix": sc["old8"], "seeds": sd_, "mean": float(np.mean(sd_)), "sd": float(np.std(sd_, ddof=1)), "ci": [list(map(float, c)) for c in cis]}
        print("%-15s %8.4f %8.4f | %8.4f %8.4f %8.4f | %8.4f %8.4f | %s" % (f"{sub}_{arm}", sc["old0"], sc["old8"], *sd_, np.mean(sd_), np.std(sd_, ddof=1), "  ".join("%+.3f[%+.3f,%+.3f]" % c for c in cis)), flush=True)
    ln = {}
    for t in ("old8", "s0", "s1", "s2"):
        a_, b_ = items(t, "lowlight", ks), items(t, "normal", ks); bs = np.array([BF.agg([a_[i] for i in ix]) - BF.agg([b_[i] for i in ix]) for ix in idx]); pt = BF.agg(a_) - BF.agg(b_); ln[t] = (float(pt), *map(float, np.percentile(bs, [2.5, 97.5])))
    res[f"{sub}_lowlight_minus_normal"] = ln; print("   %s Lowlight-Normal: " % sub + "  ".join("%s %+.4f[%+.4f,%+.4f]" % (t, *v) for t, v in ln.items()), flush=True)
(Q / "ssd_fixboard/analysis_fix.json").write_text(json.dumps(res, indent=1)); print("SSD_FIX_ANALYSIS_DONE")
