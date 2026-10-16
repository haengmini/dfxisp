"""DPU-only replay of the SAME 400 lossless PNGs for SSDLite models: the deployed ssdlite_mbv3_dpu.xmodel ('old') and v2 seeds. Usage: python board_replay_ssd.py <tag> [<tag> ...]  (tags: old, SSD_A_full_s0, ...)
Same preprocess (PIL BILINEAR via run_detector, cv2 disabled) for 320 input, norm pm1; postprocess run_detector.ssdlite_postprocess(conf .001, iou .55, deployed anchors). No ISP/DFXC/guard access."""
from pathlib import Path
import json, hashlib, time, sys
import numpy as np
from PIL import Image
sys.path.insert(0, '/home/root/exp/app')
import run_detector as RD
RD._have_cv2 = lambda: False
assert hashlib.sha256(Path(RD.__file__).read_bytes()).hexdigest() == '5b228c310ee6bed2e4affe090caee3e205521e8703be0027c59d01df3fb3d756'
O = Path('/tmp/v2_dpu_replay'); man = json.loads((O / 'replay_manifest.json').read_text()); assert len(man) == 400
ANC = np.load('/home/root/exp/app/ssdlite_anchors.npy'); assert ANC.shape == (3234, 4)
M = json.loads((O / 'ssd_models.json').read_text())      # tag -> [path, sha256]
status = {'state': 'RUNNING', 'tags': sys.argv[1:], 'done': {}}
def ws(): (O / 'status_ssd.json').write_text(json.dumps(status))
for tag in sys.argv[1:]:
    path, sha = M[tag]; assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, tag
    runner = RD.DpuSubgraphRunner(path); assert runner.in_dims == (1, 320, 320, 3), runner.in_dims
    outp = O / f'ssd_{tag}_board.jsonl'; done = set()
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
            x = RD.preprocess(img, 320, 'pm1'); t = time.perf_counter(); outs = runner.run(x); ms = (time.perf_counter() - t) * 1000
            assert sorted(a.shape[-1] for a in outs.values()) == [4, 4] and all(a.shape == (1, 3234, 4) for a in outs.values())
            dd = RD.ssdlite_postprocess(outs, ANC, 320, .001, .55)
            dets = [[float(b[0]*w/320), float(b[1]*h/320), float(b[2]*w/320), float(b[3]*h/320), float(b[4]), int(b[5])] for b in dd]
            f.write(json.dumps({'id': rid, 'key': r['key'], 'arm': r['arm'], 'width': w, 'height': h, 'dpu_ms': ms, 'detections': dets}) + '\n'); f.flush()
            status['done'][tag] = i + 1
            if (i + 1) % 100 == 0: ws(); print('REPLAY', tag, i + 1, flush=True)
    del runner; status['done'][tag] = 400; ws()
status['state'] = 'COMPLETE'; ws(); print('SSD_REPLAY_COMPLETE', flush=True)
