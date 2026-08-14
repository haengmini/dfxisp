# This script segment is generated automatically by AutoPilot

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


