# This script segment is generated automatically by AutoPilot

set name checker_scan_mul_32s_32s_32_1_1
if {${::AESL::PGuard_rtl_comp_handler}} {
	::AP::rtl_comp_handler $name BINDTYPE {op} TYPE {mul} IMPL {auto} LATENCY 0 ALLOW_PRAGMA 1
}


if {${::AESL::PGuard_rtl_comp_handler}} {
	::AP::rtl_comp_handler checker_scan_gmem0_m_axi BINDTYPE {interface} TYPE {adapter} IMPL {m_axi}
}


# clear list
if {${::AESL::PGuard_autoexp_gen}} {
    cg_default_interface_gen_dc_begin
    cg_default_interface_gen_bundle_begin
    AESL_LIB_XILADAPTER::native_axis_begin
}

set axilite_register_dict [dict create]
set port_control {
raw_bayer { 
	dir I
	width 64
	depth 1
	mode ap_none
	offset 16
	offset_end 27
}
width { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 28
	offset_end 35
}
height { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 36
	offset_end 43
}
mode { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 44
	offset_end 51
}
dark_pixel_threshold { 
	dir I
	width 16
	depth 1
	mode ap_none
	offset 52
	offset_end 59
}
verdict_pct { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 60
	offset_end 67
}
enter_pct { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 68
	offset_end 75
}
exit_pct { 
	dir I
	width 32
	depth 1
	mode ap_none
	offset 76
	offset_end 83
}
selected_mode { 
	dir O
	width 32
	depth 1
	mode ap_vld
	offset 84
	offset_end 91
}
dark_count { 
	dir O
	width 32
	depth 1
	mode ap_vld
	offset 100
	offset_end 107
}
ap_start { }
ap_done { }
ap_ready { }
ap_idle { }
interrupt {
}
}
dict set axilite_register_dict control $port_control


# Native S_AXILite:
if {${::AESL::PGuard_simmodel_gen}} {
	if {[info proc ::AESL_LIB_XILADAPTER::s_axilite_gen] == "::AESL_LIB_XILADAPTER::s_axilite_gen"} {
		eval "::AESL_LIB_XILADAPTER::s_axilite_gen { \
			id 11 \
			corename checker_scan_control_axilite \
			name checker_scan_control_s_axi \
			ports {$port_control} \
			op interface \
			interrupt_clear_mode TOW \
			interrupt_trigger_type default \
			is_flushable 0 \
			is_datawidth64 0 \
			is_addrwidth64 1 \
		} "
	} else {
		puts "@W \[IMPL-110\] Cannot find AXI Lite interface model in the library. Ignored generation of AXI Lite  interface for 'control'"
	}
}

if {${::AESL::PGuard_rtl_comp_handler}} {
	::AP::rtl_comp_handler checker_scan_control_s_axi BINDTYPE interface TYPE interface_s_axilite
}

# Direct connection:
if {${::AESL::PGuard_autoexp_gen}} {
eval "cg_default_interface_gen_dc { \
    id 12 \
    name hyst_flags \
    type other \
    dir O \
    reset_level 0 \
    sync_rst true \
    corename dc_hyst_flags \
    op interface \
    ports { hyst_flags { O 32 vector } hyst_flags_ap_vld { O 1 bit } } \
} "
}


# Adapter definition:
set PortName ap_clk
set DataWd 1 
if {${::AESL::PGuard_autoexp_gen}} {
if {[info proc cg_default_interface_gen_clock] == "cg_default_interface_gen_clock"} {
eval "cg_default_interface_gen_clock { \
    id -1 \
    name ${PortName} \
    reset_level 0 \
    sync_rst true \
    corename apif_ap_clk \
    data_wd ${DataWd} \
    op interface \
}"
} else {
puts "@W \[IMPL-113\] Cannot find bus interface model in the library. Ignored generation of bus interface for '${PortName}'"
}
}


# Adapter definition:
set PortName ap_rst_n
set DataWd 1 
if {${::AESL::PGuard_autoexp_gen}} {
if {[info proc cg_default_interface_gen_reset] == "cg_default_interface_gen_reset"} {
eval "cg_default_interface_gen_reset { \
    id -2 \
    name ${PortName} \
    reset_level 0 \
    sync_rst true \
    corename apif_ap_rst_n \
    data_wd ${DataWd} \
    op interface \
}"
} else {
puts "@W \[IMPL-114\] Cannot find bus interface model in the library. Ignored generation of bus interface for '${PortName}'"
}
}



# merge
if {${::AESL::PGuard_autoexp_gen}} {
    cg_default_interface_gen_dc_end
    cg_default_interface_gen_bundle_end
    AESL_LIB_XILADAPTER::native_axis_end
}


