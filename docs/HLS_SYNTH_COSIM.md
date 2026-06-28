# DFXISP HLS Synthesis / Cosimulation Guide

This guide is the next hardware-verification step after the local `g++` C-sim loop passes.

## Current prerequisite status

Run from the repository root:

```bash
cd /path/to/dfxisp
make -C isppipeline/hls verify
make -C isppipeline/hls report
```

Expected C-sim pass signal:

```text
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```

Current default HLS target:

- top: `dfxisp_accel`
- part: `xczu7ev-ffvc1156-2-e` (ZCU104 Zynq UltraScale+ MPSoC)
- clock: `5.0 ns`
- project: `isppipeline/hls/build/vitis_hls/dfxisp_accel`
- Tcl: `isppipeline/hls/scripts/vitis_hls.tcl`

Inspect the dry-run configuration:

```bash
make -C isppipeline/hls hls-report
```

## Environment setup

On a Vitis-installed workstation, source the Xilinx settings script first. Examples:

```bash
source /tools/Xilinx/Vitis/2023.2/settings64.sh
# or
source /opt/Xilinx/Vitis/2023.2/settings64.sh
```

Then verify:

```bash
command -v vitis_hls
vitis_hls -version
```

If `vitis_hls` is not on `PATH`, `make ... hls` will fail with:

```text
ERROR: vitis_hls not found. Install/source Vitis HLS, or set VITIS_HLS=/path/to/vitis_hls.
```

## Run C-sim inside Vitis HLS

This is different from the local `g++` C-sim. It runs through the Vitis HLS project flow:

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=csim hls
```

Expected log location:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log
```

## Run C synthesis

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls
```

Expected report:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt
```

Extract and record at minimum:

- latency min / max / avg if present
- initiation interval / pipeline II if present
- LUT / FF / BRAM / DSP usage
- clock period estimate
- any synthesis warnings that affect interface, memory, or loop pipelining

## Run RTL cosimulation

Cosim requires C synthesis first. The current Tcl flow runs `csim_design`, `csynth_design`, then `cosim_design`:

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=cosim hls
```

Expected output locations vary slightly by Vitis version, but check under:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/sim/
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/
```

Record:

- whether RTL cosim passes or fails
- simulator used by Vitis
- latency / transaction summary
- generated waveform path if enabled
- mismatch lines if any

## Export IP for Vivado / DFX integration

After C synthesis passes:

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=export hls
```

Expected export artifact:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/impl/export.zip
```

This exported IP is the artifact to connect into the Vivado static/DFX design.

## Recommended evidence commit contents

After running on a Vitis machine, commit only meaningful source/docs/report artifacts, for example:

```text
isppipeline/hls/src/dfxisp_accel.cpp
isppipeline/hls/include/dfxisp_accel.hpp
isppipeline/hls/tests/test_dfxisp_csim.cpp
isppipeline/hls/tests/golden_vectors.csv
isppipeline/hls/tools/*.py
isppipeline/hls/scripts/vitis_hls.tcl
isppipeline/hls/reports/latest.md
isppipeline/hls/reports/csynth-summary.md      # create from real *_csynth.rpt
isppipeline/hls/reports/cosim-summary.md       # create from real cosim logs
```

Do **not** commit large generated Vitis project directories such as `build/vitis_hls/` unless a specific small report artifact is intentionally extracted.

## Current limitation

A machine without Vitis/Vivado can only run the local `g++` C-sim loop. It cannot produce real `csynth`, `cosim`, LUT/FF/BRAM/DSP, timing, export IP, partial bitstream, or board metrics. Do not report those metrics until real Vitis/Vivado logs exist.
