# Vitis HLS build scaffold for DFXISP.
# Defaults target ZCU104's Zynq UltraScale+ MPSoC part; override with:
#   DFXISP_HLS_PART=<part> DFXISP_HLS_CLOCK=<ns> DFXISP_HLS_FLOW=<csim|csynth|cosim|export> vitis_hls -f scripts/vitis_hls.tcl
# or Tcl args:
#   vitis_hls -f scripts/vitis_hls.tcl -- -part <part> -clock <ns> -flow <flow>

set script_dir [file dirname [file normalize [info script]]]
set hls_root [file normalize [file join $script_dir ".."]]

set top_name "dfxisp_accel"
set project_dir [file join $hls_root "build" "vitis_hls" $top_name]
set solution_name "solution1"
set part_name "xczu7ev-ffvc1156-2-e"
set clock_period "5.0"
set flow "csim"

if {[info exists ::env(DFXISP_HLS_PROJECT)]} {
    set project_dir $::env(DFXISP_HLS_PROJECT)
}
if {[info exists ::env(DFXISP_HLS_PART)]} {
    set part_name $::env(DFXISP_HLS_PART)
}
if {[info exists ::env(DFXISP_HLS_CLOCK)]} {
    set clock_period $::env(DFXISP_HLS_CLOCK)
}
if {[info exists ::env(DFXISP_HLS_FLOW)]} {
    set flow $::env(DFXISP_HLS_FLOW)
}

set i 0
while {$i < $argc} {
    set key [lindex $argv $i]
    incr i
    if {$key eq "--"} {
        continue
    }
    if {$i >= $argc} {
        error "missing value for $key"
    }
    set val [lindex $argv $i]
    incr i
    switch -- $key {
        -project { set project_dir $val }
        -part { set part_name $val }
        -clock { set clock_period $val }
        -flow { set flow $val }
        default { error "unknown argument $key (expected -project, -part, -clock, -flow)" }
    }
}

puts "DFXISP Vitis HLS scaffold"
puts "  top     : $top_name"
puts "  project : $project_dir"
puts "  part    : $part_name"
puts "  clock   : $clock_period ns"
puts "  flow    : $flow"

open_project -reset $project_dir
set_top $top_name
add_files [file join $hls_root "src" "dfxisp_accel.cpp"] -cflags "-std=c++17 -I[file join $hls_root include]"
add_files -tb [file join $hls_root "tests" "test_dfxisp_csim.cpp"] -cflags "-std=c++17 -I[file join $hls_root include]"
open_solution -reset $solution_name
set_part $part_name
create_clock -period $clock_period -name default

switch -- $flow {
    csim {
        csim_design
    }
    csynth {
        csim_design
        csynth_design
    }
    cosim {
        csim_design
        csynth_design
        cosim_design
    }
    export {
        csim_design
        csynth_design
        export_design -format ip_catalog
    }
    default {
        error "unsupported DFXISP_HLS_FLOW '$flow' (use csim, csynth, cosim, or export)"
    }
}

close_project
