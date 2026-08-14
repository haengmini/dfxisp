set repo [file normalize [file join [file dirname [info script]] .. ..]]
open_project -reset /tmp/dfxisp_checker_crop_csim
set_top checker_scan
add_files [file join $repo results tools checker_design_wrapper.cpp] -cflags "-I[file join $repo include]"
add_files -tb [file join $repo results tools checker_hls_csim_tb.cpp] -cflags "-I[file join $repo include]"
open_solution -reset solution1 -flow_target vivado
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0
csim_design -argv "[file join $repo results checker_validation_2026-08-06 checker_cosim_crops_2026-08-06.csv] [file join $repo results checker_validation_2026-08-06 checker_crop_csim_frames_2026-08-06.csv]"
exit
