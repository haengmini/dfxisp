# Phase-1 board-integrated DFX implementation for ZCU104.
# Uses the already verified NormalISP board shell as static logic and makes
# only the HLS compute core (`.../NormalISP_0/inst`) reconfigurable. AXI
# adapters, PS, DDR interconnect, clock and reset remain static.
#
# Usage:
#   vivado -mode batch -source build_phase1.tcl -tclargs /path/to/dfxisp

set repo [file normalize [lindex $argv 0]]
set part xczu7ev-ffvc1156-2-e
set out [file join $repo hw DFX build phase1]
file mkdir $out

set normal_synth [file join $repo hw NormalISP NormalISP_zcu104 NormalISP_zcu104.runs synth_1 NormalISP_zcu104_design1_wrapper.dcp]
set lowlight_synth [file join $repo hw LowlightISP LowlightISP_zcu104 LowlightISP_zcu104.runs synth_1 LowlightISP_zcu104_wrapper.dcp]
# Keep the complete generated HLS IP wrapper inside the RP. Using the inner
# `inst` cell is invalid after synthesis because cross-boundary optimization
# exposes implementation-specific pins and breaks RM port compatibility.
set normal_cell NormalISP_zcu104_design1_i/NormalISP_0
set lowlight_cell LowlightISP_zcu104_i/LowlightISP_0

foreach f [list $normal_synth $lowlight_synth] {
    if {![file exists $f]} { error "Required checkpoint missing: $f" }
}

proc exact_cell {name} {
    set cells [get_cells -quiet $name]
    if {[llength $cells] != 1} {
        error "Expected exactly one cell '$name', got [llength $cells]"
    }
    return $cells
}

# Extract each HLS compute core as a gate-level RM checkpoint.
open_checkpoint $normal_synth
set ncell [exact_cell $normal_cell]
write_checkpoint -force -cell $ncell [file join $out rm_normal_synth.dcp]
report_utilization -cells $ncell -file [file join $out rm_normal_synth_util.rpt]
close_design

open_checkpoint $lowlight_synth
set lcell [exact_cell $lowlight_cell]
write_checkpoint -force -cell $lcell [file join $out rm_lowlight_synth.dcp]
report_utilization -cells $lcell -file [file join $out rm_lowlight_synth_util.rpt]
close_design

# Configuration 1: NormalISP in the RP, using the proven NormalISP board shell.
open_checkpoint $normal_synth
# The project-mode PS IP XDC is not embedded as a primary clock in the synth
# checkpoint. Recreate the verified 100 MHz PL clock explicitly so placement,
# routing and timing reports are constrained in this non-project DFX flow.
set pl_clk_pin [get_pins -quiet NormalISP_zcu104_design1_i/zynq_ultra_ps_e_0/pl_clk0]
if {[llength $pl_clk_pin] != 1} { error "PS pl_clk0 source pin not found" }
create_clock -name pl_clk0 -period 10.000 $pl_clk_pin
set rp [exact_cell $normal_cell]
set_property HD.RECONFIGURABLE true $rp
create_pblock pblock_isp_rp
resize_pblock [get_pblocks pblock_isp_rp] -add {CLOCKREGION_X1Y0:CLOCKREGION_X2Y0}
add_cells_to_pblock [get_pblocks pblock_isp_rp] $rp
set_property CONTAIN_ROUTING true [get_pblocks pblock_isp_rp]
set_property EXCLUDE_PLACEMENT true [get_pblocks pblock_isp_rp]
set_property SNAPPING_MODE ON [get_pblocks pblock_isp_rp]
write_checkpoint -force [file join $out static_with_normal_synth.dcp]
report_utilization -pblocks pblock_isp_rp -file [file join $out pblock_capacity.rpt]

opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force [file join $out config1_normal_routed.dcp]
report_utilization -file [file join $out config1_normal_util.rpt]
report_timing_summary -file [file join $out config1_normal_timing.rpt]
report_drc -file [file join $out config1_normal_drc.rpt]
close_design

# Configuration 2: preserve the routed static shell and replace only the RM.
open_checkpoint [file join $out config1_normal_routed.dcp]
set rp [exact_cell $normal_cell]
update_design -cell $rp -black_box
lock_design -level routing
read_checkpoint -cell $rp [file join $out rm_lowlight_synth.dcp]
opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force [file join $out config2_lowlight_routed.dcp]
report_utilization -file [file join $out config2_lowlight_util.rpt]
report_timing_summary -file [file join $out config2_lowlight_timing.rpt]
report_drc -file [file join $out config2_lowlight_drc.rpt]
close_design

pr_verify -initial [file join $out config1_normal_routed.dcp] \
          -additional [file join $out config2_lowlight_routed.dcp] \
          -file [file join $out pr_verify.rpt]
puts "PHASE1_DFX_PR_VERIFY_PASS"
exit
