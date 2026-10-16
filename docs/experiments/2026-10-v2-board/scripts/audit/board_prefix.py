#!/usr/bin/env python3
"""Board side: run each prefix xmodel (single DPU output) on the SAME int8 input as the deployed s0 diag (images 0 and 2 of diag_inputs.npz). Saves raw int8 output per stage. DPU-only.
usage: board_prefix.py <stage> [<stage> ...]   (xmodel at /tmp/v2_dpu_replay/prefix/pre_<stage>.xmodel, sha in prefix/SHA256SUMS)"""
import os, sys, hashlib, subprocess, urllib.request
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/root/exp/app')
import run_detector as RD
RD._have_cv2 = lambda: False
O = Path('/tmp/v2_dpu_replay'); X = np.load(O / 'diag_inputs.npz')['X']
sums = dict(l.split()[::-1] for l in (O / 'prefix/SHA256SUMS').read_text().splitlines() if l.strip())
out = {}
for st in sys.argv[1:]:
    p = O / f'prefix/pre_{st}.xmodel'; assert hashlib.sha256(p.read_bytes()).hexdigest() == sums[f'pre_{st}.xmodel'], st
    r = RD.DpuSubgraphRunner(str(p)); assert r.in_dims == (1, 320, 320, 3) and len(r.out_ts) == 1, (st, r.in_dims, len(r.out_ts))
    print(st, 'out', [(t.name[-40:], list(t.dims), t.get_attr('fix_point')) for t in r.out_ts], flush=True)
    for i in (0, 2):
        q = np.clip(np.round(X[i].transpose(1, 2, 0) * r.in_scale), -128, 127).astype(np.int8)
        o = np.empty(tuple(r.out_ts[0].dims), dtype=np.int8, order='C'); jid = r.runner.execute_async([np.ascontiguousarray(q.reshape(r.in_dims))], [o]); r.runner.wait(jid)
        out[f'{st}_{i}'] = o[0].copy(); out[f'{st}_in{i}'] = q
    del r
f = O / ('diag_prefix_' + '_'.join(sys.argv[1:]) + '.npz'); np.savez(f, **out)
b = f.read_bytes(); urllib.request.urlopen(urllib.request.Request(os.environ['BOARD_CHANNEL_URL'] + '/up/' + f.name, data=b), timeout=60); print('POSTED', f.name, len(b), {k: v.shape for k, v in out.items() if 'in' not in k})
