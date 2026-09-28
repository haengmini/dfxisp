# Phase-1 DFX implementation result — 2026-09-23

## Scope

Board-integrated ZCU104 DFX implementation using the verified NormalISP shell:

- static: Zynq UltraScale+ MPSoC PS, DDR/SmartConnect, AXI-Lite adapters, 100 MHz PL clock/reset
- RP: complete generated HLS IP wrapper
- RM 0: `NormalISP`
- RM 1: `LowlightISP`

This phase proves software-triggered RM compatibility and produces loadable bitstreams. Checker-driven autonomous triggering and physical board loading remain later phases.

## Verification

| Check | Normal | Lowlight |
|---|---:|---:|
| WNS @ 100 MHz | +3.102 ns | +2.830 ns |
| TNS | 0.000 ns | 0.000 ns |
| DRC errors | 0 | 0 |
| Critical warnings | 0 | 0 |
| Routed CLB LUTs, complete design | 8,477 | 7,752 |
| Routed registers, complete design | 12,525 | 10,253 |
| DSPs | 28 | 14 |
| BRAM tiles | 1.5 | 1.5 |

`pr_verify` passed:

- reconfigurable modules compared: 1
- partition pins compared: 121
- static cells compared: 10,212
- static routed nodes compared: 140,425
- static routed PIPs compared: 132,177
- result: checkpoints compatible

The 37 non-critical bitgen warnings are retained in the Vivado logs; bitgen reported 0 errors and 0 critical warnings.

## Generated bitstreams

Generated under `hw/DFX/build/phase1/` (ignored build output):

| File | Bytes | SHA-256 |
|---|---:|---|
| `config1_normal_full.bit` | 19,311,229 | `ae2a2426bf13318cb2d5a4fb0abdfd41d3280c87be81a66504a3d4f87e5c68c1` |
| `rm_normal_partial.bit` | 1,504,826 | `7da66e15da5ba6cb5c3933b7142efab1dbeca49b46b5bf7e1d6bd2c00a9121bd` |
| `rm_lowlight_partial.bit` | 1,476,154 | `91e5d5d8263b77ea9356ef9d605e2caa918e072f41188730b84117ef3a6190f9` |

Matching `.bin` files were also generated for software/DFX-controller loading.

## Important implementation findings

1. The inner HLS `inst` is not a safe RP boundary. Post-synthesis optimization exposed implementation-specific pins and caused a Normal→Lowlight port mismatch.
2. The complete generated HLS IP wrapper is a valid boundary. It preserves a stable AXI interface and passed `pr_verify`.
3. Opening the project synthesis DCP outside project mode did not retain a primary PL-clock object. The flow therefore explicitly creates the verified 100 MHz clock on PS `pl_clk0`; otherwise timing reports misleadingly show `WNS=NA` even though implementation and bitgen succeed.

## Next phase

1. Stage full Normal bitstream and both partial `.bin` files for ZCU104.
2. Add software-controlled shutdown/decouple/load/restart and verify Normal→Lowlight→Normal on physical buffers.
3. Integrate `checker_scan`, `checker_hysteresis`, `dfxc_trigger_adapter`, and AMD DFX Controller into static logic.
4. Resolve and verify `ap_start` re-assertion after each RM swap.
