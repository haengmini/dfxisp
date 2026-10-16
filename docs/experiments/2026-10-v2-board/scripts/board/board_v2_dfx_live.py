#!/usr/bin/env python3
"""DFX live: checker-driven RM selection (scan_decide, MODE_AUTO) -> board ISP -> FOUR DPU models on the SAME ISP output:
  old = deployed yolov8n_dpu.xmodel; s0,s1,s2 = v2 balanced-trained seeds. One cold-boot-owned session, no retry/recovery between jobs.
Per-frame gate: board RGB sha256 must equal the PC reference for (chosen RM arm, frame) -> stops immediately on mismatch (fault containment as in the reviewed sessions).
Sequential closed-loop frames, NOT a real-time arrival/drop measurement. Jobs: night100, day100, mixed200, mixed_blocks200 (600 frames).
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np
EXPECTED = {'partials/partial_normal_bs1.icap.bin': 'd921d7c495d6136e29f62fe2994956725317ba9095b4579edb587bf80559f8c1',
            'partials_blc16/partial_lowlight_blc16_bs1.icap.bin': 'b739f7837e4e2c5a3592a1385d2af548322ef59ebc3822c339d73b0bea28bf1f'}
MODELS = {'old': ('/home/root/exp/models/yolov8n_dpu.xmodel', '6713fbad2065a6b15e627b334633912c24cf691748455b9c7b82f8f269698817'),
          's0': ('/home/root/exp/v2live/v2_yolo_A_s0.xmodel', '4565206dc2dbd03a8fcc312a558e5b4bd1763dbf87b26e8ec1f4b7952f202357'),
          's1': ('/home/root/exp/v2live/v2_yolo_A_full_s1.xmodel', 'b747014257ac6924287b92cd34ed9fff417a279ef6435c6221b3c1e864ff55b0'),
          's2': ('/home/root/exp/v2live/v2_yolo_A_full_s2.xmodel', 'ca8dd8181a77f1f138367ef425b450c89718369a32bcf5a586dc02b450e3588c')}
JOBS = (('night', 100), ('day', 100), ('mixed', 200), ('mixed_blocks', 200))
REFS = '/home/root/exp/v2live/live_ref.json'

def fid_key(fid):
    stem = fid.split('/')[-1]
    return ('night_' if fid.startswith('LOD/') else 'day_') + stem

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='/home/root/exp'); ap.add_argument('--out', default=None)
    ap.add_argument('--cold-boot-verified', action='store_true'); ap.add_argument('--preflight', action='store_true'); a = ap.parse_args()
    root = Path(a.root); sys.path.insert(0, str(root / 'app'))
    import run_detector as RD
    RD._have_cv2 = lambda: False
    assert hashlib.sha256(Path(RD.__file__).read_bytes()).hexdigest() == '5b228c310ee6bed2e4affe090caee3e205521e8703be0027c59d01df3fb3d756'
    import zcu_modes as Z, zcu_runtime as R
    from controller import State
    for f, h in EXPECTED.items(): assert hashlib.sha256((root / f).read_bytes()).hexdigest() == h, f
    for t, (p, h) in MODELS.items(): assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h, t
    ref = {(r['arm'], r['key']): r['board_rgb_sha256'] for r in json.loads(Path(REFS).read_text())}; assert len(ref) == 400
    d, by, sets = Z.load_dataset(str(root)); assert d['input'] == [1368, 912]
    for s, n in JOBS: assert len(sets[s]) == n, s
    for s, _ in JOBS:
        for fid in sets[s]:
            assert ('normal', fid_key(fid)) in ref and ('lowlight', fid_key(fid)) in ref, ('NO_REF', fid)
            assert (root / by[fid]['raw']).stat().st_size == 1368 * 912 * 2
    print('STATIC_PREFLIGHT_OK frames', {s: len(sets[s]) for s, _ in JOBS}, flush=True)
    runners = {}
    for t, (p, _) in MODELS.items():
        runners[t] = RD.DpuSubgraphRunner(p); assert runners[t].in_dims == (1, 640, 640, 3), t
    print('FOUR_DPU_RUNNERS_OK', list(runners), flush=True)
    if a.preflight:
        x = np.zeros((640, 640, 3), np.float32)
        for t, r in runners.items(): o = r.run(x); assert sorted((v.shape[1], v.shape[-1]) for v in o.values()) == [(20, 3), (20, 64), (40, 3), (40, 64), (80, 3), (80, 64)], t
        print('PREFLIGHT_DPU_ONLY_PASS', flush=True); return
    if not a.cold_boot_verified: raise SystemExit('fresh user-confirmed power-cycle required')
    if not a.out: raise SystemExit('--out required')
    out = Path(a.out); out.mkdir(exist_ok=False)
    status = {'state': 'PREFLIGHT', 'completed': [], 'scope': 'DFX checker-driven RM select live; BLC16 Lowlight partial; 4 DPU models on same ISP output; sequential closed loop'}
    def update(**kw):
        status.update(kw); p = out / 'status.tmp'; p.write_text(json.dumps(status, indent=1)); p.replace(out / 'status.json')
        print(json.dumps({'state': status['state'], 'current': status.get('current'), 'completed': len(status['completed']), 'error': status.get('error')}), flush=True)
    io = R.UioBackend(); s = io.read(0xA2000000); g = io.read(0xA3020008); io.close(); assert s == 7 and g == 0, ('FRESH_STATE_REFUSAL', hex(s), hex(g))
    update(state='INITIAL_STATUS'); board = None
    try:
        board = Z.Board.__new__(Z.Board); Z.Board.__init__(board, str(root), cold_boot_verified=True)
        board.stage_partials(str(root / 'partials/partial_normal_bs1.icap.bin'), str(root / 'partials_blc16/partial_lowlight_blc16_bs1.icap.bin'))
        update(state='BATCH'); W, H = d['input']
        for subset, n in JOBS:
            files = {t: (out / f'dfx_{t}_{subset}.jsonl').open('w') for t in MODELS}; meta = (out / f'dfx_meta_{subset}.jsonl').open('w')
            try:
                for i, fid in enumerate(sets[subset]):
                    key = fid_key(fid); raw = (root / by[fid]['raw']).read_bytes()
                    t0 = time.perf_counter(); checker = board.scan_decide(raw, W, H, Z.MODE_AUTO); scan_ms = (time.perf_counter() - t0) * 1000
                    rm = board.current_rm(); arm = 'normal' if rm == 0 else 'lowlight'
                    rgb, ow, oh, isp_ms = board.isp_frame(raw, W, H); assert (ow, oh) == ((1368, 912) if rm == 0 else (684, 456)), (ow, oh, rm)
                    sha = hashlib.sha256(rgb).hexdigest()
                    # board RGB is hashed as raw bytes for lowlight? reference uses the PC image packed as <u4 at the NATIVE output size, same convention as coco_board_rgb_check
                    assert sha == ref[(arm, key)], ('PIXEL_PARITY_FAIL', arm, key, sha, ref[(arm, key)])
                    arr = Z.rgb_to_array(rgb, ow, oh); x = RD.preprocess(arr, 640, 'unit')
                    meta.write(json.dumps({'id': key, 'subset': subset, 'idx': i, 'checker': checker if isinstance(checker, (int, float, str, dict, list, type(None))) else str(checker), 'rm': rm, 'arm': arm, 'scan_ms': scan_ms, 'isp_ms': isp_ms, 'w': ow, 'h': oh, 'rgb_sha256': sha}) + '\n'); meta.flush()
                    for t, r in runners.items():
                        t1 = time.perf_counter(); outs = r.run(x); dpu_ms = (time.perf_counter() - t1) * 1000
                        dd = RD.yolov8_postprocess(outs, 640, 3, .001, .45)
                        dets = [[float(b[0]*ow/640), float(b[1]*oh/640), float(b[2]*ow/640), float(b[3]*oh/640), float(b[4]), int(b[5])] for b in dd]
                        files[t].write(json.dumps({'id': key, 'subset': subset, 'rm': rm, 'arm': arm, 'width': ow, 'height': oh, 'dpu_ms': dpu_ms, 'detections': dets}) + '\n'); files[t].flush()
                    if (i + 1) % 10 == 0: update(current={'job': subset, 'done': i + 1, 'total': n})
            finally:
                for f in list(files.values()) + [meta]: f.close()
            status['completed'].append(subset); update()
        update(state='COMPLETE', current=None)
    except BaseException as exc:
        containment = None; ctrl = getattr(board, 'ctrl', None)
        if ctrl is not None and ctrl.state != State.FAULT:
            try: ctrl.fault('v2 dfx live stopped: ' + repr(exc))
            except BaseException as fault: containment = str(fault)
        try: update(state='STOPPED', error=repr(exc), containment=containment)
        except BaseException as le: print('STOPPED ' + repr(exc) + '; status write failed: ' + repr(le), file=sys.stderr, flush=True)
        raise
    finally:
        if board and getattr(board, 'ctrl', None) is not None and board.ctrl.state != State.FAULT: board.ctrl.close(); board.io.close(); board.buf.close()

if __name__ == '__main__': main()
