# DFXISP HLS Verification Report

Generated: 2026-06-26 05:11:07 UTC
Report: `reports/latest.md`

## Status

| Check | Status | Evidence |
|---|---:|---|
| Golden vectors | PASS | `tests/golden_vectors.csv`; 560 data rows; 8 cases |
| C-sim | PASS | `build/dfxisp_csim`; return code 0 |

## Makefile state

- `CXX`: `g++`
- `PYTHON`: `python3`
- `CSIM_BIN`: `build/dfxisp_csim`
- `GOLDEN_CSV`: `tests/golden_vectors.csv`
- Targets include: `.PHONY, all, csim, golden, verify, report, hls-report, hls, clean`

## Golden vector cases

| Case | Mode | Threshold | Dimensions | Rows |
|---|---:|---:|---:|---:|
| normal_4x4 | 0 | 90 | 4x4 | 16 |
| lowlight_4x4 | 1 | 90 | 4x4 | 16 |
| auto_lowlight_4x4 | 2 | 120 | 4x4 | 16 |
| bright_normal_8x8 | 0 | 512 | 8x8 | 64 |
| dark_lowlight_8x8 | 1 | 512 | 8x8 | 64 |
| mixed_auto_16x16 | 2 | 1400 | 16x16 | 256 |
| threshold_boundary_equal_8x8 | 2 | 512 | 8x8 | 64 |
| threshold_boundary_below_8x8 | 2 | 512 | 8x8 | 64 |

## DPU-facing shape policy

Decision for this C2 verification set: keep the default HLS/C-sim output shape at `H x W` for NORMAL, LOW_LIGHT, and AUTO outputs. This preserves a fixed-size DPU-facing ABI while the H/2 x W/2 low-light binning path remains an explicit ablation/future RM variant rather than the default golden-vector contract.

- Rationale: current `dfxisp_accel` signature exposes one output buffer without output-width/output-height metadata, so H/2 emission would make bit-exact comparison ambiguous and would force downstream resize/pad policy before DPU integration.
- Ablation policy: evaluate `H/2 x W/2` low-light binning separately once the interface includes output shape metadata or an explicit post-binning upsample/pad stage. Compare it against the preserve-shape path using the same bright/dark/mixed/threshold-boundary fixtures.
- Current golden-vector contract: packed RGB888 `0x00RRGGBB`, one output pixel per input pixel, with low-light represented by deterministic gain/lift at preserved shape.

## C-sim output

```text
DFXISP golden vector compare passed (560 pixels)
DFXISP C-sim smoke tests passed
```
