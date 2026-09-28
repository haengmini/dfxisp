# DFXISP reconfigurable partition floorplan (ZCU104 xczu7ev)
# Cell path is set by the Phase-1 static-shell build.
set rp_cell [get_cells -quiet dfx_demo_i/isp_rp]
if {[llength $rp_cell] != 1} {
  error "Expected exactly one RP cell at dfx_demo_i/isp_rp"
}
set_property HD.RECONFIGURABLE true $rp_cell
create_pblock pblock_isp_rp
add_cells_to_pblock [get_pblocks pblock_isp_rp] $rp_cell
resize_pblock [get_pblocks pblock_isp_rp] -add {CLOCKREGION_X1Y0:CLOCKREGION_X2Y0}
set_property CONTAIN_ROUTING true [get_pblocks pblock_isp_rp]
set_property SNAPPING_MODE ON [get_pblocks pblock_isp_rp]
