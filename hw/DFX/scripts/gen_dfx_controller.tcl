# Generate + configure the AMD DFX Controller IP (xilinx.com:ip:dfx_controller:1.0)
# for DFXISP: 1 Virtual Socket, 2 HW triggers mapped trigger0->RM_0(NORMAL) /
# trigger1->RM_1(LOW_LIGHT), with per-RM shutdown/reset wired for hardware
# operation. Verified on Vivado 2024.1 (2026-08-06 port-contract probe,
# 2026-09-28 RM-level config unblock + full IP generation) -- see
# results/pr_controller/dfxc_adapter.md.
#
# 2024.1 batch-mode notes (2026-09-28 re-probe, corrects the 2026-08-06 record):
#  * The dotted-path API (dfx_controller_v1_0::set_property CONFIG.VS.VS_0.RM.*)
#    genuinely CANNOT create/configure RM-level keys in batch: it always
#    errors with "RM ... doesn't exist within Virtual Socket Manager", even
#    right after setting TRIGGERx_TO_RM to that same RM name. This appears to
#    be an ordering/materialization limitation of the incremental API, not a
#    hard GUI-only restriction.
#  * WORKAROUND (confirmed working, full generation verified): build the
#    complete VS dict -- both RMs, each with
#    SHUTDOWN_REQUIRED/RESET_REQUIRED/RESET_DURATION/BS already populated --
#    and assign it in one shot via plain `set_property CONFIG.ALL_PARAMS
#    $dict $ip` (not the namespaced API). A complete, internally consistent
#    dict succeeds; `validate_ip` and `generate_target ... synthesis` both
#    pass with all 49 documented ports generated.
#  * RESET_REQUIRED takes "no"/"high"/"low" (not "yes"/"no").
#  * UltraScale+ requires EXACTLY 1 bitstream (BS) entry per RM -- the
#    IP-default two-BS-slot RM_0 template (BS.0 + BS.1, meant for other
#    device families/compression modes) fails generation on this part with
#    "UltraScale+ devices require exactly 1 bitstream per RM". Give each RM
#    a single BS.0 entry only.
#
# Usage: vivado -mode batch -source gen_dfx_controller.tcl
#        (expects an open/created project targeting xczu7ev-ffvc1156-2-e)

set part xczu7ev-ffvc1156-2-e
if {[catch {current_project}]} {
    file mkdir ./build
    create_project -force dfxc_ip ./build/dfxc_ip_proj -part $part
}

create_ip -name dfx_controller -vendor xilinx.com -library ip -version 1.0 \
    -module_name dfx_controller_0

set ip [get_ips dfx_controller_0]

# BS.0 ADDR/SIZE are still 0 -- fill in the real DDR bitstream table
# (RM_0 -> rm_normal_partial.bin, RM_1 -> rm_lowlight_partial.bin staging
# addresses/sizes) once the Stage 6 DDR layout is decided. IP generation
# passes with zero placeholders, but they cannot perform an actual swap.
set full_params {VS {VS_0 {ID 0 NAME VS_0 RM {\
RM_0 {ID 0 NAME RM_0 SHUTDOWN_REQUIRED hw RESET_REQUIRED high RESET_DURATION 8 \
      BS {0 {ID 0 ADDR 0 SIZE 0 CLEAR 0}}} \
RM_1 {ID 1 NAME RM_1 SHUTDOWN_REQUIRED hw RESET_REQUIRED high RESET_DURATION 8 \
      BS {0 {ID 0 ADDR 0 SIZE 0 CLEAR 0}}}} \
NUM_HW_TRIGGERS 2 TRIGGER_TO_RM {0 RM_0 1 RM_1} POR_RM RM_0}} CP_FAMILY ultrascale_plus}

set_property CONFIG.ALL_PARAMS $full_params $ip
validate_ip $ip

generate_target {instantiation_template synthesis} $ip
puts "ALL_PARAMS: [get_property CONFIG.ALL_PARAMS $ip]"
puts "Done -- port template: <proj>.gen/sources_1/ip/dfx_controller_0/dfx_controller_0.veo"
