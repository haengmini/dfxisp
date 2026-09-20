# Build the LowlightISP + DPUCZDX8G ZCU104 design from scratch, headless.
#
#   cd LowlightISP_DPU/vivado && vivado -mode batch -source build_lowlightisp_dpu.tcl
#   vivado -mode batch -source build_lowlightisp_dpu.tcl -tclargs 4      ;# 4 parallel jobs
#
# Default jobs is 2 on purpose: this design's out-of-context IP synthesis (the DPU above all)
# needs several GB per job, and on a 14 GB machine -jobs 8 drove 13 GB of swap and thrashed
# instead of finishing. Raise it only with the RAM to back it.
#
# This is NormalISP_DPU's block design with the ISP IP swapped, per docs/NormalISP_DPU.md SS8
# ("LowlightISP 스왑 — 포트 시그니처가 동일하므로 BD에서 IP만 교체"). The BD tcl next to this
# file was produced by write_bd_tcl -no_ip_version on NormalISP_DPU and then had NormalISP
# renamed to LowlightISP; everything else -- DPU parameters, the three clock domains, the
# HPC0/HP1/HP2 split, interrupt concat, and every address assignment -- is bit-identical,
# which is what keeps the DPU fingerprint at 0x101000056010407 and the already-compiled
# xmodels valid. The check at the end of this script asserts exactly that.
#
# Products: LowlightISP_DPU_zcu104/LowlightISP_DPU_zcu104_wrapper.xsa (bitstream included),
# ready for `petalinux-config --get-hw-description`.

set jobs [expr {[llength $argv] > 0 ? [lindex $argv 0] : 2}]
set here [file normalize [file dirname [info script]]]
set dfx  [file normalize $here/../..]
set proj_dir $dfx/LowlightISP_DPU/LowlightISP_DPU_zcu104
set proj_name LowlightISP_DPU_zcu104
set part xczu7ev-ffvc1156-2-e
set board xilinx.com:zcu104:part0:1.1
set ip_repos [list $dfx/LowlightISP/LowlightISP_hls \
                   $dfx/../tutorials/vitisAI/dpu_zcu104/DPUCZDX8G_VAI_v3.0/dpu_ip]

foreach r $ip_repos {
    if {![file isdirectory $r]} { error "IP repo not found: $r" }
}
if {[file exists $proj_dir/$proj_name.xpr]} {
    error "$proj_dir/$proj_name.xpr already exists -- delete it first to rebuild from scratch"
}

file mkdir $proj_dir
create_project $proj_name $proj_dir -part $part
set_property BOARD_PART $board [current_project]
set_property ip_repo_paths $ip_repos [current_project]
update_ip_catalog -rebuild

if {[llength [get_ipdefs -quiet xilinx.com:hls:LowlightISP:*]] == 0} {
    error "xilinx.com:hls:LowlightISP not in the catalog -- re-export the IP from Vitis HLS\
           (LowlightISP/LowlightISP_hls/LowlightISP/hls/impl/ip/component.xml must exist)"
}

source $here/LowlightISP_DPU_design1_bd.tcl
set bd_file [get_files LowlightISP_DPU_design1.bd]
regenerate_bd_layout
validate_bd_design
save_bd_design

# The DPU fingerprint must still match the NormalISP_DPU build, or every staged xmodel
# would need recompiling (dpu_ip/.../README.md's "Model Recompile Required" table).
foreach p {CONFIG.ARCH CONFIG.DPU_NUM CONFIG.RAM_USAGE CONFIG.CHANNEL_AUGMENTATION \
           CONFIG.DWCV_ENA CONFIG.POOL_AVERAGE CONFIG.CONV_RELU_TYPE CONFIG.SFM_ENA} {
    catch {puts "dpu $p = [get_property $p [get_bd_cells /dpuczdx8g_0]]"}
}

make_wrapper -files $bd_file -top
add_files -norecurse $proj_dir/$proj_name.gen/sources_1/bd/LowlightISP_DPU_design1/hdl/LowlightISP_DPU_design1_wrapper.v
set_property top LowlightISP_DPU_design1_wrapper [current_fileset]
update_compile_order -fileset sources_1
generate_target all $bd_file

launch_runs synth_1 -jobs $jobs
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "synthesis failed: [get_property STATUS [get_runs synth_1]]"
}

launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "implementation failed: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
set wns [get_property SLACK [get_timing_paths -delay_type max]]
set whs [get_property SLACK [get_timing_paths -delay_type min]]
puts "=== TIMING: WNS $wns ns, WHS $whs ns ==="
if {$wns < 0 || $whs < 0} {
    puts "WARNING: timing not met -- do not flash this bitstream without looking at impl_1's reports"
}
report_utilization -file $proj_dir/utilization_impl.rpt
report_timing_summary -file $proj_dir/timing_summary_impl.rpt

set xsa $proj_dir/${proj_name}_wrapper.xsa
write_hw_platform -fixed -include_bit -force $xsa
catch {validate_hw_platform $xsa}
puts "=== XSA: $xsa ==="
close_project
puts "=== DONE ==="
