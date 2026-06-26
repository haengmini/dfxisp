# Sequential Agent Deployment Worklog — 2026-06-26

## Drive-first rule

All durable outputs were updated in Google Drive first/canonically where possible. Local `/opt/data` paths were used as staging/build cache and repo mirror.

## Agent deployment sequence

### 1. Coder agent — Vitis HLS/ZCU104 TCL scaffold

Implemented in `Agent OS / DFXISP / hls-csim` and local mirror `/opt/data/dfxisp_md/isppipeline/hls`.

Outputs:

- `scripts/vitis_hls.tcl`
- Makefile `hls` target
- README HLS command docs

Verification:

```text
make csim: PASS
C++ syntax check: PASS
make hls: fails clearly when vitis_hls is not installed
```

### 2. HW Coder agent — line-buffer/window-ready architecture + DFX RM boundary

Refactored the HLS C++ into explicit hardware-friendly boundaries:

- `checker_scene_average()`
- `checker_select_low_light()`
- `load_bayer_window3x3()`
- `demosaic_grbg_window()`
- `normal_pixel_kernel()`
- `normal_pipeline()`
- `low_light_pipeline()`
- `low_light_reconfigurable_module()`

`low_light_reconfigurable_module()` is marked/commented as the intended DFX reconfigurable module boundary.

Verification:

```text
make -C /opt/data/dfxisp_md/isppipeline/hls csim: PASS
```

### 3. Research/Coder agent — Python golden vector + bit-compare

Added deterministic golden-vector generation and C-sim bit comparison.

Outputs:

- `tools/gen_golden_vectors.py`
- `tests/golden_vectors.csv`
- C++ test updated to compare packed RGB output against golden CSV
- Makefile `golden` and `verify` targets

Verification:

```text
make -C /opt/data/dfxisp_md/isppipeline/hls verify
DFXISP golden vector compare passed (48 pixels)
DFXISP C-sim smoke tests passed
```

### 4. Dashboard agent — loop health embedded in hq-dashboard

Updated `/opt/data/scripts/agent_os_drive_first_loop.py` and Drive canonical dashboard so the latest loop status is embedded into `window.STATE.loop_status` rather than relying on sidecar `fetch()` from file URLs.

Drive dashboard:

- `hq-dashboard.html`
- Drive ID: `1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0`
- Link: https://drive.google.com/file/d/1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0/view?usp=drivesdk

Verification:

```text
node --check: PASS
/opt/data/scripts/agent_os_drive_first_loop.sh: PASS
```

## Drive canonical DFXISP HLS folder

Folder:

- `Agent OS / DFXISP / hls-csim`
- Drive folder ID: `1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML`
- Link: https://drive.google.com/drive/folders/1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML

Updated/created Drive files:

| File | Status | Drive ID |
|---|---|---|
| `.gitignore` | updated | `1WPHkesxezKZrJtINzFaVf_LxCWdpdiSU` |
| `README.md` | updated | `1-wXNhlK4IsjOVh-zQvhS5CfdV1VVRSmT` |
| `Makefile` | updated | `1I5b1kD6oOhTw9ei535aU80A-WBTohzJv` |
| `include/dfxisp_accel.hpp` | updated | `1us6QwxvWoMBnahg0Oy6p215HTrBUrpub` |
| `src/dfxisp_accel.cpp` | updated | `17MqS_XkTrXKgexGnofhNqmqiMYYkTVv7` |
| `tests/test_dfxisp_csim.cpp` | updated | `1QYx2HyI7iVC_0VBC9k_S9ixk-0sNSxaM` |
| `scripts/vitis_hls.tcl` | created | `1fhpvnbuqU-Y391yfVRTKWit78OV9Wv_y` |
| `tools/gen_golden_vectors.py` | created | `1A-zEbdAgmNuSdn1r1tc51lYXAEkAB78r` |
| `tests/golden_vectors.csv` | created | `18dt49Qp376F5sQk686KlQlXJUpBju6L6` |

## Loop status

Latest loop result:

- `loop-status-latest.md`: https://drive.google.com/file/d/1qRVLAKN4bRCPazQuYnv_OhjngTbCH5z1/view?usp=drivesdk
- Overall: `PASS`

Checks:

```text
✅ drive_hq_dashboard_js
✅ drive_dfxisp_hls_files
✅ dfxisp_local_csim
```

## Git status

Local commits:

```text
547af2f feat: extend DFXISP HLS verification loop
c5b920d feat: add DFXISP HLS C-sim scaffold
```

GitHub push remains blocked by missing HTTPS credentials in this runtime:

```text
fatal: could not read Username for 'https://github.com': No such device or address
```

No source push was completed. Drive canonical artifacts are saved.

## Next sequential deployment target

1. Admin agent: configure GitHub auth or switch remote to authenticated SSH/token flow.
2. HW Coder agent: add Vitis HLS export synthesis target once `vitis_hls` is available.
3. Reviewer agent: compare Python golden vectors against a higher-fidelity ISP golden model from `isppipeline/unprocess`.
4. Dashboard agent: add visible UI drill-down for HLS verification history and GitHub push status.
