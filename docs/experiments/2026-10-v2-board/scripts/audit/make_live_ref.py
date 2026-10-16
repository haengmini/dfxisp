"""Build live_ref.json: per (arm,key) the sha256 of the PC reference RGB in the BOARD's packed format (<u4 of R<<16|G<<8|B), exactly as coco_board_rgb_check.py compared.
Also verifies the smoke frames against the earlier board-verified hashes (normal PASCAL/2014_000018 and lowlight BLC16 LOD/DSC01133)."""
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
Q = Path('/home/mini/dfxisp_eval_20261007/v2_quant'); man = json.loads((Q / 'test_rgb/manifest.json').read_text()); out = []
for r in man:
    rgb = np.asarray(Image.open(Q / 'test_rgb' / r['file']).convert('RGB'))
    packed = ((rgb[:, :, 0].astype(np.uint32) << 16) | (rgb[:, :, 1].astype(np.uint32) << 8) | rgb[:, :, 2]).astype('<u4').tobytes()
    out.append({'arm': r['arm'], 'key': r['key'], 'board_rgb_sha256': hashlib.sha256(packed).hexdigest(), 'w': rgb.shape[1], 'h': rgb.shape[0]})
d = {(o['arm'], o['key']): o['board_rgb_sha256'] for o in out}
n = d[('normal', 'day_2014_000018')]; l = d[('lowlight', 'night_DSC01133')]
print('smoke normal', n == '2707fa5db9412d69fb881b8b93c034254d3fa442c2173e24bd0ba9dee39fddf2', '| smoke lowlight BLC16', l == '80d130cb7d6a4baaa925f8155bfe11939d2bd820124745a51f7f438a0bbeb08a')
assert n == '2707fa5db9412d69fb881b8b93c034254d3fa442c2173e24bd0ba9dee39fddf2' and l == '80d130cb7d6a4baaa925f8155bfe11939d2bd820124745a51f7f438a0bbeb08a'
Path('/tmp/live_ref.json').write_text(json.dumps(out)); print('refs', len(out))
