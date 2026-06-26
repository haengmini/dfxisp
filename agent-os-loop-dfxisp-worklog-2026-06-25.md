# Agent OS All-in-One Platform Loop + DFXISP HLS C-sim Worklog — 2026-06-25

## Summary

이 작업은 Google Drive 정본을 기준으로 수행했다. 로컬 `/opt/data`는 Drive 파일 검증/빌드용 staging cache로만 사용했다.

## Drive Dashboard Fix

Canonical dashboard file:

- `hq-dashboard.html`
- Drive ID: `1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0`
- Link: https://drive.google.com/file/d/1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0/view?usp=drivesdk

Fix applied:

- JS syntax error in the `에이전트/agent` local-answer path was patched.
- Re-downloaded the Drive file after update and verified with `node --check`.

Verification:

```text
title Agent OS — Command Center
node --check /tmp/drive_hq_redownload.js: PASS
```

## Drive-first Loop Engineering

Created and ran a Drive-first watchdog loop:

- Local executable cache: `/opt/data/scripts/agent_os_drive_first_loop.py`
- Wrapper: `/opt/data/scripts/agent_os_drive_first_loop.sh`
- Drive script IDs:
  - `agent_os_drive_first_loop.py`: `1Sfg0bP0-F_w8d-HDXrlP-4VzgyObx7Wp`
  - `agent_os_drive_first_loop.sh`: `14JCv3jTp2G_A6JgTief9iov51ja28d2j`
- Cron job: `agent-os-drive-first-loop`
- Schedule: every 30 minutes
- Delivery: local, script-only/no_agent

Loop checks:

1. Download canonical Drive `hq-dashboard.html` and run JS syntax check.
2. Verify Drive DFXISP HLS C-sim folder contains required source files.
3. Run local C-sim mirror: `make -C /opt/data/dfxisp_md/isppipeline/hls csim`.
4. Upsert status artifacts into Drive `05-dashboard`:
   - `loop-status-latest.json`
   - `loop-status-latest.md`

Latest loop result:

```text
Agent OS loop PASS — Drive status updated: https://drive.google.com/file/d/1qRVLAKN4bRCPazQuYnv_OhjngTbCH5z1/view?usp=drivesdk
```

## DFXISP HLS C-sim / Hardware Scaffold

Canonical Drive folder:

- `Agent OS / DFXISP / hls-csim`
- Drive folder ID: `1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML`
- Link: https://drive.google.com/drive/folders/1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML

Uploaded files:

| File | Drive ID |
|---|---|
| `README.md` | `1-wXNhlK4IsjOVh-zQvhS5CfdV1VVRSmT` |
| `Makefile` | `1I5b1kD6oOhTw9ei535aU80A-WBTohzJv` |
| `.gitignore` | `1WPHkesxezKZrJtINzFaVf_LxCWdpdiSU` |
| `include/dfxisp_accel.hpp` | `1us6QwxvWoMBnahg0Oy6p215HTrBUrpub` |
| `src/dfxisp_accel.cpp` | `17MqS_XkTrXKgexGnofhNqmqiMYYkTVv7` |
| `tests/test_dfxisp_csim.cpp` | `1QYx2HyI7iVC_0VBC9k_S9ixk-0sNSxaM` |

Local mirror/repo path:

- `/opt/data/dfxisp_md/isppipeline/hls/`

Implemented hardware-facing top:

```cpp
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold);
```

Supported modes:

- `DFXISP_MODE_NORMAL`
- `DFXISP_MODE_LOW_LIGHT`
- `DFXISP_MODE_AUTO`

Current algorithm:

```text
pseudo-RAW Bayer GRBG uint16
  -> scene average checker
  -> normal / low-light mode select
  -> border-clamped demosaic
  -> low-light integer gain + lift
  -> packed RGB888 uint32
```

C-sim verification:

```text
make -C isppipeline/hls csim
DFXISP C-sim smoke tests passed
```

Git local commit:

```text
c5b920d feat: add DFXISP HLS C-sim scaffold
```

GitHub push status:

```text
blocked: GitHub HTTPS credentials unavailable in this environment
fatal: could not read Username for 'https://github.com': No such device or address
```

Drive canonical artifacts are already saved; GitHub push can be retried after GitHub auth is configured.

## Next Loop Targets

1. Add Vitis HLS TCL for ZCU104 part/clock and export target.
2. Replace reference demosaic with line-buffer/window HLS architecture.
3. Introduce explicit DFX reconfigurable-module boundary for low-light path.
4. Generate Python golden vectors and bit-compare RGB888/RGB32 output.
5. Feed loop status into `hq-dashboard.html` visual cards instead of status-only artifacts.
