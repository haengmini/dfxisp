# DFX bring-up workspace

This directory starts the real `NormalISP <-> LowlightISP` Dynamic Function eXchange integration on ZCU104.

## Scope

The first milestone deliberately follows the verified calculator-demo sequence before autonomous checker triggering:

1. Prove that both ISP HLS IPs expose an identical RP boundary and AXI-Lite register contract.
2. Build one static shell with a single reconfigurable partition.
3. Implement `NormalISP` and `LowlightISP` as mutually exclusive RMs.
4. Run `pr_verify` and emit one full plus two partial bitstreams.
5. Only after the software-triggered swap is proven, add `checker_scan -> checker_hysteresis -> dfxc_trigger_adapter -> AMD DFX Controller`.

This avoids mixing RP-boundary failures with checker/trigger failures.

## Current kickoff artifacts

- `scripts/preflight.py`: validates source/IP prerequisites and emits `build/preflight.json`.
- `scripts/gen_dfx_controller.tcl`: generates the AMD DFX Controller IP contract with two hardware triggers.
- `constraints/dfx_pblock.xdc`: project-sized RP pblock from the measured Stage-5 floorplan.
- `rtl/`: verified static-trigger-chain RTL copied from `isppipeline/hls/checker/ip_repo/src/`.

## Phase-1 implementation

`build_phase1.tcl` reuses the verified NormalISP ZCU104 shell and makes the **complete generated HLS IP wrapper** the RP. The inner HLS `inst` must not be used as the RP boundary: synthesis exposes implementation-specific optimized pins there and Lowlight insertion fails with a port mismatch. Keeping the wrapper inside the RP leaves PS, DDR SmartConnect, AXI-Lite adapters, clock and reset in static logic and gives both RMs the stable AXI boundary.

The non-project DCP flow explicitly recreates the PS `pl_clk0` constraint as 100 MHz. Without this, implementation and bitstream generation can succeed while `report_timing_summary` incorrectly reports `WNS=NA`.

```bash
cd ~/Desktop/dfxisp/hw/DFX
python3 scripts/preflight.py
/tools/Xilinx/Vivado/2024.1/bin/vivado -mode batch \
  -source scripts/build_phase1.tcl -tclargs ~/Desktop/dfxisp
/tools/Xilinx/Vivado/2024.1/bin/vivado -mode batch \
  -source scripts/write_phase1_bitstreams.tcl -tclargs ~/Desktop/dfxisp
```

Generated Vivado artifacts stay under `build/` and are ignored by `hw/.gitignore`.

## Decision held for later

Who re-asserts `ap_start` immediately after an RM swap remains intentionally unresolved. It does not block Phase 1 software-triggered RP/RM compatibility proof.
