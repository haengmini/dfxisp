import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
sys.path.insert(0, "/work/app")
import eval_map as EM
man = json.loads(Path("/work/test_rgb/manifest.json").read_text())
dets = json.loads(Path("/work/host_int8_test_dets.json").read_text())
lab = {r["key"]: r["label"].replace("/home/mini/dfxisp_eval_20261007/hw1368", "/hw") for r in man}
assert all(Path(p).exists() for p in lab.values()), [p for p in lab.values() if not Path(p).exists()][:3]
chk = {r["key"]: r["checker"] for r in man if r["arm"] == "normal"}
def score(recs):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": recs}, td)
    shutil.rmtree(td); return {"mAP50_95": a, "mAP50": a50, "n": len(recs)}
res = {}
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    for kind in ("normal", "lowlight", "adaptive"):
        recs = {}
        for k in dets["normal"]:
            if k.split("_")[0] not in parts: continue
            arm = kind if kind != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); recs[k] = dets[arm][k]
        res[f"test_{sub}_{kind}"] = score(recs); print(f"test_{sub}_{kind}", "%.4f %.4f n=%d" % (res[f"test_{sub}_{kind}"]["mAP50_95"], res[f"test_{sub}_{kind}"]["mAP50"], res[f"test_{sub}_{kind}"]["n"]))
Path("/work/host_int8_test_scores.json").write_text(json.dumps(res, indent=1)); print("RESCORE_DONE")
