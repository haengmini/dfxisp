# HW Stage — Vitis HLS C-Synthesis Resource Results (2026-06-29)

Target: ZCU104 `xczu7ev-ffvc1156-2-e`, Vitis HLS 2024.1, clock target 5.0 ns (200 MHz).
Flow: `csynth_design` per top, flat temp-dir method (`/tmp/hls/<top>`), `-std=c++17`.
Source: `src/dfxisp_hls_variants.cpp` (4 synthesizable `extern "C"` tops, `m_axi`+`s_axilite`).

## Per-variant post-synthesis estimates (real)

| variant  | role                         | BRAM_18K | DSP | FF     | LUT    | CP (ns) | Fmax (MHz) |
|----------|------------------------------|---------:|----:|-------:|-------:|--------:|-----------:|
| normal   | static base (demosaic)       |        3 |  14 |  3,537 |  4,654 |   3.650 |     273.97 |
| reg_only | register fast-path (gain/γ)  |        3 |  14 |  3,564 |  4,780 |   3.650 |     273.97 |
| dfx_bin  | RM low-light (2×2 bin + bilinear) | 4 | 56 | 16,183 | 18,783 |   3.650 |     273.97 |
| dfx_fp   | RM ablation (green-guided B/D)| 4 |  47 | 24,372 | 22,216 |   3.650 |     273.97 |

All four meet the 5.0 ns target with identical 3.650 ns critical path (273.97 MHz);
timing is not the differentiator — area/power is (Direction A).
Source: `results/resource_csynth.csv` and the per-top `*_csynth.rpt`.

## Direction-A resource analysis

Incremental RM logic (variant − base `normal`):

| RM       | ΔLUT   | ΔFF    | ΔDSP | ΔBRAM |
|----------|-------:|-------:|-----:|------:|
| reg      |    126 |     27 |    0 |     0 |
| bin      | 14,129 | 12,646 |   42 |     1 |
| fp       | 17,562 | 20,835 |   33 |     1 |

**Static all-resident** must instantiate every variant's datapath concurrently;
**DFX** time-multiplexes one RM into a single Reconfigurable Partition sized to the
largest RM (base region stays fixed). Source: `results/resource_dfx_savings.csv`.

| scenario | metric | static-all-resident | DFX (time-mux) | saving |
|----------|--------|--------------------:|---------------:|-------:|
| deployed 2-RM (reg+bin)     | LUT | 18,909 | 18,783 |  **0.7 %** (126) |
| candidate 3-RM (reg+bin+fp) | LUT | 36,471 | 22,216 | **39.1 %** (14,255) |
| candidate 3-RM (reg+bin+fp) | DSP |     89 |     47 | **47.2 %** (42) |
| power proxy (daylight/normal) | LUT-active | 18,909 | 4,780 | **74.7 %** (bin datapath dark) |

### Honest interpretation
- With the **final deployed 2-RM set** (reg + bin) the **static-area saving is
  negligible (0.7 % LUT)** — one RM (bin) dominates and the reg RM is ~free, so
  time-multiplexing two RMs where one is tiny saves almost no static area. This is
  reported as-is, not oversold.
- The DFX area value is **scalability-bound**: it materialises as the RM library
  grows. The 3-RM candidate set (had `fp` not been screened out) already shows
  **39 % LUT / 47 % DSP** reduction versus static-all-resident, because static cost
  grows ~linearly in #RMs while DFX stays at `base + max(RM)`.
- The dominant DFX benefit at the current RM count is **power, not static area**:
  the binning datapath (14,129 LUT, 42 DSP ≈ 75 % of fabric) is configured/clocked
  **only in low-light**. In daylight the RP holds only the reg RM (4,780 LUT active),
  so the binning logic draws no dynamic power — the `*_active_daylight` rows above.
- `dfx_fp` is the largest RM yet the screened-out **negative case** (fails low-light
  mAP, see `results/map_exdark.csv`): it both validates the screening methodology and
  is the worked example for the 3-RM scalability figure.

## Reproduce

```bash
source /tools/Xilinx/Vitis_HLS/2024.1/settings64.sh
for top in dfxisp_normal dfxisp_regonly dfxisp_bin_rm dfxisp_fp_rm; do
  W=/tmp/hls/$top; rm -rf "$W"; mkdir -p "$W"
  cp src/dfxisp_hls_variants.cpp "$W/"
  printf 'open_project -reset proj\nset_top %s\nadd_files dfxisp_hls_variants.cpp -cflags "-std=c++17"\nopen_solution -reset sol\nset_part xczu7ev-ffvc1156-2-e\ncreate_clock -period 5.0 -name default\ncsynth_design\n' "$top" > "$W/run.tcl"
  ( cd "$W" && timeout 360 vitis_hls -f run.tcl )
done
# reports: /tmp/hls/<top>/proj/sol/syn/report/<top>_csynth.rpt
```

Note: Vitis HLS 2024.1 occasionally hangs on process exit after `close_project`;
omit `close_project` (as above) or kill the lingering `vitis_hls` PID — the report
is already written before the hang.

## Empty layout — ZCU104 board measurement (to fill)

| measurement | static-all-resident | DFX normal | DFX low-light | unit | tool |
|-------------|---------------------|-----------|---------------|------|------|
| full-bitstream LUT/FF/DSP/BRAM (post-route) | — | — | — | count | Vivado impl |
| partial-bitstream size (bin RM)             | n/a | — | — | KB | write_bitstream |
| ICAP/PR reconfiguration latency             | n/a | — | — | ms | board timer |
| static power (PL)                           | — | — | — | W | BEAM/INA226 |
| dynamic power, daylight                     | — | — | — | W | board rail |
| dynamic power, low-light                    | — | — | — | W | board rail |
