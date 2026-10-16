"""Compare board DPU replay vs host INT8 on the SAME 400 lossless PNGs, then score board result (test: night/day/mixed x normal/lowlight/adaptive)."""
import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
import numpy as np
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
man = json.loads((Q / "test_rgb/manifest.json").read_text()); chk = {r["key"]: r["checker"] for r in man if r["arm"] == "normal"}
lab = {r["key"]: r["label"] for r in man}
board = {}
for l in (Q / "board_v2/v2_yolo_board.jsonl").read_text().splitlines():
    r = json.loads(l); board.setdefault(r["arm"], {})[r["key"]] = r
host = json.loads((Q / "host_int8_test_dets.json").read_text())
assert sum(len(v) for v in board.values()) == 400 and all(len(board[a]) == 200 for a in ("normal", "lowlight"))
# detection-level agreement
nd_b = nd_h = 0; ident = 0; maxdiff = 0.0; cnt_equal = 0
for arm in ("normal", "lowlight"):
    for k, r in board[arm].items():
        b = np.array(r["detections"], dtype=np.float64).reshape(-1, 6); h = np.array(host[arm][k]["detections"], dtype=np.float64).reshape(-1, 6)
        nd_b += len(b); nd_h += len(h)
        if len(b) == len(h):
            cnt_equal += 1
            if len(b):
                o1 = np.lexsort((b[:, 0], -b[:, 4])); o2 = np.lexsort((h[:, 0], -h[:, 4])); d = np.abs(b[o1] - h[o2]).max(); maxdiff = max(maxdiff, float(d)); ident += int(d < 1e-3)
            else: ident += 1
print("detections board", nd_b, "host", nd_h, "| images with equal detection count", cnt_equal, "/400 | images identical within 1e-3:", ident, "| max abs diff among equal-count", round(maxdiff, 4))
def score(recs):
    td = tempfile.mkdtemp()
    for k in recs: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": {k: {"width": v["width"], "height": v["height"], "detections": v["detections"]} for k, v in recs.items()}}, td)
    shutil.rmtree(td); return a, a50
res = {}; hs = json.loads((Q / "host_int8_test_scores.json").read_text()); fp = {t: json.loads((H / f"v2_eval/scores_{t}.json").read_text()) for t in ("A_full_s0", "base_hswish")}
print("%-18s %8s %8s %8s %8s"%("TEST mAP50-95", "FP32", "hostINT8", "board", "base FP32"))
for sub, parts in (("night", ["night"]), ("day", ["day"]), ("mixed", ["day", "night"])):
    for kind in ("normal", "lowlight", "adaptive"):
        recs = {}
        for k in board["normal"]:
            if k.split("_")[0] not in parts: continue
            arm = kind if kind != "adaptive" else ("lowlight" if chk[k] == "lowlight" else "normal"); recs[k] = board[arm][k]
        a, a50 = score(recs); res[f"{sub}_{kind}"] = {"board_mAP50_95": a, "board_mAP50": a50, "n": len(recs)}
        kk = f"test_{sub}_{kind}"; print("%-18s %8.4f %8.4f %8.4f %8.4f"%(f"{sub}_{kind}", fp["A_full_s0"][kk]["mAP50_95"], hs[kk]["mAP50_95"], a, fp["base_hswish"][kk]["mAP50_95"]))
dp = np.mean([r["dpu_ms"] for a in board.values() for r in a.values()]); print("mean DPU ms/frame", round(dp, 1))
(Q / "board_v2/board_scores.json").write_text(json.dumps({"scores": res, "dpu_ms_mean": dp, "det_board": nd_b, "det_host": nd_h, "identical_images": ident, "equal_count_images": cnt_equal}, indent=1))
