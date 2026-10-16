"""Parity gate: re-convert 3 already-used train ARW from Drive and require byte-identical .bin and identical remapped labels.
Also measures download + convert time. Read-only Drive; temp ARW deleted."""
import io, json, sys, time, hashlib, tempfile
from pathlib import Path
sys.path.insert(0, "/opt/data/second-brain/20-projects/dfxisp/experiment-corpus-2026-10-07/laptop/home/mini/Desktop/dfxisp/isppipeline/hls/tools")
sys.path.insert(0, "/opt/data/work/dfxisp_sep_exp")
import build_hw_dataset as B
import prep_ft_data as P
W = P.W
d = P.svc(); files = P.list_sony(d)
split = json.load(open(W / "ann/ft_split.json")); labels = json.load(open(W / "ann/ft_labels.json"))
sample = split["train"][:2] + split["val"][:1]
tmp = Path(tempfile.mkdtemp(dir="/opt/data/work/dfxisp_sep_exp/ft_tmp"))
for k in sample:
    s = "train" if k in split["train"] else "val"
    t0 = time.time(); src = tmp / f"{k}.ARW"; P.download(d, files[k]["id"], src); t1 = time.time()
    lab = labels[k]; lines = [f"{P.CLS[c]} {(x+bw/2)/lab['w']:.6f} {(y+bh/2)/lab['h']:.6f} {bw/lab['w']:.6f} {bh/lab['h']:.6f}" for (x, y, bw, bh), c in lab["boxes"]]
    lp = tmp / f"{k}.txt"; lp.write_text("\n".join(lines) + "\n")
    out = tmp / "out"; [(out / sub).mkdir(parents=True, exist_ok=True) for sub in ("raw_bin", "labels", "preview")]
    B.convert_one(src, lp, out, 0.25, False); t2 = time.time()
    new = (out / "raw_bin" / f"{k}.bin").read_bytes(); old = (W / "ft_hw" / s / "raw_bin" / f"{k}.bin").read_bytes()
    nl = (out / "labels" / f"{k}.txt").read_text(); ol = (W / "ft_hw" / s / "labels" / f"{k}.txt").read_text()
    print(k, s, "bin_identical", new == old, "label_identical", nl == ol, "dl %.1fs conv %.1fs" % (t1 - t0, t2 - t1), "size", len(new), flush=True)
    assert new == old and nl == ol, "PARITY FAIL"
    src.unlink()
import shutil; shutil.rmtree(tmp)
print("PARITY_PASS")
