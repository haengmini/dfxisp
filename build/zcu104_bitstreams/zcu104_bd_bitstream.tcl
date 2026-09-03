proc required_env {name} {
    if {![info exists ::env($name)]} { error "missing environment variable $name" }
    return $::env($name)
}
set module_name [required_env DFXISP_MODULE]
set hls_top [required_env DFXISP_HLS_TOP]
set ip_repo [file normalize [required_env DFXISP_IP_REPO]]
set output_root [file normalize [required_env DFXISP_OUTPUT_ROOT]]
set project_dir [file join $output_root vivado $module_name]
create_project -force $module_name $project_dir -part xczu7ev-ffvc1156-2-e
set_property target_language Verilog [current_project]
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:* ps]
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP2 {0} CONFIG.PSU__USE__S_AXI_GP2 {1} CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {100}] $ps
set hls [create_bd_cell -type ip -vlnv xilinx.com:hls:${hls_top}:1.0 $hls_top]
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_pl]
set ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:* axi_ctrl]
set mem [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:* axi_mem]
set mem_ports [get_bd_intf_pins -quiet ${hls}/m_axi_*]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $ctrl
set_property -dict [list CONFIG.NUM_SI [llength $mem_ports] CONFIG.NUM_MI {1}] $mem
connect_bd_net [get_bd_pins ps/pl_clk0] [get_bd_pins ps/maxihpm0_fpd_aclk] [get_bd_pins ps/saxihp0_fpd_aclk] [get_bd_pins ${hls}/ap_clk] [get_bd_pins rst_pl/slowest_sync_clk] [get_bd_pins axi_ctrl/aclk] [get_bd_pins axi_mem/aclk]
connect_bd_net [get_bd_pins ps/pl_resetn0] [get_bd_pins rst_pl/ext_reset_in]
connect_bd_net [get_bd_pins rst_pl/peripheral_aresetn] [get_bd_pins ${hls}/ap_rst_n] [get_bd_pins axi_ctrl/aresetn] [get_bd_pins axi_mem/aresetn]
connect_bd_intf_net [get_bd_intf_pins ps/M_AXI_HPM0_FPD] [get_bd_intf_pins axi_ctrl/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_ctrl/M00_AXI] [get_bd_intf_pins ${hls}/s_axi_control]
set port_index 0
foreach mem_port $mem_ports {
    connect_bd_intf_net $mem_port [get_bd_intf_pins [format "axi_mem/S%02d_AXI" $port_index]]
    incr port_index
}
connect_bd_intf_net [get_bd_intf_pins axi_mem/M00_AXI] [get_bd_intf_pins ps/S_AXI_HP0_FPD]
make_bd_intf_pins_external [get_bd_intf_pins ps/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps/FIXED_IO]
assign_bd_address
validate_bd_design
save_bd_design
set bd_file [get_files system.bd]
generate_target all $bd_file
make_wrapper -files $bd_file -top
add_files -norecurse [file join $project_dir ${module_name}.gen sources_1 bd system hdl system_wrapper.v]
update_compile_order -fileset sources_1
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
set_property strategy Performance_Explore [get_runs impl_1]
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "implementation did not complete: [get_property STATUS [get_runs impl_1]]" }
set candidates [glob -nocomplain [file join $project_dir ${module_name}.runs impl_1 *.bit]]
if {[llength $candidates] != 1} { error "bitstream output not found" }
file mkdir [file join $output_root bitstreams]
file copy -force [lindex $candidates 0] [file join $output_root bitstreams ${module_name}_zcu104.bit]
open_run impl_1
report_utilization -file [file join $output_root bitstreams ${module_name}_utilization.rpt]
report_timing_summary -file [file join $output_root bitstreams ${module_name}_timing.rpt]
puts "BITSTREAM_COMPLETE [file join $output_root bitstreams ${module_name}_zcu104.bit]"
exit
