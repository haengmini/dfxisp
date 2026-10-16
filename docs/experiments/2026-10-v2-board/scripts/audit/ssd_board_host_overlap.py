"""Is board-vs-host SSD INT8 disagreement just rounding-level differences in the raw head (so the detection lists differ only in low-score tails), rather than a pipeline bug?
Per-image: top-K (by score) detection overlap between board and host lists, and the mAP of each (done elsewhere). K=20 and score>=0.3.
Also reports how many detections each list has (the cap is 100 per image -> 120000 total for 1200 = 400 images x 300? check)."""
import json
from pathlib import Path
import numpy as np
Q = Path.home() / "dfxisp_eval_20261007" / "v2_quant"
def load(p):
    d = {}
    for l in Path(p).read_text().splitlines():
        r = json.loads(l); d.setdefault(r["arm"], {})[r["key"]] = r
    return d
def iou(a, b):
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1]); x2 = min(a[2], b[2]); y2 = min(a[3], b[3]); i = max(0, x2 - x1) * max(0, y2 - y1)
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)
for k, tag in (("s0", "SSD_A_full_s0"), ("s1", "SSD_A_full_s1"), ("s2", "SSD_A_full_s2")):
    B = load(Q / f"ssd_board/ssd_{tag}_board.jsonl"); Hh = json.loads((Q / f"host_int8_ssd_dets_{tag}.json").read_text())
    n_b = []; match = []; hi_b = hi_h = hi_m = 0
    for arm in ("normal", "lowlight"):
        for key, r in B[arm].items():
            b = [d for d in r["detections"] if d[4] >= 0.3]; h = [d for d in Hh[arm][key]["detections"] if d[4] >= 0.3]; hi_b += len(b); hi_h += len(h)
            used = set()
            for d in b:
                best = None
                for j, e in enumerate(h):
                    if j in used or int(e[5]) != int(d[5]): continue
                    v = iou(d, e)
                    if v >= 0.7 and (best is None or v > best[0]): best = (v, j)
                if best: used.add(best[1]); hi_m += 1
            n_b.append(len(r["detections"]))
    print(f"{k}: detections/image board {np.mean(n_b):.0f} (max {max(n_b)}) | score>=0.3: board {hi_b} host {hi_h}, matched(IoU>=.7 same class) {hi_m} -> {hi_m/max(hi_b,1):.3f} of board, {hi_m/max(hi_h,1):.3f} of host")
