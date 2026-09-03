proc required_env {name} {
    if {![info exists ::env($name)]} { error "missing environment variable $name" }
    return $::env($name)
}
set hls_root [file normalize [required_env DFXISP_HLS_ROOT]]
set top_name [required_env DFXISP_HLS_TOP]
set src_file [required_env DFXISP_HLS_SRC]
set workspace [file normalize [required_env DFXISP_HLS_WORKSPACE]]
set project_dir [file join $workspace ${top_name}_project]
set stage_dir [file join $workspace ${top_name}_src]
file delete -force $stage_dir
file mkdir [file join $stage_dir include]
file copy -force [file join $hls_root $src_file] [file join $stage_dir [file tail $src_file]]
foreach header [glob [file join $hls_root include *.hpp]] {
    file copy -force $header [file join $stage_dir include [file tail $header]]
}
cd $workspace
open_project -reset $project_dir
set_top $top_name
add_files [file join $stage_dir [file tail $src_file]] -cflags "-std=c++17 -I[file join $stage_dir include]"
open_solution -reset solution1 -flow_target vivado
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0 -name default
config_interface -m_axi_alignment_byte_size 16 -m_axi_max_widen_bitwidth 128
csynth_design
export_design -format ip_catalog
close_project
exit
