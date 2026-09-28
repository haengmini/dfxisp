# Emit the Phase-1 full and partial bitstreams after pr_verify succeeds.
# Usage: vivado -mode batch -source write_phase1_bitstreams.tcl -tclargs /path/to/dfxisp
set repo [file normalize [lindex $argv 0]]
set out [file join $repo hw DFX build phase1]
set normal_dcp [file join $out config1_normal_routed.dcp]
set lowlight_dcp [file join $out config2_lowlight_routed.dcp]
set rp_cell NormalISP_zcu104_design1_i/NormalISP_0
foreach f [list $normal_dcp $lowlight_dcp [file join $out pr_verify.rpt]] {
    if {![file exists $f]} { error "Required verified Phase-1 artifact missing: $f" }
}
open_checkpoint $normal_dcp
set rp [get_cells -quiet $rp_cell]
if {[llength $rp] != 1} { error "Normal configuration RP cell not found: $rp_cell" }
write_bitstream -force -bin_file [file join $out config1_normal_full.bit]
write_bitstream -force -bin_file -cell $rp [file join $out rm_normal_partial.bit]
close_design
open_checkpoint $lowlight_dcp
set rp [get_cells -quiet $rp_cell]
if {[llength $rp] != 1} { error "Lowlight configuration RP cell not found: $rp_cell" }
write_bitstream -force -bin_file -cell $rp [file join $out rm_lowlight_partial.bit]
close_design
puts "PHASE1_DFX_BITSTREAMS_WRITTEN"
exit
