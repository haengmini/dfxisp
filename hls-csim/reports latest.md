# DFXISP HLS Verification Report

Generated: 2026-06-26 01:04:52 UTC
Report: `reports/latest.md`

## Status

| Check | Status | Evidence |
|---|---:|---|
| Golden vectors | PASS | `tests/golden_vectors.csv`; 48 data rows; 3 cases |
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

## C-sim output

```text
DFXISP golden vector compare passed (48 pixels)
DFXISP C-sim smoke tests passed
```
