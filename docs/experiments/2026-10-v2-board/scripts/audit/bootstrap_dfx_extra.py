"""Paired frame bootstrap of DFX live minus fixed-RM (Normal, Lowlight) for subsets day / mixed / mixed_blocks (the earlier analyses only did night and mixed).
Also DFX minus the better of the two fixed arms per resample ('best fixed'), to ask whether DFX adds anything beyond picking one RM for the whole set.
Applies to SSD (5 models) and YOLO (4 models) live runs. Saved measurement files only. usage: python bootstrap_dfx_extra.py"""
import json, sys
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app")
sys.path.insert(0, str(H)); import bootstrap_fast as BF
def load_fix(p):
    d = {}
    for l in Path(p).read_text().splitlines():
        r = json.loads(l); d.setdefault(r["arm"], {})[r["key"]] = r
    return d
CFG = {
    "SSD": dict(L=Q / "ssd_dfx_live", pre="ssddfx_", tags=("old", "oldfx", "s0", "s1", "s2"),
                FIX={"old": Q / "ssd_board/ssd_old_board.jsonl", "oldfx": Q / "ssd_fixboard/ssd_fix_old_k8_board.jsonl", "s0": Q / "ssd_fixboard/ssd_fix_s0_k8_board.jsonl",
                     "s1": Q / "ssd_fixboard/ssd_fix_s1_k8_board.jsonl", "s2": Q / "ssd_fixboard/ssd_fix_s2_k8_board.jsonl"}),
    "YOLO": dict(L=Q / "dfx_live", pre="dfxlive_", tags=("old", "s0", "s1", "s2"),
                 FIX={"old": Q / "old_board/old_yolo_board.jsonl", "s0": Q / "board_v2/v2_yolo_board.jsonl", "s1": Q / "seeds_board/A_full_s1_board.jsonl", "s2": Q / "seeds_board/A_full_s2_board.jsonl"}),
}
SUBS = ("day", "mixed", "mixed_blocks"); NB = 1000; out = {}
for name, c in CFG.items():
    L, pre, tags = c["L"], c["pre"], c["tags"]
    assert json.loads((L / f"{pre}status.json").read_text())["state"] == "COMPLETE", name
    FIX = {t: load_fix(p) for t, p in c["FIX"].items()}
    meta = {s: [json.loads(l) for l in (L / f"{pre}dfx_meta_{s}.jsonl").read_text().splitlines()] for s in SUBS}
    print(f"\n=== {name} live vs fixed RM, paired frame bootstrap (NB={NB}, seed fixed), mAP50-95 ===", flush=True)
    rng = np.random.default_rng(20261018)
    for s in SUBS:
        n = len(meta[s]); idx = [rng.integers(0, n, n) for _ in range(NB)]
        for t in tags:
            live = [json.loads(l) for l in (L / f"{pre}dfx_{t}_{s}.jsonl").read_text().splitlines()]
            assert len(live) == n and all(r["id"] == m["id"] for r, m in zip(live, meta[s]))
            def its(recs): return [BF.per_image({"width": r["width"], "height": r["height"], "detections": r["detections"]}, k) for k, r in recs]
            D = its([(m["id"], r) for r, m in zip(live, meta[s])]); N = its([(m["id"], FIX[t]["normal"][m["id"]]) for m in meta[s]]); Lw = its([(m["id"], FIX[t]["lowlight"][m["id"]]) for m in meta[s]])
            d, nn, ll = BF.agg(D), BF.agg(N), BF.agg(Lw)
            bs_n = np.array([BF.agg([D[i] for i in ix]) - BF.agg([N[i] for i in ix]) for ix in idx])
            bs_l = np.array([BF.agg([D[i] for i in ix]) - BF.agg([Lw[i] for i in ix]) for ix in idx])
            bs_b = np.array([BF.agg([D[i] for i in ix]) - max(BF.agg([N[i] for i in ix]), BF.agg([Lw[i] for i in ix])) for ix in idx])
            res = {k: [float(v), *map(float, np.percentile(b, [2.5, 97.5]))] for k, v, b in (("dfx_minus_normal", d - nn, bs_n), ("dfx_minus_lowlight", d - ll, bs_l), ("dfx_minus_bestfixed", d - max(nn, ll), bs_b))}
            res["scores"] = {"dfx": d, "normal": nn, "lowlight": ll}; out[f"{name}_{s}_{t}"] = res
            f = lambda k: "%+.4f[%+.4f,%+.4f]" % tuple(res[k])
            print(f"  {s:12s} {t:5s} dfx {d:.4f} N {nn:.4f} L {ll:.4f} | -N {f('dfx_minus_normal')} | -L {f('dfx_minus_lowlight')} | -best {f('dfx_minus_bestfixed')}", flush=True)
(Q / "dfx_extra_bootstrap.json").write_text(json.dumps(out, indent=1)); print("DFX_EXTRA_BOOTSTRAP_DONE")
