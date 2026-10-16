"""Render the TEST frames (night100 LOD, day100 PASCAL; hw1368 bins) with NormalISP and LowlightISP BLC16 (repo golden = board RM) to LOSSLESS PNG once.
Same RGB files feed (1) host INT8 evaluation, (2) board DPU-only replay -> any difference is quantization or DPU, never rendering.
Writes manifest.json with sha256 per image and the label path. Test frames are never used for training/calibration/selection."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"; O = H / "v2_quant" / "test_rgb"
sys.path.insert(0, str(Path.home() / "Desktop/dfxisp/isppipeline/sw"))
import default_isp_pipeline as PD
import lowlight_isp_pipeline as PW
assert PW.G.BLC_LEVEL12 == 16 and PW.G.BLC_MUL_Q8 == 257
fr = json.loads((H / "phaseA_pil/frames.json").read_text()); man = []
for arm in ("normal", "lowlight"): (O / arm).mkdir(parents=True, exist_ok=True)
for r in fr:
    d = "LOD" if r["split"] == "night" else "PASCAL"; key = f"{r['split']}_{r['stem']}"
    raw = np.fromfile(H / "hw1368" / d / "raw_bin" / f"{r['stem']}.bin", dtype="<u2").reshape(912, 1368); r16 = raw.astype(np.uint16) << 4
    for arm, mod, name in (("normal", PD, "default_isp"), ("lowlight", PW, "lowlight_isp")):
        img = mod.run_arm(r16, 1368, 912, name); p = O / arm / f"{key}.png"; Image.fromarray(img).save(p)
        man.append({"key": key, "split": r["split"], "arm": arm, "checker": r["checker"], "file": f"{arm}/{key}.png", "w": img.shape[1], "h": img.shape[0],
                    "sha256": hashlib.sha256(img.tobytes()).hexdigest(), "label": f"/home/mini/dfxisp_eval_20261007/hw1368/{d}/labels/{r['stem']}.txt"})
(O / "manifest.json").write_text(json.dumps(man))
sz = sum(p.stat().st_size for p in O.rglob("*.png"))
print("images", len(man), "bytes", sz, "MB", round(sz / 1e6, 1), "normal", sum(m["arm"] == "normal" for m in man), "lowlight", sum(m["arm"] == "lowlight" for m in man))
