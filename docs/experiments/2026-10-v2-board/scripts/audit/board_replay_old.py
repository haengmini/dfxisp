"""DPU-only replay of the SAME 400 lossless PNGs through the EXISTING deployed yolov8n_dpu.xmodel (project baseline INT8, sha256 6713fbad...).
Identical code path to board_replay_v2.py (same preprocess = PIL BILINEAR via run_detector with cv2 disabled, same postprocess); only the model file and output name differ.
No ISP/DFXC/guard access. The baseline model has 2 DPU subgraphs (DFL on DPU); DpuSubgraphRunner uses the first (backbone+head conv) exactly as the deployed app does, outputs asserted to be the same 6 raw tensors."""
from pathlib import Path
import json, hashlib, time
import numpy as np
from PIL import Image
import sys
O = Path(__file__).parent; sys.path.insert(0, '/home/root/exp/app')
import run_detector as RD
RD._have_cv2 = lambda: False
assert hashlib.sha256(Path(RD.__file__).read_bytes()).hexdigest() == '5b228c310ee6bed2e4affe090caee3e205521e8703be0027c59d01df3fb3d756'
man = json.loads((O / 'replay_manifest.json').read_text()); assert len(man) == 400
mp = Path('/home/root/exp/models/yolov8n_dpu.xmodel'); assert hashlib.sha256(mp.read_bytes()).hexdigest() == '6713fbad2065a6b15e627b334633912c24cf691748455b9c7b82f8f269698817'
status = {'state': 'RUNNING', 'scope': 'DPU-only RGB replay, EXISTING baseline model; no ISP/DFXC/guard access', 'done': 0}
def ws(): (O / 'status_old.json').write_text(json.dumps(status))
ws(); runner = RD.DpuSubgraphRunner(str(mp)); assert runner.in_dims == (1, 640, 640, 3), runner.in_dims
outp = O / 'old_yolo_board.jsonl'; done = set()
if outp.exists():
    for l in outp.read_text().splitlines():
        try: done.add(json.loads(l)['id'])
        except Exception: pass
with outp.open('a') as f:
    for i, r in enumerate(man):
        rid = r['arm'] + ':' + r['key']
        if rid in done: continue
        assert hashlib.sha256((O / r['rgb']).read_bytes()).hexdigest() == r['png_sha256']
        img = np.asarray(Image.open(O / r['rgb']).convert('RGB')); h, w = img.shape[:2]
        x = RD.preprocess(img, 640, 'unit')
        t = time.perf_counter(); outs = runner.run(x); ms = (time.perf_counter() - t) * 1000
        shp = sorted((a.shape[1], a.shape[-1]) for a in outs.values()); assert shp == [(20, 3), (20, 64), (40, 3), (40, 64), (80, 3), (80, 64)], shp
        dd = RD.yolov8_postprocess(outs, 640, 3, .001, .45)
        dets = [[float(b[0]*w/640), float(b[1]*h/640), float(b[2]*w/640), float(b[3]*h/640), float(b[4]), int(b[5])] for b in dd]
        f.write(json.dumps({'id': rid, 'key': r['key'], 'arm': r['arm'], 'width': w, 'height': h, 'dpu_ms': ms, 'detections': dets}) + '\n'); f.flush()
        status['done'] = i + 1
        if (i + 1) % 25 == 0: ws(); print('REPLAY', i + 1, flush=True)
status['state'] = 'COMPLETE'; ws(); print('REPLAY_COMPLETE', flush=True)
