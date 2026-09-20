#include "checker.hpp"

// =============================================================================
// File   : checker.cpp
// Updated: 2026-08-06
// Function: Standalone static-region HLS scene-checker measurement top.
// =============================================================================
extern "C" void checker_scan(
    const uint16_t* raw_bayer, int width, int height, int mode,
    uint16_t dark_pixel_threshold,
    int verdict_pct, int enter_pct, int exit_pct,
    int* selected_mode, int* hyst_flags, int* dark_count) {
// depth is a C/RTL co-simulation BFM sizing hint, not synthesized memory size.
// 2048 matches dfxisp_accel(): enough headroom for the current multi-call
// fixture while avoiding the wrapc failures seen with a full-HD depth model.
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0 depth=2048 max_widen_bitwidth=128
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=mode bundle=control
#pragma HLS INTERFACE s_axilite port=dark_pixel_threshold bundle=control
#pragma HLS INTERFACE s_axilite port=verdict_pct bundle=control
#pragma HLS INTERFACE s_axilite port=enter_pct bundle=control
#pragma HLS INTERFACE s_axilite port=exit_pct bundle=control
#pragma HLS INTERFACE s_axilite port=selected_mode bundle=control
#pragma HLS INTERFACE ap_vld port=hyst_flags
#pragma HLS INTERFACE s_axilite port=dark_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    if (!raw_bayer || width <= 0 || height <= 0) {
        if (selected_mode) *selected_mode = DFXISP_MODE_NORMAL;
        if (hyst_flags) *hyst_flags = DFXISP_HYST_BELOW_EXIT;
        if (dark_count) *dark_count = 0;
        return;
    }
    int flags = 0, measured_dark_count = 0;
    const int selected = checker_select_mode(
        raw_bayer, width, height, mode, dark_pixel_threshold,
        verdict_pct, enter_pct, exit_pct, flags, measured_dark_count);
    if (selected_mode) *selected_mode = selected;
    if (hyst_flags) *hyst_flags = flags;
    if (dark_count) *dark_count = measured_dark_count;
}
