"""DPU-only replay of the SAME 400 PNGs (already on board in /tmp/v2_dpu_replay/images) for extra seeds. Usage: python board_replay_seed.py A_full_s1 [A_full_s2]
Same code path as board_replay_v2.py; models are verified by sha256 from seeds.json. No ISP/DFXC/guard access."""
from pathlib import Path
import json, hashlib, time, sys
import numpy as np
from PIL import Image
sys.path.insert(0, '/home/root/exp/app')
import run_detector as RD
RD._have_cv2 = lambda: False
assert hashlib.sha256(Path(RD.__file__).read_bytes()).hexdigest() == '5b228c310ee6bed2e4affe090caee3e205521e8703be0027c59d01df3fb3d756'
O = Path('/tmp/v2_dpu_replay'); man = json.loads((O / 'replay_manifest.json').read_text()); assert len(man) == 400
seeds = json.loads((O / 'seeds.json').read_text()); status = {'state': 'RUNNING', 'tags': sys.argv[1:], 'done': {}}
def ws(): (O / 'status_seeds.json').write_text(json.dumps(status))
for tag in sys.argv[1:]:
    mp = O / 'models' / f'v2_yolo_{tag}.xmodel'; assert hashlib.sha256(mp.read_bytes()).hexdigest() == seeds[tag], tag
    runner = RD.DpuSubgraphRunner(str(mp)); assert runner.in_dims == (1, 640, 640, 3)
    outp = O / f'{tag}_board.jsonl'; done = set()
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
            x = RD.preprocess(img, 640, 'unit'); t = time.perf_counter(); outs = runner.run(x); ms = (time.perf_counter() - t) * 1000
            shp = sorted((a.shape[1], a.shape[-1]) for a in outs.values()); assert shp == [(20, 3), (20, 64), (40, 3), (40, 64), (80, 3), (80, 64)], shp
            dd = RD.yolov8_postprocess(outs, 640, 3, .001, .45)
            dets = [[float(b[0]*w/640), float(b[1]*h/640), float(b[2]*w/640), float(b[3]*h/640), float(b[4]), int(b[5])] for b in dd]
            f.write(json.dumps({'id': rid, 'key': r['key'], 'arm': r['arm'], 'width': w, 'height': h, 'dpu_ms': ms, 'detections': dets}) + '\n'); f.flush()
            status['done'][tag] = i + 1
            if (i + 1) % 50 == 0: ws(); print('REPLAY', tag, i + 1, flush=True)
    del runner
    status['done'][tag] = 400; ws()
status['state'] = 'COMPLETE'; ws(); print('SEEDS_REPLAY_COMPLETE', flush=True)
