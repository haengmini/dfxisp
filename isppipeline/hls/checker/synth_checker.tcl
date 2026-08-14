# Vitis HLS 2024.1 batch synthesis for the static checker scan core.
set repo_dir [file normalize [file join [file dirname [info script]] ..]]
set build_root /tmp/dfxisp_checker_hls
set staged_src /tmp/dfxisp_checker_src
file mkdir $staged_src/include
file copy -force [file join $repo_dir src checker.cpp] $staged_src/checker.cpp
file copy -force [file join $repo_dir include checker.hpp] $staged_src/include/checker.hpp
file copy -force [file join $repo_dir include dfxisp_accel.hpp] $staged_src/include/dfxisp_accel.hpp
cd /tmp
open_project -reset dfxisp_checker_hls
set_top checker_scan
add_files dfxisp_checker_src/checker.cpp -cflags "-I/tmp/dfxisp_checker_src/include"
open_solution -reset solution1 -flow_target vivado
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0 -name default
config_interface -m_axi_alignment_byte_size 16 -m_axi_max_widen_bitwidth 128
csynth_design
exit
