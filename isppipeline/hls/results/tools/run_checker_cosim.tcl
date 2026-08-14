set repo [file normalize [file join [file dirname [info script]] .. ..]]
cd [file join $repo results]
open_project -reset hls_work/checker_cosim
file mkdir hls_work/checker_cosim/local
file copy -force [file join $repo src checker.cpp] hls_work/checker_cosim/local/checker.cpp
file copy -force tools/checker_hls_tb.cpp hls_work/checker_cosim/local/checker_hls_tb.cpp
cd hls_work/checker_cosim
set_top checker_scan
add_files local/checker.cpp -cflags "-I[file join $repo include]"
add_files -tb local/checker_hls_tb.cpp -cflags "-I[file join $repo include]"
open_solution -reset solution1 -flow_target vivado
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0
config_interface -m_axi_alignment_byte_size 16 -m_axi_max_widen_bitwidth 128
csynth_design
cosim_design -rtl verilog -tool xsim -trace_level none -argv "[file join $repo results checker_validation_2026-08-06 checker_cosim_crops_2026-08-06.csv] [file join $repo results checker_validation_2026-08-06 checker_crop_cosim_frames_2026-08-06.csv]"
exit
