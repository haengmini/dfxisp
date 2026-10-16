"""3-seed board analysis (DPU-only replay of the same 400 PNGs). Test-frame sampling uncertainty (paired frame bootstrap) AND training-seed variation, reported separately.
Checks: board == host INT8 per seed (detections), per-seed new-old vs the existing deployed INT8 model, seed mean/sd, Lowlight-Normal per seed."""
import json, sys, io, contextlib, shutil, tempfile
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
B = {"old": load(Q / "old_board/old_yolo_board.jsonl"), "s0": load(Q / "board_v2/v2_yolo_board.jsonl"), "s1": load(Q / "seeds_board/A_full_s1_board.jsonl"), "s2": load(Q / "seeds_board/A_full_s2_board.jsonl")}
HOST = {"s0": Q / "host_int8_test_dets.json", "s1": Q / "host_int8_test_dets_A_full_s1.json", "s2": Q / "host_int8_test_dets_A_full_s2.json"}
for t, D in B.items(): assert len(D["normal"]) == 200 and len(D["lowlight"]) == 200, t
print("board vs host INT8 detections, per seed:")
for t, p in HOST.items():
    h = json.loads(p.read_text()); ident = tot = 0; md = 0.0
    for arm in ("normal", "lowlight"):
        for k, r in B[t][arm].items():
            b = np.array(r["detections"], dtype=np.float64).reshape(-1, 6); x = np.array(h[arm][k]["detections"], dtype=np.float64).reshape(-1, 6); tot += 1
            if len(b) == len(x):
                if len(b) == 0: ident += 1
                else:
                    o1 = np.lexsort((b[:, 0], -b[:, 4])); o2 = np.lexsort((x[:, 0], -x[:, 4])); d = float(np.abs(b[o1] - x[o2]).max()); md = max(md, d); ident += int(d < 1e-3)
    print(f"  {t}: identical images {ident}/{tot}, max abs diff {md:.4f}")
chk = BF.CHK; keys_all = sorted(B["old"]["normal"])
def rec(D, arm, k): a = arm if arm != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); r = D[a][k]; return {"width": r["width"], "height": r["height"], "detections": r["detections"]}
lab = {}
for r in json.loads((Q / "test_rgb/manifest.json").read_text()): lab[r["key"]] = r["label"]
CACHE = {}
def items(tag, arm, ks):
    out = []
    for k in ks:
        key = (tag, arm, k)
        if key not in CACHE: CACHE[key] = BF.per_image(rec(B[tag], arm, k), k)
        out.append(CACHE[key])
    return out
rng = np.random.default_rng(20261015); NB = 400; res = {}
print("\n%-15s %8s | %8s %8s %8s | %8s %8s | seed new-old (95%% frame CI)" % ("BOARD INT8", "old", "s0", "s1", "s2", "mean", "sd"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    ks = [k for k in keys_all if k.split("_")[0] in parts]; idx = [rng.integers(0, len(ks), len(ks)) for _ in range(NB)]; full = list(range(len(ks)))
    for arm in ("normal", "lowlight", "adaptive"):
        sc = {t: BF.agg(items(t, arm, ks)) for t in B}; sd_ = [sc["s0"], sc["s1"], sc["s2"]]
        cis = []
        for t in ("s0", "s1", "s2"):
            n_, o_ = items(t, arm, ks), items("old", arm, ks); bs = np.array([BF.agg([n_[i] for i in ix]) - BF.agg([o_[i] for i in ix]) for ix in idx]); cis.append((sc[t] - sc["old"], *np.percentile(bs, [2.5, 97.5])))
        res[f"{sub}_{arm}"] = {"old": sc["old"], "seeds": sd_, "mean": float(np.mean(sd_)), "sd": float(np.std(sd_, ddof=1)), "ci": [list(map(float, c)) for c in cis]}
        print("%-15s %8.4f | %8.4f %8.4f %8.4f | %8.4f %8.4f | %s" % (f"{sub}_{arm}", sc["old"], *sd_, np.mean(sd_), np.std(sd_, ddof=1), "  ".join("%+.3f[%+.3f,%+.3f]" % c for c in cis)), flush=True)
    ln = {}
    for t in ("old", "s0", "s1", "s2"):
        a_, b_ = items(t, "lowlight", ks), items(t, "normal", ks); bs = np.array([BF.agg([a_[i] for i in ix]) - BF.agg([b_[i] for i in ix]) for ix in idx]); pt = BF.agg(a_) - BF.agg(b_); ln[t] = (float(pt), *map(float, np.percentile(bs, [2.5, 97.5])))
    res[f"{sub}_lowlight_minus_normal"] = ln
    print("   %s Lowlight-Normal: " % sub + "  ".join("%s %+.4f[%+.4f,%+.4f]" % (t, *v) for t, v in ln.items()), flush=True)
    # pooled across seeds: average the three per-seed paired differences within each bootstrap replicate
    pb = []
    for ix in idx: pb.append(np.mean([BF.agg([items(t, "lowlight", ks)[i] for i in ix]) - BF.agg([items(t, "normal", ks)[i] for i in ix]) for t in ("s0", "s1", "s2")]))
    pt = np.mean([ln[t][0] for t in ("s0", "s1", "s2")]); res[f"{sub}_lowlight_minus_normal_seedmean"] = [float(pt), *map(float, np.percentile(pb, [2.5, 97.5]))]
    print("   %s Lowlight-Normal seed-mean: %+.4f [%+.4f,%+.4f] (frame resampling, 3 fixed models)" % (sub, pt, *np.percentile(pb, [2.5, 97.5])), flush=True)
(Q / "seeds_board/analysis3.json").write_text(json.dumps(res, indent=1)); print("ANALYSIS_DONE")
