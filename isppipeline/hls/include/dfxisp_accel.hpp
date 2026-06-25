#pragma once

#include <cstdint>

// DFX AI-ISP HLS C-sim interface.
// Pixel format:
// - input: pseudo-RAW Bayer GRBG, 12-bit values stored in uint16_t
// - output: packed RGB888 in uint32_t, 0x00RRGGBB
// Mode policy:
// - NORMAL: lightweight Bayer-to-RGB path
// - LOW_LIGHT: 2x2 local binning/gain-inspired brightening path
// - AUTO: scene checker selects LOW_LIGHT when average luminance is below threshold

enum DfxIspMode : int {
    DFXISP_MODE_NORMAL = 0,
    DFXISP_MODE_LOW_LIGHT = 1,
    DFXISP_MODE_AUTO = 2,
};

extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold);
