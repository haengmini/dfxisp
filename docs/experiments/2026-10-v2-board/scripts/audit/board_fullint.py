#!/usr/bin/env python3
"""Board: run full (candidate) SSD xmodels on diag images 0 and 2; save int8 head outputs (cls, reg). usage: board_fullint.py <tag>:<path> ..."""
import os, sys, hashlib, urllib.request
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/root/exp/app')
import run_detector as RD
RD._have_cv2 = lambda: False
O = Path('/tmp/v2_dpu_replay'); X = np.load(O / 'diag_inputs.npz')['X']; out = {}
for spec in sys.argv[1:]:
    tag, path = spec.split(':'); r = RD.DpuSubgraphRunner(path); assert r.in_dims == (1, 320, 320, 3) and len(r.out_ts) == 2
    print(tag, 'out', [(t.name[-30:], list(t.dims), t.get_attr('fix_point')) for t in r.out_ts], flush=True)
    for i in (0, 2):
        q = np.clip(np.round(X[i].transpose(1, 2, 0) * r.in_scale), -128, 127).astype(np.int8)
        outs = [np.empty(tuple(t.dims), dtype=np.int8, order='C') for t in r.out_ts]; jid = r.runner.execute_async([np.ascontiguousarray(q.reshape(r.in_dims))], outs); r.runner.wait(jid)
        for t, o in zip(r.out_ts, outs): out[f"{tag}_{'cls' if 'classification' in t.name else 'reg'}_{i}"] = o[0].copy()
        out[f'{tag}_fp_cls'] = np.array(next(t.get_attr('fix_point') for t in r.out_ts if 'classification' in t.name)); out[f'{tag}_fp_reg'] = np.array(next(t.get_attr('fix_point') for t in r.out_ts if 'regression' in t.name))
    del r
f = O / ('diag_full_' + '_'.join(s.split(':')[0] for s in sys.argv[1:]) + '.npz'); np.savez(f, **out)
urllib.request.urlopen(urllib.request.Request(os.environ['BOARD_CHANNEL_URL'] + '/up/' + f.name, data=f.read_bytes()), timeout=60); print('POSTED', f.name)
