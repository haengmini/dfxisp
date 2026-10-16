"""SSD 3-seed board analysis (DPU-only replay of the SAME 400 PNGs): board vs host INT8 per seed, seeds vs deployed SSD (old), Lowlight-Normal per model.
Test-frame sampling uncertainty (paired frame bootstrap) and training-seed variation reported separately."""
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
TAGS = {"old": "old", "s0": "SSD_A_full_s0", "s1": "SSD_A_full_s1", "s2": "SSD_A_full_s2"}
B = {k: load(Q / f"ssd_board/ssd_{v}_board.jsonl") for k, v in TAGS.items()}
for k, D in B.items(): assert len(D["normal"]) == 200 and len(D["lowlight"]) == 200, k
print("board vs host INT8 detections:")
for k in ("s0", "s1", "s2"):
    h = json.loads((Q / f"host_int8_ssd_dets_{TAGS[k]}.json").read_text()); ident = tot = nb = nh = 0; md = 0.0
    for arm in ("normal", "lowlight"):
        for key, r in B[k][arm].items():
            b = np.array(r["detections"], dtype=np.float64).reshape(-1, 6); x = np.array(h[arm][key]["detections"], dtype=np.float64).reshape(-1, 6); tot += 1; nb += len(b); nh += len(x)
            if len(b) == len(x):
                if len(b) == 0: ident += 1
                else:
                    o1 = np.lexsort((b[:, 0], -b[:, 4])); o2 = np.lexsort((x[:, 0], -x[:, 4])); d = float(np.abs(b[o1] - x[o2]).max()); md = max(md, d); ident += int(d < 1e-3)
    print(f"  {k}: identical images {ident}/{tot}; detections board {nb} host {nh}; max abs diff {md:.4f}")
chk = BF.CHK; keys_all = sorted(B["old"]["normal"])
def rec(D, arm, k): a = arm if arm != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); r = D[a][k]; return {"width": r["width"], "height": r["height"], "detections": r["detections"]}
CACHE = {}
def items(tag, arm, ks):
    out = []
    for k in ks:
        key = (tag, arm, k)
        if key not in CACHE: CACHE[key] = BF.per_image(rec(B[tag], arm, k), k)
        out.append(CACHE[key])
    return out
rng = np.random.default_rng(20261016); NB = 400; res = {}
print("\n%-15s %8s | %8s %8s %8s | %8s %8s | new-old (95%% frame CI) per seed" % ("SSD BOARD INT8", "old", "s0", "s1", "s2", "mean", "sd"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    ks = [k for k in keys_all if k.split("_")[0] in parts]; idx = [rng.integers(0, len(ks), len(ks)) for _ in range(NB)]
    for arm in ("normal", "lowlight", "adaptive"):
        sc = {t: BF.agg(items(t, arm, ks)) for t in B}; sd_ = [sc["s0"], sc["s1"], sc["s2"]]; cis = []
        for t in ("s0", "s1", "s2"):
            n_, o_ = items(t, arm, ks), items("old", arm, ks); bs = np.array([BF.agg([n_[i] for i in ix]) - BF.agg([o_[i] for i in ix]) for ix in idx]); cis.append((sc[t] - sc["old"], *np.percentile(bs, [2.5, 97.5])))
        res[f"{sub}_{arm}"] = {"old": sc["old"], "seeds": sd_, "mean": float(np.mean(sd_)), "sd": float(np.std(sd_, ddof=1)), "ci": [list(map(float, c)) for c in cis]}
        print("%-15s %8.4f | %8.4f %8.4f %8.4f | %8.4f %8.4f | %s" % (f"{sub}_{arm}", sc["old"], *sd_, np.mean(sd_), np.std(sd_, ddof=1), "  ".join("%+.3f[%+.3f,%+.3f]" % c for c in cis)), flush=True)
    ln = {}
    for t in ("old", "s0", "s1", "s2"):
        a_, b_ = items(t, "lowlight", ks), items(t, "normal", ks); bs = np.array([BF.agg([a_[i] for i in ix]) - BF.agg([b_[i] for i in ix]) for ix in idx]); pt = BF.agg(a_) - BF.agg(b_); ln[t] = (float(pt), *map(float, np.percentile(bs, [2.5, 97.5])))
    res[f"{sub}_lowlight_minus_normal"] = ln; print("   %s Lowlight-Normal: " % sub + "  ".join("%s %+.4f[%+.4f,%+.4f]" % (t, *v) for t, v in ln.items()), flush=True)
(Q / "ssd_board/analysis3.json").write_text(json.dumps(res, indent=1)); print("SSD_ANALYSIS_DONE")
