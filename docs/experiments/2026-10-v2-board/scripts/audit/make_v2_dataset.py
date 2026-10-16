"""Build the v2 balanced training dataset (laptop). Ultralytics layout; images are PRE-RESIZED to 640x640 with the board contract
(plain stretch, PIL BILINEAR) so training/validation geometry == board geometry (LetterBox on a square 640 image is the identity).
Night: RAW12 bin -> NormalISP (1368x912) and LowlightISP BLC16/257 (684x456, repo golden = board RM) -> 640 stretch.
Day: pre-built replay (camera JPG stretch 640) from prep_day_replay.py.  Test frames are never touched.
Usage: make_v2_dataset.py selftest | build"""
import json, os, random, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"; R = H / "sep_20261012"; OUT = H / "v2_data"
sys.path.insert(0, str(Path.home() / "Desktop/dfxisp/isppipeline/sw"))
import default_isp_pipeline as PD
import lowlight_isp_pipeline as PW
G = PW.G
assert G.BLC_LEVEL12 == 16 and G.BLC_MUL_Q8 == 257, ("repo golden is not BLC16/257", G.BLC_LEVEL12, G.BLC_MUL_Q8)

def render(raw12):
    raw16 = raw12.astype(np.uint16) << 4
    return {"normal": PD.run_arm(raw16, 1368, 912, "default_isp"), "lowlight": PW.run_arm(raw16, 1368, 912, "lowlight_isp")}

def to640(a): return Image.fromarray(a).resize((640, 640), Image.BILINEAR)

def one(job):
    split, stem, binp, labp = job
    raw = np.fromfile(binp, dtype="<u2"); assert raw.size == 1368 * 912 and raw.max() <= 4095
    imgs = render(raw.reshape(912, 1368)); lab = Path(labp).read_text()
    for arm, im in imgs.items():
        d = OUT / "night" / arm
        (d / "images" / split).mkdir(parents=True, exist_ok=True); (d / "labels" / split).mkdir(parents=True, exist_ok=True)
        to640(im).save(d / "images" / split / f"{stem}.png"); (d / "labels" / split / f"{stem}.txt").write_text(lab)
    return stem

def pool_jobs():
    """existing train359/val60 stay as-is; new pool split by contiguous blocks of 20 selected frames (every 6th block -> val),
    new-train frames within +-3 frame numbers of any new-val frame are dropped (burst leakage guard)."""
    jobs = []
    for s in ("train", "val"):
        for p in sorted((R / "ft_hw" / s / "raw_bin").glob("*.bin")):
            jobs.append((s, p.stem, str(p), str(R / "ft_hw" / s / "labels" / f"{p.stem}.txt")))
    new = json.loads((R / "ft_hw_v2/selection.json").read_text())["selected"]; num = lambda x: int(x[3:])
    blocks = [new[i:i + 20] for i in range(0, len(new), 20)]
    val = [s for bi, b in enumerate(blocks) if bi % 6 == 5 for s in b]; vn = {num(s) for s in val}
    tr = [s for bi, b in enumerate(blocks) if bi % 6 != 5 for s in b if not any(abs(num(s) - v) <= 3 for v in vn)]
    for split, lst in (("train", tr), ("val", val)):
        for s in lst:
            jobs.append((split, s, str(R / "ft_hw_v2/raw_bin" / f"{s}.bin"), str(R / "ft_hw_v2/labels" / f"{s}.txt")))
    return jobs, len(new), len(tr), len(val)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "selftest":
        import time; p = sorted((R / "ft_hw/val/raw_bin").glob("*.bin"))[0]; raw = np.fromfile(p, dtype="<u2").reshape(912, 1368)
        t = time.time(); im = render(raw); print("render s", round(time.time() - t, 2), {k: v.shape for k, v in im.items()})
        assert im["normal"].shape == (912, 1368, 3) and im["lowlight"].shape == (456, 684, 3)
        sys.path.insert(0, str(H)); sys.path.insert(0, str(R)); os.environ.setdefault("RESIZE", "pil")
        import exp5_lowlight_wb as X5
        ref = X5.render_one(raw, blc=16); d = np.abs(ref.astype(int) - im["lowlight"].astype(int))
        # authority = repo golden (BLC16/257), which the board RM was verified against; exp5 render_one rounds gain differently (<=1 LSB)
        print("lowlight repo-golden vs exp5 render_one(blc=16): max diff", int(d.max()), "differing px %.1f%%" % ((d > 0).mean() * 100))
        assert d.max() <= 1; print("SELFTEST_PASS")
    else:
        jobs, n_new, n_tr, n_val = pool_jobs(); print("new pool", n_new, "new train", n_tr, "new val", n_val, "total jobs", len(jobs), flush=True)
        with Pool(8) as p:
            for i, s in enumerate(p.imap_unordered(one, jobs, chunksize=4), 1):
                if i % 200 == 0: print(i, "/", len(jobs), flush=True)
        stats = {}
        for arm in ("normal", "lowlight"):
            for sp in ("train", "val"):
                stats[f"{arm}_{sp}"] = len(list((OUT / "night" / arm / "images" / sp).glob("*.png")))
        print("BUILD_DONE", stats, "day", {sp: len(list((OUT / "day/images" / sp).glob("*.png"))) for sp in ("train", "val")})
