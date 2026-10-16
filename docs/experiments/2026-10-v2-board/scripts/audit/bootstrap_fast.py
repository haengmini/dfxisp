"""Fast paired bootstrap (multiprocess, 16 cores). Precomputes per-image matched-detection statistics ONCE and resamples via recomputed AP from cached per-detection TP flags.
Equivalent to eval_map.evaluate (same IoU thresholds, greedy matching, all-point AP); verified against EM.evaluate on the full set before bootstrapping (must match to 1e-9)."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
THR = np.arange(0.5, 0.96, 0.05); NC = 3
fr = json.loads((H / "phaseA_pil/frames.json").read_text()); LAB = {}; CHK = {}
for r in fr:
    d = "LOD" if r["split"] == "night" else "PASCAL"; k = f"{r['split']}_{r['stem']}"
    LAB[k] = str(H / "hw1368" / d / "labels" / f"{r['stem']}.txt"); CHK[k] = r["checker"]
def per_image(rec, k):
    """-> per class: (tp[thr, n_det], conf[n_det], n_gt)"""
    w, h = rec["width"], rec["height"]; gt = EM.load_labels(str(Path(LAB[k]).parent), Path(LAB[k]).stem, w, h)
    dets = np.array(rec["detections"], dtype=np.float32).reshape(-1, 6); out = []
    for c in range(NC):
        g = gt[gt[:, 0] == c, 1:5]; d = dets[dets[:, 5] == c]; d = d[np.argsort(-d[:, 4])]
        ious = EM.iou_matrix(d[:, :4], g) if len(d) and len(g) else np.zeros((len(d), len(g)))
        tp = np.zeros((len(THR), len(d)), dtype=np.float32)
        for ti, thr in enumerate(THR):
            matched = np.zeros(len(g), dtype=bool)
            for i in range(len(d)):
                if len(g) == 0: break
                cand = np.where((ious[i] >= thr) & ~matched)[0]
                if len(cand): j = cand[np.argmax(ious[i, cand])]; matched[j] = True; tp[ti, i] = 1.0
        out.append((tp, d[:, 4].copy(), len(g)))
    return out
def agg(items):
    ap = np.full((len(THR), NC), np.nan)
    for c in range(NC):
        n_gt = sum(it[c][2] for it in items)
        tp = np.concatenate([it[c][0] for it in items], axis=1); conf = np.concatenate([it[c][1] for it in items])
        for ti in range(len(THR)): ap[ti, c] = EM.average_precision(tp[ti], conf, n_gt)
    return float(np.nanmean(ap))
def work(args):
    tag, arm, keys = args; D = json.loads((H / "v2_eval" / f"dets_test_{tag}.json").read_text()); res = {}
    for k in keys:
        a = arm if arm != "adaptive" else ("lowlight" if CHK[k] == "lowlight" else "normal"); res[k] = per_image(D[a][k], k)
    return tag, arm, res
if __name__ == "__main__":
    NB = int(sys.argv[1]); tags = ["base_hswish", "A_full_s0", "A_full_s1", "A_full_s2"]
    allk = list(json.loads((H / "v2_eval" / "dets_test_base_hswish.json").read_text())["normal"])
    jobs = [(t, a, allk) for t in tags for a in ("normal", "lowlight", "adaptive")]
    with Pool(12) as p: out = p.map(work, jobs)
    C = {(t, a): r for t, a, r in out}
    # verification against the board scorer on the full night set for one arm
    import contextlib, io, shutil, tempfile
    keys_n = [k for k in allk if k.startswith("night")]; D = json.loads((H / "v2_eval" / "dets_test_A_full_s0.json").read_text())["lowlight"]
    td = tempfile.mkdtemp(); [shutil.copyfile(LAB[k], f"{td}/{k}.txt") for k in keys_n]
    with contextlib.redirect_stdout(io.StringIO()): _, ref = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": {k: D[k] for k in keys_n}}, td)
    mine = agg([C[("A_full_s0", "lowlight")][k] for k in keys_n]); print("verify night/lowlight A_full_s0: board scorer %.10f fast %.10f" % (ref, mine)); assert abs(ref - mine) < 1e-9
    rng = np.random.default_rng(20261014); out = {}
    for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
        keys = [k for k in allk if k.split("_")[0] in parts]; idxs = [rng.integers(0, len(keys), len(keys)) for _ in range(NB)]
        def sc(t, a, ix): return agg([C[(t, a)][keys[i]] for i in ix])
        full = np.arange(len(keys)); res = {}
        def pair(name, fa, fb):
            pt = fa(full) - fb(full); bs = np.array([fa(ix) - fb(ix) for ix in idxs]); res[name] = (float(pt), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
            print(f"{sub:6s} {name:40s} {pt:+.4f} [{res[name][1]:+.4f}, {res[name][2]:+.4f}]", flush=True)
        for t in tags[1:]:
            for a in ("normal", "lowlight", "adaptive"): pair(f"{t}:{a}:minus_base", lambda ix, t=t, a=a: sc(t, a, ix), lambda ix, a=a: sc("base_hswish", a, ix))
            pair(f"{t}:lowlight_minus_normal", lambda ix, t=t: sc(t, "lowlight", ix), lambda ix, t=t: sc(t, "normal", ix))
        pair("base:lowlight_minus_normal", lambda ix: sc("base_hswish", "lowlight", ix), lambda ix: sc("base_hswish", "normal", ix))
        out[sub] = res
    (H / "v2_eval" / "bootstrap_v2.json").write_text(json.dumps({"NB": NB, "results": out}, indent=1)); print("BOOT_DONE", NB)
