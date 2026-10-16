"""Day replay set from Stanford PASCALRAW piece aa (600x400 camera JPG + XML). Laptop. Anti-forgetting replay ONLY (not ISP-domain day data).
Excludes any id within +-3 of a TEST day id. Seeded split by contiguous-id clusters (gap<=1). Pre-resizes to 640x640 stretch with the SAME PIL BILINEAR as the board path."""
import json, random, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
H = Path.home() / "dfxisp_eval_20261007"; D = H / "pascalraw_dl"; O = H / "v2_data" / "day"
test = {x["stem"] for x in json.loads((H / "phaseA_pil/frames.json").read_text()) if x["split"] == "day"}
assert len(test) == 100
tn = {int(s.split("_")[1]) for s in test}; near = {x for t in tn for x in range(t - 3, t + 4)}
ids = [f"2014_{i:06d}" for i in range(1, 4260)]
cand = [s for s in ids if int(s.split("_")[1]) not in near]
rnd = random.Random(20261014); rnd.shuffle(cand); sel = sorted(cand[:1100])
clusters, cur = [], [sel[0]]
for a, b in zip(sel, sel[1:]):
    if int(b.split("_")[1]) - int(a.split("_")[1]) <= 1: cur.append(b)
    else: clusters.append(cur); cur = [b]
clusters.append(cur); rnd.shuffle(clusters)
val, tr = [], []
for c in clusters: (val if len(val) < 200 else tr).extend(c)
print("candidates", len(cand), "selected", len(sel), "train", len(tr), "val", len(val), "overlap test", len(set(sel) & test))
assert not (set(sel) & test)
raw = O / "raw"; raw.mkdir(parents=True, exist_ok=True)
names = [f"PASCALRAW/jpg/{s}.jpg" for s in sel] + [f"PASCALRAW/annotations/{s}.xml" for s in sel]
(O / "names.txt").write_text("\n".join(names))
subprocess.run(f"gzip -dc {D}/PASCALRAW.tar.gzaa 2>/dev/null | tar -x -C {raw} -T {O}/names.txt 2>/dev/null; true", shell=True, check=True)
CL = {"person": 0, "car": 1, "bicycle": 2}
def conv(s):
    r = ET.parse(raw / "PASCALRAW/annotations" / f"{s}.xml").getroot(); w = float(r.findtext("size/width")); h = float(r.findtext("size/height")); L = []
    for o in r.findall("object"):
        n = o.findtext("name", "").strip()
        if n not in CL: continue
        b = o.find("bndbox"); x1, y1, x2, y2 = [float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1: continue
        L.append(f"{CL[n]} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}")
    return L
cnt = {"train": 0, "val": 0}; boxes = 0
for split, lst in (("train", tr), ("val", val)):
    (O / "images" / split).mkdir(parents=True, exist_ok=True); (O / "labels" / split).mkdir(parents=True, exist_ok=True)
    for s in lst:
        im = Image.open(raw / "PASCALRAW/jpg" / f"{s}.jpg").convert("RGB")
        im.resize((640, 640), Image.BILINEAR).save(O / "images" / split / f"day_{s}.png")
        L = conv(s); boxes += len(L)
        (O / "labels" / split / f"day_{s}.txt").write_text("\n".join(L) + ("\n" if L else "")); cnt[split] += 1
(O / "split.json").write_text(json.dumps({"train": tr, "val": val}))
print("DONE", cnt, "boxes", boxes)
