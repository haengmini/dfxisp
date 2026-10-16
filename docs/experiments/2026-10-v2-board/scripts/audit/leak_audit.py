"""Scene-leak audit using the already-converted 1368x912 12-bit RAW bins (laptop). Thumbnails = 2x2-binned same-colour planes block-averaged to 57x38, log-gain normalized.
Reports: nearest-neighbour similarity of each TEST frame to existing train/val, versus frame-number distance."""
import json, numpy as np
from pathlib import Path
H = Path.home() / "dfxisp_eval_20261007"
def thumb(p):
    a = np.fromfile(p, dtype="<u2").reshape(912, 1368).astype(np.float32)
    g = (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4   # 456x684 luminance-ish
    t = g.reshape(38, 12, 57, 12).mean(axis=(1, 3))
    t = np.log1p(t); t = (t - t.mean()) / (t.std() + 1e-6)
    return t.ravel()
test = [x["stem"] for x in json.loads((H / "phaseA_pil/frames.json").read_text()) if x["split"] == "night"]
tr = sorted(p.stem for p in (H / "sep_20261012/ft_hw/train/raw_bin").glob("*.bin"))
va = sorted(p.stem for p in (H / "sep_20261012/ft_hw/val/raw_bin").glob("*.bin"))
TT = {s: thumb(H / "hw1368/LOD/raw_bin" / f"{s}.bin") for s in test}
TR = {s: thumb(H / "sep_20261012/ft_hw/train/raw_bin" / f"{s}.bin") for s in tr}
VA = {s: thumb(H / "sep_20261012/ft_hw/val/raw_bin" / f"{s}.bin") for s in va}
num = lambda s: int(s[3:])
def corr(a, b): return float(np.dot(a, b) / len(a))
rows = []
for name, pool in [("train", TR), ("val", VA)]:
    keys = list(pool)
    M = np.stack([pool[k] for k in keys])
    for s, t in TT.items():
        c = M @ t / len(t); i = int(np.argmax(c)); rows.append((name, s, keys[i], float(c[i]), abs(num(s) - num(keys[i]))))
# baseline: similarity among test frames themselves (different scenes mostly)
tk = list(TT); TM = np.stack([TT[k] for k in tk]); S = TM @ TM.T / TM.shape[1]; np.fill_diagonal(S, -1)
out = {"test_vs_trainval_nn_corr": {}, "buckets": {}}
for name in ("train", "val"):
    r = [x for x in rows if x[0] == name]; cs = np.array([x[3] for x in r]); dd = np.array([x[4] for x in r])
    out["test_vs_trainval_nn_corr"][name] = {"median": float(np.median(cs)), "p90": float(np.percentile(cs, 90)), "frac_ge_0.9": float((cs >= 0.9).mean()), "frac_ge_0.8": float((cs >= 0.8).mean()),
        "nn_frame_number_distance_median": float(np.median(dd)), "frac_nn_within_10_frames": float((dd <= 10).mean())}
# similarity vs frame distance buckets (test vs all train)
keys = list(TR); M = np.stack([TR[k] for k in keys]); bucket = {"0-2": [], "3-10": [], "11-50": [], "51+": []}
for s, t in TT.items():
    c = M @ t / len(t)
    for k, v in zip(keys, c):
        d = abs(num(s) - num(k)); bucket["0-2" if d <= 2 else "3-10" if d <= 10 else "11-50" if d <= 50 else "51+"].append(float(v))
out["buckets"] = {b: {"n": len(v), "median_corr": (float(np.median(v)) if v else None), "p90": (float(np.percentile(v, 90)) if v else None)} for b, v in bucket.items()}
out["test_vs_test_nn_corr_median"] = float(np.median(S.max(axis=1)))
out["counts"] = {"test": len(test), "train": len(tr), "val": len(va)}
print(json.dumps(out, indent=1))
(H / "expanded_scope_20261014").mkdir(exist_ok=True); (H / "expanded_scope_20261014/leak_audit.json").write_text(json.dumps(out, indent=1))
print("LEAK_AUDIT_DONE")
