# checker/package_checker_ip.tcl -- reproducible Vivado 2024.1 IP-XACT package
# Run: vivado -mode batch -source checker/package_checker_ip.tcl
set script_dir [file normalize [file dirname [info script]]]
set repo_dir   [file normalize [file join $script_dir ..]]
set build_dir  [file join $script_dir .package_checker_ip]
set out_dir    [file join $script_dir ip_repo]
set hls_rtl_dir /tmp/dfxisp_checker_hls/solution1/syn/verilog

# Regenerate the HLS RTL outside the repository so packaging never relies on a
# stale or untracked csynth directory.
exec vitis_hls -f [file join $script_dir synth_checker.tcl]
if {![file exists [file join $hls_rtl_dir checker_scan.v]]} {
  error "checker_scan csynth RTL was not generated"
}

create_project -force checker_ip_pack $build_dir -part xczu7ev-ffvc1156-2-e
set_property target_language Verilog [current_project]
add_files [list \
  {*}[glob [file join $hls_rtl_dir *.v]] \
  [file join $script_dir checker_ip.v] \
  [file join $script_dir checker_hysteresis.v] \
  [file join $script_dir dfxc_trigger_adapter.v] \
  [file join $script_dir pr_latency_probe.v]]
set_property top checker_ip [current_fileset]
update_compile_order -fileset sources_1

ipx::package_project -root_dir $out_dir -vendor user.org -library user \
  -taxonomy /UserIP -import_files -set_current true -force
set core [ipx::current_core]
set_property name checker_ip $core
set_property display_name {DFX ISP Static Scene Checker} $core
set_property description {RAW scene scan, Schmitt policy, PG374 trigger adapter, and latency counters} $core
set_property version 1.0 $core
set_property core_revision 1 $core
ipx::infer_bus_interfaces xilinx.com:interface:aximm_rtl:1.0 $core
# Vivado derives interface names from the lowercase HDL port prefixes.
foreach busif {s_axi_control s_axi_status m_axi_gmem0} {
  if {[llength [ipx::get_bus_interfaces $busif -of_objects $core]]} {
    ipx::associate_bus_interfaces -busif $busif -clock aclk $core
  }
}
ipx::create_xgui_files $core
ipx::update_checksums $core
ipx::check_integrity -quiet $core
ipx::save_core $core
close_project
puts "PACKAGED checker_ip at $out_dir"
