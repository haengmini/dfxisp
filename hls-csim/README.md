# DFXISP HLS C-sim Scaffold

Drive-first canonical placement: Agent OS / 06-production / DFXISP / hls-csim.
Local repository path: `isppipeline/hls/`.

## Goal

This scaffold creates the first deterministic C-simulation target for the DFX AI-ISP hardware path:

```text
pseudo-RAW Bayer GRBG uint16
  -> scene checker
  -> normal pipeline or low-light DFX RM path
  -> packed RGB888 uint32
```

It is intentionally Ponytail-style: one small HLS top, stdlib-only C-sim, no Vitis dependency for local smoke tests, and HLS pragmas preserved for Vitis HLS/Vitis flow.

## Files

- `include/dfxisp_accel.hpp` — HLS top-level interface and mode enum
- `src/dfxisp_accel.cpp` — checker + 3x3-window demosaic pipeline + low-light RM boundary
- `tests/test_dfxisp_csim.cpp` — C-sim smoke tests plus optional golden CSV RGB bit-compare
- `tools/gen_golden_vectors.py` — stdlib-only deterministic Bayer/RGB golden vector generator
- `tools/gen_verification_report.py` — stdlib-only Markdown verifier/report generator
- `scripts/vitis_hls.tcl` — Vitis HLS project scaffold for `dfxisp_accel`
- `Makefile` — local C-sim build with `g++`, golden generation, verify/report targets, and Vitis HLS dry-run report

## Run C-sim locally

```bash
cd isppipeline/hls
make csim
```

Expected output without `tests/golden_vectors.csv`:

```text
DFXISP golden vector compare skipped (tests/golden_vectors.csv not found)
DFXISP C-sim smoke tests passed
```

## Generate and verify golden vectors

`make golden` writes `tests/golden_vectors.csv` using a stdlib-only Python model that mirrors the documented C++ algorithm: GRBG Bayer input, clamped 3x3 demosaic, RAW12-to-RGB8 shift, and integer low-light gain/lift. `make verify` regenerates that CSV, runs C-sim, and bit-compares each packed `0x00RRGGBB` output against the golden values.

```bash
cd isppipeline/hls
make verify
```

Expected output:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (49 rows including header)
./build/dfxisp_csim
DFXISP golden vector compare passed (48 pixels)
DFXISP C-sim smoke tests passed
```

## Generate compact verification report

`make report` regenerates golden vectors, inspects `Makefile` state, runs the
local C-sim binary, and writes `reports/latest.md` with golden/C-sim status.
The report generator uses only the Python standard library.

```bash
cd isppipeline/hls
make report
```

Expected output:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (49 rows including header)
python3 tools/gen_verification_report.py --out reports/latest.md
wrote /path/to/isppipeline/hls/reports/latest.md (golden=pass, csim=pass)
```

## Run Vitis HLS scaffold

The TCL script defaults to the ZCU104 Zynq UltraScale+ part `xczu7ev-ffvc1156-2-e` and a 5.0 ns clock. Override the part/clock/flow if your board installation uses a different speed grade or target:

Before invoking Vitis, `make hls-report` prints the exact top function, project directory, part, clock, source/testbench files, and expected report/export paths without requiring `vitis_hls` to be installed:

```bash
cd isppipeline/hls
make hls-report
```

Expected output:

```text
DFXISP Vitis HLS dry-run report
  top     : dfxisp_accel
  project : build/vitis_hls/dfxisp_accel
  part    : xczu7ev-ffvc1156-2-e
  clock   : 5.0 ns
  flow    : csim
  tcl     : scripts/vitis_hls.tcl
  sources : src/dfxisp_accel.cpp include/dfxisp_accel.hpp
  testbench: tests/test_dfxisp_csim.cpp tests/golden_vectors.csv
  expected outputs:
    local csim binary : build/dfxisp_csim
    golden vectors    : tests/golden_vectors.csv
    HLS project       : build/vitis_hls/dfxisp_accel
    csim log          : build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log
    synthesis report  : build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt (for csynth/cosim/export)
    exported IP       : build/vitis_hls/dfxisp_accel/solution1/impl/export.zip (for export)
  note: dry-run only; vitis_hls is not invoked.
```

```bash
cd isppipeline/hls
make hls                                    # default: DFXISP_HLS_FLOW=csim
DFXISP_HLS_FLOW=csynth make hls             # run C-sim then synthesis
DFXISP_HLS_PART=xczu7ev-ffvc1156-2-e \
DFXISP_HLS_CLOCK=5.0 \
DFXISP_HLS_FLOW=csynth make hls
```

You can also pass Tcl args directly:

```bash
vitis_hls -f scripts/vitis_hls.tcl -- -part xczu7ev-ffvc1156-2-e -clock 5.0 -flow csynth
```

If `vitis_hls` is not on `PATH`, `make hls` exits with a clear install/source message. Set `VITIS_HLS=/path/to/vitis_hls` to use a non-standard executable path.

## HLS top function

```cpp
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold);
```

## Hardware/DFX structure

`src/dfxisp_accel.cpp` is now split along the intended hardware boundaries while
remaining stdlib-only for local C-sim:

- `checker_select_low_light()` / `checker_scene_average()` are the static-region
  scene checker blocks. In `AUTO`, they route the frame to the normal or low-light
  path based on average RAW luminance and `low_light_threshold`.
- `load_bayer_window3x3()` produces an explicit 3x3 Bayer neighborhood consumed by
  `demosaic_grbg_window()`. Today it uses clamped memory reads for deterministic
  C-sim; this boundary is intended to be replaced by a streaming line-buffer/window
  producer for hardware without changing the demosaic pixel operator.
- `normal_pipeline()` is the baseline static ISP path.
- `low_light_reconfigurable_module()` is the explicit DFX reconfigurable-module
  boundary candidate. In a Vivado DFX implementation, synthesize/package this
  low-light stage as the RM-compatible block and keep `dfxisp_accel`, the checker,
  and the normal pipeline in the static region. The function is marked `INLINE off`
  with an HLS pragma so the hierarchy is visible to synthesis.

No Vitis-specific headers are required for C-sim; only HLS pragmas are present and
ignored by the local `g++` build.

## Next hardware steps

1. Replace `load_bayer_window3x3()` clamped reads with a true streaming line buffer.
2. Promote `low_light_reconfigurable_module()` into a standalone DFX RM packaging flow.
3. Expand Python golden vector coverage beyond the current deterministic 4x4 GRBG smoke set.
