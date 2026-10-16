import json, sys, io, contextlib, shutil, tempfile
from pathlib import Path
H = Path.home() / "dfxisp_eval_20261007"; Q = H / "v2_quant"
sys.path.insert(0, "/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2/app"); import eval_map as EM
man = json.loads((Q / "test_rgb/manifest.json").read_text()); lab = {r["key"]: r["label"] for r in man}
live = {"normal": {}, "lowlight": {}}
for sub in ("night", "day"):
    for arm in ("normal", "lowlight"):
        for l in (Q / f"live_v2/v2live_v2_yolo_{sub}_{arm}.jsonl").read_text().splitlines():
            r = json.loads(l); live[arm][r["id"]] = r
board = {}
for l in (Q / "board_v2/v2_yolo_board.jsonl").read_text().splitlines():
    r = json.loads(l); board.setdefault(r["arm"], {})[r["key"]] = r
def score(recs, order):
    td = tempfile.mkdtemp(); keys = [k for k in order if k in recs]
    for k in keys: shutil.copyfile(lab[k], f"{td}/{k}.txt")
    with contextlib.redirect_stdout(io.StringIO()): a50, a = EM.evaluate({"classes": ["person", "car", "bicycle"], "images": {k: {"width": recs[k]["width"], "height": recs[k]["height"], "detections": recs[k]["detections"]} for k in keys}}, td)
    shutil.rmtree(td); return a
ko = [r["key"] for r in man if r["arm"] == "normal"]; night_first = sorted(ko, key=lambda k: (k.startswith("day"), k)); day_first = sorted(ko, key=lambda k: (k.startswith("night"), k))
for arm in ("normal", "lowlight"):
    L = {k: live[arm][k] for k in ko}; B = {k: board[arm][k] for k in ko}
    print(arm, "mixed | live night-first %.4f day-first %.4f manifest-order %.4f | replay night-first %.4f day-first %.4f manifest-order %.4f" % (score(L, night_first), score(L, day_first), score(L, ko), score(B, night_first), score(B, day_first), score(B, ko)))
