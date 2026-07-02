#pragma once

#include <cstdint>

// DFX AI-ISP HLS C-sim interface (reset 2026-07-01).
//
// Architecture: shared baseline ISP core + mutually exclusive mode-specific
// tone RMs (see RESEARCH.md). The tone RM slot *wraps* the shared baseline core:
//
//   NORMAL:
//     raw -> RM_NORMAL_TONE (identity bypass)
//         -> baseline_isp_core (demosaic + BLC + AWB + CCM, no gain/gamma)
//         -> RGB32  (H x W)
//
//   LOW_LIGHT:
//     raw -> RM_LOW_LIGHT_TONE.front  (2x2 RAW binning, before precision loss)
//         -> baseline_isp_core (demosaic + BLC + AWB + CCM, no gain/gamma)
//         -> RM_LOW_LIGHT_TONE.back   (low-light gain + gamma-4.0 tone)
//         -> RGB32  (H/2 x W/2, shape-changing Policy A)
//
// Invariants proven by the C-sim golden gates (RESEARCH.md §8.2):
//   * exactly one tone RM per frame (mutually exclusive)
//   * gain/gamma live only in the tone RMs, never duplicated in the baseline core
//   * output metadata reports mode, selected RM, and output shape
//
// Pixel format:
//   input : pseudo-RAW Bayer RGGB, 12-bit values stored in uint16_t
//   output: packed RGB888 in uint32_t, 0x00RRGGBB
//   rgb_out capacity must be >= in_width * in_height (low-light uses <= that).

enum DfxIspMode : int {
    DFXISP_MODE_NORMAL = 0,
    DFXISP_MODE_LOW_LIGHT = 1,
    DFXISP_MODE_AUTO = 2,
};

enum DfxIspSelectedRm : int {
    DFXISP_RM_NORMAL_TONE = 0,     // identity bypass tone RM (normal scenes)
    DFXISP_RM_LOW_LIGHT_TONE = 1,  // 2x2 binning + gain + gamma tone RM (dark scenes)
};

// Output metadata for the mutually exclusive tone RM slot.
struct DfxIspResult {
    int out_width;      // baseline-core / RM output width
    int out_height;     // baseline-core / RM output height
    int selected_mode;  // DFXISP_MODE_NORMAL or DFXISP_MODE_LOW_LIGHT (resolved AUTO)
    int selected_rm;    // DfxIspSelectedRm
};

extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t dark_pixel_threshold,
    DfxIspResult* result);
