#pragma once

#include <cstdint>

// =============================================================================
// File   : isppipeline/hls/include/lowlight_isp.hpp
// Added  : 2026-08-06
// Function: lowlight_ISP -- the proposal low-light arm (v2), rebuilt from the
//           principles in results/lowlight-feature-principles-2026-07-05.md and
//           the measured levers of the 07-08..07-20 real-RAW campaigns.
//
// Relationship to the existing arms:
//   * default_isp.cpp  = the standard/reference arm (Vitis Vision ordering).
//   * lowlight_isp.cpp = THIS -- shares default_isp's correction backbone
//     (Bayer-domain black level + gain, CCM) so that the two arms differ ONLY
//     in the low-light specialisation: 2x2 binning, the 2.0x exposure gain
//     and the H/2 x W/2 output shape. Since 2026-08-06 both arms share the
//     SAME gamma 2.0 tone curve, so the tone axis is no longer a difference.
//     That is what makes the paper's "specialised beats general in its own
//     condition" comparison controlled.
//   * RM_LOW_LIGHT_TONE in dfxisp_accel.cpp (v1) is untouched and still the
//     deployed arm; promoting lowlight_ISP is a separate decision.
//
// Pipeline (derivations in lowlight_isp.md):
//   RAW Bayer 12-bit
//     -> (1) binning                [RAW]    same-colour 2x2 average: +6 dB on
//                                            R/B (4 samples), +9 dB on G (8).
//                                            BEFORE black level, so the pedestal
//                                            is subtracted once from the average
//                                            instead of rectifying each noisy
//                                            sample at zero (a positive bias).
//     -> (2) blackLevelCorrection   [binned] subtract pedestal + restore range
//     -> (3) gain                   [binned] exposure 2.0x x per-channel WB,
//                                            folded, upstream of quantisation
//     -> (4) colorcorrectionmatrix  [RGB12]  same matrix as default_isp
//     -> (5) gamma 2.0 tone         [12->8]  same curve as default_ISP. A
//                                            GAT/Anscombe VST sat here until
//                                            2026-08-06 and was measured to be
//                                            worse on both metrics with both
//                                            detectors; it survives only as an
//                                            ablation arm in the Python golden.
//                                            results/gat-tone-ablation-2026-08-06.md
//     -> packed RGB888 0x00RRGGBB, H/2 x W/2 (Policy A)
//
// All arithmetic is integer and bit-exact against
// tools/gen_lowlight_isp_golden.py.
// =============================================================================

// A 3x3 sigma-clipped denoise stage sat after the tone curve until 2026-08-06.
// It was removed, not switched off: across a 4x threshold sweep (k = 1.0..4.0,
// per-channel thresholds derived from the binned noise sigma) it never improved
// mAP@50 over having no denoise at all, and its mAP@[.5:.95] gains stayed inside
// the measurement noise band. Removing it also freed the 3-row line buffer that
// was the pipeline's only BRAM consumer.
// Evidence: results/denoise-k-sweep-2026-08-06.md, v2-arm-ablation-2026-08-06.md.

// Binning mode (stage 1). SUBSAMPLE reproduces the pre-2026-08-06 behaviour
// (one R and one B sample per cell = 0 dB, the cell's 2 G samples = +3 dB) and
// exists ONLY as the ablation baseline: with it, binning's SNR contribution can
// be measured directly instead of assumed. Measured gain of BINNING over
// SUBSAMPLE on synthetic Poisson-Gaussian frames: +5.6 to +7.1 dB.
enum LowlightIspBinning : int {
    LOWLIGHT_ISP_BIN_SUBSAMPLE = 0,
    LOWLIGHT_ISP_BIN_BINNING = 1,
};

// Development/analysis top: exposes the binning-mode switch.
//   raw_bayer : RAW Bayer RGGB, 12-bit values in uint16_t (W*H)
//   rgb_out   : packed RGB888 0x00RRGGBB; capacity >= W*H (uses W/2 * H/2)
// out_width/out_height report the binned shape (Policy A).
extern "C" void lowlight_isp(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int bin_mode,
    int* out_width,
    int* out_height);

// DFX Reconfigurable Module candidate. Port list is IDENTICAL (type, order,
// count) to rm_normal_tone_top / rm_low_light_tone_top / rm_default_isp_top,
// so all of them are valid implementations of the same RP slot (SPEC.md §7).
// Same-colour binning enabled.
extern "C" void rm_lowlight_isp_top(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int* out_width,
    int* out_height);
