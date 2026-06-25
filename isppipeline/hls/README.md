# DFXISP HLS C-sim Scaffold

Drive-first canonical placement: Agent OS / 06-production / DFXISP / hls-csim.
Local repository path: `isppipeline/hls/`.

## Goal

This scaffold creates the first deterministic C-simulation target for the DFX AI-ISP hardware path:

```text
pseudo-RAW Bayer GRBG uint16
  -> scene checker
  -> normal or low-light ISP mode
  -> packed RGB888 uint32
```

It is intentionally Ponytail-style: one small HLS top, stdlib-only C-sim, no Vitis dependency for local smoke tests, and HLS pragmas preserved for Vitis HLS/Vitis flow.

## Files

- `include/dfxisp_accel.hpp` — HLS top-level interface and mode enum
- `src/dfxisp_accel.cpp` — demosaic + low-light gain/gamma-lift + auto checker
- `tests/test_dfxisp_csim.cpp` — C-sim smoke tests
- `Makefile` — local C-sim build with `g++`

## Run C-sim locally

```bash
cd isppipeline/hls
make csim
```

Expected output:

```text
DFXISP C-sim smoke tests passed
```

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

## Next hardware steps

1. Add Vitis HLS project TCL for ZCU104 target clock/part.
2. Replace border-clamped reference demosaic with line-buffer/window implementation.
3. Split low-light processing into a DFX reconfigurable module boundary.
4. Generate golden vectors from Python ISP and compare RGB888/RGB32 output bitwise.
