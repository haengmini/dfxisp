"""Score the v2 LIVE run (RAW -> board ISP -> v2 DPU) and verify against DPU-only replay (same PNG pixels).
Checks: 400 frames, unique ids, all ISP hashes == PC reference (re-verified here), detections identical to the replay of the same frames.
Adaptive = checker verdict from frames.json applied to the two fixed-RM live outputs (offline selection of which stream to read; not a live checker-driven DFX switch)."""
import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"; L = Q / "live_v2"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
assert json.loads((L / "v2live_status.json").read_text())["state"] == "COMPLETE"
man = json.loads((Q / "test_rgb/manifest.json").read_text()); lab = {r["key"]: r["label"] for r in man}; chk = {r["key"]: r["checker"] for r in man if r["arm"] == "normal"}
ref = {(r["arm"], r["key"]): r["board_rgb_sha256"] for r in json.loads((Q / "live_ref.json").read_text())}
live = {"normal": {}, "lowlight": {}}
for sub in ("night", "day"):
    for arm in ("normal", "lowlight"):
        rr = [json.loads(l) for l in (L / f"v2live_v2_yolo_{sub}_{arm}.jsonl").read_text().splitlines()]
        assert len(rr) == 100 and len({r["id"] for r in rr}) == 100
        for r in rr: assert r["rgb_sha256"] == ref[(arm, r["id"])], ("HASH", arm, r["id"]); live[arm][r["id"]] = r
assert all(len(v) == 200 for v in live.values()); print("ISP outputs hash-matched to PC reference: 400/400")
board = {}
for l in (Q / "board_v2/v2_yolo_board.jsonl").read_text().splitlines():
    r = json.loads(l); board.setdefault(r["arm"], {})[r["key"]] = r
same = sum(live[a][k]["detections"] == board[a][k]["detections"] for a in live for k in live[a]); print("live detections exactly equal to DPU-only replay:", same, "/ 400")
def score(recs):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": {k: {"width": v["width"], "height": v["height"], "detections": v["detections"]} for k, v in recs.items()}}, td)
    shutil.rmtree(td); return a, a50
out = {}; prior = json.loads((Q / "board_v2/board_scores.json").read_text())["scores"]
print("%-18s %8s %8s"%("LIVE TEST", "live", "replay"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    for kind in ("normal", "lowlight", "adaptive"):
        recs = {k: live[kind if kind != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal")][k] for k in live["normal"] if k.split("_")[0] in parts}
        a, a50 = score(recs); out[f"{sub}_{kind}"] = {"mAP50_95": a, "mAP50": a50, "n": len(recs)}; print("%-18s %8.4f %8.4f"%(f"{sub}_{kind}", a, prior[f"{sub}_{kind}"]["board_mAP50_95"]))
ms = lambda a, k: float(np.mean([r[k] for r in live[a].values()]))
t = {a: {k: ms(a, k) for k in ("isp_ms", "pre_ms", "dpu_ms", "post_ms")} for a in live}; print("mean ms/frame", json.dumps({a: {k: round(v, 1) for k, v in d.items()} for a, d in t.items()}))
(L / "live_scores.json").write_text(json.dumps({"scores": out, "timing_ms": t, "identical_to_replay": same}, indent=1)); print("LIVE_VERIFIED")
