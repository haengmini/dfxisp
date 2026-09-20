#pragma once

#include <cstdint>

// =============================================================================
// File   : NormalISP/NormalISP.hpp
// Function: NormalISP -- the reference "standard" ISP module, restructured to
//           follow the AMD Vitis Vision Library L3 `isppipeline` example
//           (Xilinx/Vitis_Libraries, vision/L3/examples/isppipeline) in stage
//           ORDER and stage DOMAIN, instead of the hand-rolled RGB-domain
//           ordering used by the project's original architecture.
//
// Why this exists (see docs/NormalISP.md):
//   The original approach corrects in the RGB domain AFTER demosaic and uses
//   fixed white balance with an identity CCM. The Vitis Vision reference
//   corrects in the Bayer domain BEFORE demosaic, applies an adaptive AWB
//   stage after it, and uses a real color correction matrix. That is a
//   structural difference, not a constant difference, so a fair "standard ISP
//   baseline" claim needs this pipeline.
//
// This module is ADDITIVE: the project's original normal-mode implementation,
// its golden vectors and the deployed BLC/checker decisions are untouched.
// Whether NormalISP replaces it as the deployed normal-condition module is a
// separate decision.
//
// Stage order (Vitis Vision isppipeline):
//   RAW Bayer(12-bit)
//     -> (1) blackLevelCorrection   [Bayer domain, subtract + range rescale]
//     -> (2) gaincontrol            [Bayer domain, per-Bayer-position R/B gain]
//     -> (3) demosaicing            [RGGB -> RGB, 12-bit preserved]
//     -> (4) AWB                    [RGB domain, per-frame adaptive, bypassable]
//     -> (5) colorcorrectionmatrix  [RGB domain, real 3x3 Q8 matrix]
//     -> (6) quantization 12->8     [>>4; Vitis' optional dithering omitted]
//     -> (7) gammacorrection        [256-entry LUT, gamma 2.0, shared with
//                                    LowlightISP for cross-comparability]
//     -> packed RGB888 0x00RRGGBB   [Vitis' rgb2yuyv output CSC omitted --
//                                    downstream DPU/detector consumes RGB]
//
// All arithmetic is integer and bit-exact against tools/gen_default_isp_golden.py
// (origin repo haengmini/dfxisp).
// =============================================================================

// AWB mode. Mirrors the Vitis Vision example's `mode_reg` bit 0, which selects
// between the adaptive AWB path (fifo_awb) and a bypass (fifo_copy).
enum NormalISPAwbMode : int {
    NORMAL_ISP_AWB_OFF = 0,  // bypass: Bayer-domain gaincontrol only
    NORMAL_ISP_AWB_ON = 1,   // adaptive per-frame gray-world AWB
};

// Development/analysis top: exposes the AWB mode switch.
//   raw_bayer : RAW Bayer RGGB, 12-bit values in uint16_t (W*H)
//   rgb_out   : packed RGB888 0x00RRGGBB (capacity >= W*H); shape is preserved
//   awb_mode  : NormalISPAwbMode
// out_width/out_height always equal width/height (shape-preserving pipeline).
extern "C" void NormalISP_dev(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int awb_mode,
    int* out_width,
    int* out_height);

// Board / DFX top: AWB fixed ON. Port list is IDENTICAL (type, order, count)
// to LowlightISP() so both are valid implementations of the same
// reconfigurable-partition slot -- DFX requires identical port signatures
// across implementations sharing one partition (SPEC.md §7, origin repo).
extern "C" void NormalISP(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int* out_width,
    int* out_height);
