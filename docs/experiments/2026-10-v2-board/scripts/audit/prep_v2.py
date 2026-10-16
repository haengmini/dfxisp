"""Expanded night training pool v2 (server). Drive Sony ARW -> HW contract 1368x912 12-bit RGGB .bin + labels, via the SAME build_hw_dataset.convert_one
(byte-parity with existing ft_hw verified by parity_check.py). New output dir; existing ft_hw untouched. Read-only Drive; ARW deleted after conversion.
Selection: seed 20261014 random 1200 from frames NOT in {existing train/val/test} and NOT within 3 frame numbers of a test frame.
Leak control by pixel similarity is applied afterwards on the converted bins (split script)."""
import json, random, sys, time
from pathlib import Path
sys.path.insert(0, "/opt/data/second-brain/20-projects/dfxisp/experiment-corpus-2026-10-07/laptop/home/mini/Desktop/dfxisp/isppipeline/hls/tools")
sys.path.insert(0, "/opt/data/work/dfxisp_sep_exp")
import build_hw_dataset as B
import prep_ft_data as P
A = Path("/opt/data/work/blc16_dfx_board_20261014/expanded_scope_audit")
OUT = Path("/opt/data/work/dfxisp_sep_exp/ft_hw_v2"); TMP = Path("/opt/data/work/dfxisp_sep_exp/ft_tmp_v2")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
used = json.loads((A / "night_used_ids.json").read_text())
num = lambda s: int(s[3:])
labels = {}
for n in ["raw_new_Sony_RX100m7_train.json", "raw_new_Sony_RX100m7_val.json", "raw_str_labeled_new_Sony_RX100m7_test.json"]:
    j = json.loads((A / "drive_labels" / n).read_text()); idm = {i["id"]: i for i in j["images"]}
    for i in j["images"]:
        labels[Path(i["file_name"]).stem] = {"w": i["width"], "h": i["height"], "boxes": []}
    for a in j["annotations"]:
        labels[Path(idm[a["image_id"]]["file_name"]).stem]["boxes"].append([a["bbox"], a["category_id"]])
assert all(v["w"] == 5472 and v["h"] == 3648 for v in labels.values()), "unexpected annotation size"
ex = set(used["test"]) | set(used["train"]) | set(used["val"])
tn = {num(s) for s in used["test"]}; near = {x for t in tn for x in range(t - 3, t + 4)}
cand = sorted(s for s in labels if s not in ex and num(s) not in near)
random.Random(20261014).shuffle(cand)
sel = sorted(cand[:N], key=num)
OUT.mkdir(exist_ok=True); TMP.mkdir(exist_ok=True)
(OUT / "selection.json").write_text(json.dumps({"seed": 20261014, "candidates": len(cand), "selected": sel}))
(OUT / "raw_bin").mkdir(exist_ok=True); (OUT / "labels").mkdir(exist_ok=True)
d = P.svc(); files = P.list_sony(d); miss = [s for s in sel if s not in files]
print("candidates", len(cand), "selected", len(sel), "missing on drive", len(miss), flush=True); assert not miss
meta, t0 = [], time.time()
for n, k in enumerate(sel, 1):
    if (OUT / "raw_bin" / f"{k}.bin").exists() and (OUT / "labels" / f"{k}.txt").exists():
        continue
    src = TMP / f"{k}.ARW"
    for attempt in range(4):
        try: P.download(d, files[k]["id"], src); break
        except Exception as e: print("retry", k, attempt, type(e).__name__, flush=True); time.sleep(5)
    lab = labels[k]
    lines = [f"{P.CLS[c]} {(x + bw / 2) / lab['w']:.6f} {(y + bh / 2) / lab['h']:.6f} {bw / lab['w']:.6f} {bh / lab['h']:.6f}" for (x, y, bw, bh), c in lab["boxes"]]
    lp = TMP / f"{k}.txt"; lp.write_text("\n".join(lines) + "\n")
    m = B.convert_one(src, lp, OUT, 0.25, False); m["stem"] = k; meta.append(m)
    src.unlink(); lp.unlink()
    if n % 25 == 0 or n == len(sel):
        print(f"{n}/{len(sel)} {time.time() - t0:.0f}s", flush=True)
        (OUT / "meta_partial.json").write_text(json.dumps(meta))
nb = len(list((OUT / "raw_bin").glob("*.bin"))); nl = len(list((OUT / "labels").glob("*.txt")))
print("DONE bins", nb, "labels", nl); assert nb == len(sel) == nl
