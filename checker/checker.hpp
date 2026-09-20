#pragma once

#include <cstdint>

// =============================================================================
// File   : checker.hpp
// Updated: 2026-08-06
// Function: Shared, stateless RAW scene measurement used by the unified Arm2
//           top and the standalone static-region checker HLS top.
// Note: DFXISP_MODE_*/DFXISP_HYST_* below are inlined from dfxisp_accel.hpp
//       (origin repo haengmini/dfxisp) so this module has no cross-file
//       dependency; keep in sync if the origin enum changes.
// =============================================================================

enum DfxIspMode {
    DFXISP_MODE_NORMAL = 0,
    DFXISP_MODE_LOW_LIGHT = 1,
    DFXISP_MODE_AUTO = 2,
};

enum DfxIspHystFlags {
    DFXISP_HYST_ABOVE_ENTER = 1 << 0,  // dark ratio > enter threshold (64%)
    DFXISP_HYST_BELOW_EXIT = 1 << 1,   // dark ratio < exit threshold (60%)
};

// Canonical Arm2 policy defaults. Arm3 receives its runtime policy through the
// HLS AXI-Lite registers, so these values are not duplicated in RTL.
static constexpr int DARK_RATIO_PCT = 62;
static constexpr int HYST_ENTER_PCT = 64;
static constexpr int HYST_EXIT_PCT = 60;

static inline int checker_select_mode(const uint16_t* raw, int width, int height, int mode,
                                      uint16_t dark_pixel_threshold, int verdict_pct,
                                      int enter_pct, int exit_pct, int& hyst_flags,
                                      int& dark_count) {
    // Forced modes report flags matching the forced state so the hysteresis
    // block (if wired) tracks the override instead of fighting it.
    if (mode == DFXISP_MODE_NORMAL) {
        dark_count = 0;
        hyst_flags = DFXISP_HYST_BELOW_EXIT;
        return DFXISP_MODE_NORMAL;
    }
    if (mode == DFXISP_MODE_LOW_LIGHT) {
        dark_count = 0;
        hyst_flags = DFXISP_HYST_ABOVE_ENTER;
        return DFXISP_MODE_LOW_LIGHT;
    }
    const int n = width * height;
    int dark = 0;
    for (int i = 0; i < n; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=16 max=2073600
        if (raw[i] < dark_pixel_threshold) ++dark;
    }
    const int dark_pct100 = dark * 100;
    dark_count = dark;
    const bool above_enter = dark_pct100 > enter_pct * n;
    const bool below_exit = dark_pct100 < exit_pct * n;
    hyst_flags = (above_enter ? DFXISP_HYST_ABOVE_ENTER : 0) |
                 (below_exit ? DFXISP_HYST_BELOW_EXIT : 0);
    // The single-frame verdict (Arm2 runtime branch / golden contract) keeps
    // the deployed C1 threshold (62), independent of the Schmitt band edges;
    // the Schmitt state machine consumes the flags outside this core.
    return (dark_pct100 > verdict_pct * n) ? DFXISP_MODE_LOW_LIGHT : DFXISP_MODE_NORMAL;
}

// Arm2 compatibility overload: its call site and policy remain exactly as
// before, with the canonical compile-time defaults and no ratio consumer.
static inline int checker_select_mode(const uint16_t* raw, int width, int height, int mode,
                                      uint16_t dark_pixel_threshold, int& hyst_flags) {
    int dark_count = 0;
    return checker_select_mode(raw, width, height, mode, dark_pixel_threshold,
                               DARK_RATIO_PCT, HYST_ENTER_PCT, HYST_EXIT_PCT,
                               hyst_flags, dark_count);
}
