"""Board package for the v2 YOLO DPU replay: the 400 pre-rendered TEST PNGs (identical files used for host INT8), the compiled xmodel, run_detector, common preprocess.
Board script = DPU-only (no ISP/DFXC/guard access). Detections use the project 3-class head directly (no COCO class map). 640 stretch via run_detector.preprocess with cv2 disabled (PIL BILINEAR) == board contract, same as eval_v2 and quantization."""
import hashlib, json, shutil, tarfile
from pathlib import Path
R = Path("/home/mini/dfxisp_eval_20261007"); Q = R / "v2_quant"; P = Q / "board_pkg_v2"; C = R / "common_dpu_pilot"
if P.exists(): shutil.rmtree(P)
P.mkdir(); (P / "models").mkdir()
shutil.copy2(C / "app/run_detector.py", P / "run_detector.py")
x = Q / "compiled/v2_yolo_A_s0.xmodel"; shutil.copy2(x, P / "models/v2_yolo_A_s0.xmodel")
(P / "model_hash.txt").write_text(hashlib.sha256(x.read_bytes()).hexdigest())
man = json.loads((Q / "test_rgb/manifest.json").read_text()); out = []
for r in man:
    dest = Path("images") / r["file"]; (P / dest).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(Q / "test_rgb" / r["file"], P / dest)
    out.append({"key": r["key"], "arm": r["arm"], "split": r["split"], "rgb": str(dest), "png_sha256": hashlib.sha256((P / dest).read_bytes()).hexdigest()})
assert len(out) == 400; (P / "replay_manifest.json").write_text(json.dumps(out))
(P / "board_replay_v2.py").write_text('''from pathlib import Path
import json, hashlib, time
import numpy as np
from PIL import Image
import run_detector as RD
RD._have_cv2 = lambda: False   # board rootfs has no cv2 -> PIL BILINEAR, identical to eval_v2/quant (NOT the COCO-pilot half-pixel preprocess)
O = Path(__file__).parent
man = json.loads((O / "replay_manifest.json").read_text()); assert len(man) == 400
mp = O / "models/v2_yolo_A_s0.xmodel"; assert hashlib.sha256(mp.read_bytes()).hexdigest() == (O / "model_hash.txt").read_text().strip()
status = {"state": "RUNNING", "scope": "DPU-only RGB replay; no ISP/DFXC/guard access", "done": 0}
def ws(): (O / "status.json").write_text(json.dumps(status))
ws(); runner = RD.DpuSubgraphRunner(str(mp)); assert runner.in_dims == (1, 640, 640, 3), runner.in_dims
# resume support: skip keys already written
outp = O / "v2_yolo_board.jsonl"; done = set()
if outp.exists():
    for l in outp.read_text().splitlines():
        try: done.add(json.loads(l)["id"])
        except Exception: pass
with outp.open("a") as f:
    for i, r in enumerate(man):
        rid = r["arm"] + ":" + r["key"]
        if rid in done: continue
        assert hashlib.sha256((O / r["rgb"]).read_bytes()).hexdigest() == r["png_sha256"]
        img = np.asarray(Image.open(O / r["rgb"]).convert("RGB")); h, w = img.shape[:2]
        x = RD.preprocess(img, 640, "unit")
        t = time.perf_counter(); outs = runner.run(x); ms = (time.perf_counter() - t) * 1000
        shp = sorted((a.shape[1], a.shape[-1]) for a in outs.values()); assert shp == [(20, 3), (20, 64), (40, 3), (40, 64), (80, 3), (80, 64)], shp
        dd = RD.yolov8_postprocess(outs, 640, 3, .001, .45)
        dets = [[float(b[0]*w/640), float(b[1]*h/640), float(b[2]*w/640), float(b[3]*h/640), float(b[4]), int(b[5])] for b in dd]
        f.write(json.dumps({"id": rid, "key": r["key"], "arm": r["arm"], "width": w, "height": h, "dpu_ms": ms, "detections": dets}) + "\\n"); f.flush()
        status["done"] = i + 1
        if (i + 1) % 25 == 0: ws(); print("REPLAY", i + 1, flush=True)
status["state"] = "COMPLETE"; ws(); print("REPLAY_COMPLETE", flush=True)
''')
T = Q / "board_pkg_v2.tar.gz"
with tarfile.open(T, "w:gz") as tar: tar.add(P, arcname="v2_dpu_replay")
sha = hashlib.sha256(T.read_bytes()).hexdigest(); (Q / "board_pkg_v2.sha256").write_text(sha)
print("archive bytes", T.stat().st_size, "MB", round(T.stat().st_size / 1e6, 1), "sha256", sha)
