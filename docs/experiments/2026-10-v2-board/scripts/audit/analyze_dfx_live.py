"""DFX live analysis: checker-driven RM selection, 4 DPU models on the same ISP output, 600 frames.
- verifies: all frames present, board RGB hashes (re-checked), per-frame RM
- scores each model per subset (night/day/mixed/mixed_blocks) with the board scorer
- compares live DFX with fixed-RM (normal/lowlight) replay scores of the same models and with the offline 'adaptive' number
- RM switch counts / per-frame times; paired frame bootstrap (DFX vs Normal, DFX vs Lowlight) per model"""
import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"; L = Q / "dfx_live"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
sys.path.insert(0, str(H)); import bootstrap_fast as BF
assert json.loads((L / "dfxlive_status.json").read_text())["state"] == "COMPLETE"
ref = {(r["arm"], r["key"]): r["board_rgb_sha256"] for r in json.loads((Q / "live_ref.json").read_text())}
SUBS = ("night", "day", "mixed", "mixed_blocks"); TAGS = ("old", "s0", "s1", "s2")
meta = {s: [json.loads(l) for l in (L / f"dfxlive_dfx_meta_{s}.jsonl").read_text().splitlines()] for s in SUBS}
assert [len(meta[s]) for s in SUBS] == [100, 100, 200, 200]
for s in SUBS:
    for m in meta[s]: assert m["rgb_sha256"] == ref[(m["arm"], m["id"])], ("HASH", s, m["id"])
print("board RGB == PC reference on all 600 frames")
live = {t: {s: {} for s in SUBS} for t in TAGS}
for t in TAGS:
    for s in SUBS:
        rr = [json.loads(l) for l in (L / f"dfxlive_dfx_{t}_{s}.jsonl").read_text().splitlines()]; assert len(rr) == len(meta[s])
        for r, m in zip(rr, meta[s]): assert r["id"] == m["id"] and r["rm"] == m["rm"]
        live[t][s] = rr
def load(p):
    d = {}
    for l in Path(p).read_text().splitlines():
        r = json.loads(l); d.setdefault(r["arm"], {})[r["key"]] = r
    return d
FIX = {"old": load(Q / "old_board/old_yolo_board.jsonl"), "s0": load(Q / "board_v2/v2_yolo_board.jsonl"), "s1": load(Q / "seeds_board/A_full_s1_board.jsonl"), "s2": load(Q / "seeds_board/A_full_s2_board.jsonl")}
man = {r["key"]: r for r in json.loads((Q / "test_rgb/manifest.json").read_text())}; lab = {k: v["label"] for k, v in man.items()}
chk = BF.CHK
# frames repeat across subsets (mixed contains night+day frames; mixed_blocks reorders): keys are unique per (subset, frame)
def score_recs(recs):
    td = tempfile.mkdtemp(); recs2 = {}
    for j, (k, r) in enumerate(recs):
        kk = f"{k}#{j}"; shutil.copyfile(lab[k], f"{td}/{kk}.txt"); recs2[kk] = {"width": r["width"], "height": r["height"], "detections": r["detections"]}
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": recs2}, td)
    shutil.rmtree(td); return a, a50
def live_recs(t, s): return [(m["id"], r) for r, m in zip(live[t][s], meta[s])]
def fixed_recs(t, arm, s): return [(m["id"], FIX[t][arm][m["id"]]) for m in meta[s]]
def checker_offline(t, s): return [(m["id"], FIX[t]["lowlight" if chk[m["id"]] == "lowlight" else "normal"][m["id"]]) for m in meta[s]]
res = {}
print("\n%-13s %-4s | %8s %8s %8s %8s | live-offline" % ("subset", "mdl", "Normal", "Lowlight", "DFX live", "offline"))
for s in SUBS:
    for t in TAGS:
        n = score_recs(fixed_recs(t, "normal", s))[0]; lo = score_recs(fixed_recs(t, "lowlight", s))[0]; dl = score_recs(live_recs(t, s))[0]; of = score_recs(checker_offline(t, s))[0]
        res[f"{s}_{t}"] = {"normal": n, "lowlight": lo, "dfx_live": dl, "offline": of}
        print("%-13s %-4s | %8.4f %8.4f %8.4f %8.4f | %+.4f" % (s, t, n, lo, dl, of, dl - of), flush=True)
print("\nRM selection and timing:")
for s in SUBS:
    rm = [m["rm"] for m in meta[s]]; sw = sum(1 for a, b in zip(rm, rm[1:]) if a != b)
    ck_match = sum(1 for m in meta[s] if (m["arm"] == "lowlight") == (chk[m["id"]] == "lowlight"))
    print(f"  {s:13s} lowlight frames {sum(rm)}/{len(rm)} | RM switches {sw} | live RM == offline checker choice {ck_match}/{len(rm)} | isp_ms normal {np.mean([m['isp_ms'] for m in meta[s] if m['rm']==0] or [0]):.1f} lowlight {np.mean([m['isp_ms'] for m in meta[s] if m['rm']==1] or [0]):.1f} | scan_ms {np.mean([m['scan_ms'] for m in meta[s]]):.1f}")
    res[f"{s}_rm"] = {"lowlight_frames": sum(rm), "switches": sw, "match_offline": ck_match}
rng = np.random.default_rng(20261016); NB = 300; print("\nPaired frame bootstrap, DFX live minus fixed RM (mAP50-95):")
for s in ("night", "mixed"):
    n = len(meta[s]); idx = [rng.integers(0, n, n) for _ in range(NB)]
    def its(recs): return [BF.per_image({"width": r["width"], "height": r["height"], "detections": r["detections"]}, k) for k, r in recs]
    for t in TAGS:
        D = its(live_recs(t, s)); N = its(fixed_recs(t, "normal", s)); Lw = its(fixed_recs(t, "lowlight", s))
        for nm, X in (("Normal", N), ("Lowlight", Lw)):
            bs = np.array([BF.agg([D[i] for i in ix]) - BF.agg([X[i] for i in ix]) for ix in idx]); pt = BF.agg(D) - BF.agg(X)
            res[f"{s}_{t}_dfx_minus_{nm}"] = [float(pt), *map(float, np.percentile(bs, [2.5, 97.5]))]
            print(f"  {s:6s} {t:3s} DFX-{nm:8s} {pt:+.4f} [{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]", flush=True)
(L / "dfx_live_analysis.json").write_text(json.dumps(res, indent=1)); print("DFX_ANALYSIS_DONE")
