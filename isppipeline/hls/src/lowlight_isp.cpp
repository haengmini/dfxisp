#include "lowlight_isp.hpp"

#include <cstdint>

// =============================================================================
// lowlight_ISP -- proposal low-light arm (v2). Shares default_isp's correction
// backbone; the low-light specialisation is binning + 2.0x exposure gain + the
// GAT/VST tone curve. Integer-only; bit-exact mirror
// of tools/gen_lowlight_isp_golden.py. Derivations: lowlight_isp.md.
// =============================================================================

namespace {

constexpr int RAW12_MAX = 4095;

// --- (2) blackLevelCorrection [binned domain] -------------------------------
constexpr int BLC_LEVEL12 = 2 << 4;   // 32; deployed real-RAW value (2026-07-20)
constexpr int BLC_MUL_Q8 = 258;       // round(256 * 4095 / (4095 - 32))

// --- (3) gain [binned domain, upstream of quantisation -- principle P3 4.3] --
// Gain cannot change SNR, but placing it before the >>4 keeps quantisation loss
// minimal; exposure and white balance are folded into ONE multiply per channel.
// Binning (1) already separated the channels, so this is a plain per-channel
// gain rather than the per-Bayer-site variant default_isp uses.
// WB stays a fixed constant: three independent campaigns measured WB to be a
// non-lever (mAP spread 0.0020 vs the BLC lever's 0.0876), so no adaptive AWB
// pass is spent here -- unlike default_isp, which keeps one for the general arm.
constexpr int EXPOSURE_GAIN_Q8 = 512;  // 2.0x
constexpr int WB_R_Q8 = 286, WB_G_Q8 = 256, WB_B_Q8 = 307;

// --- (4) colorcorrectionmatrix [RGB 12-bit] ----------------------------------
// Identical matrix to default_isp (rows sum to 256 -> neutral preserved) so the
// two arms share the backbone. Placeholder until sensor calibration.
constexpr int CCM_Q8[3][3] = {
    {288, -24, -8},
    {-24, 296, -16},
    {-16, -32, 304},
};

// --- (5) tone curve [12-bit -> 8-bit] ---------------------------------------
// gamma 2.0 as floor(sqrt(255*v)), byte-identical to the tables in
// default_isp.cpp and dfxisp_accel.cpp (each RM owns its own ROM in silicon).
//
// This slot held a GAT/Anscombe VST curve until 2026-08-06. The VST existed to
// make a CONSTANT-threshold denoise valid; once that denoise was measured to be
// worthless and deleted, the curve had to justify itself as a plain tone map --
// and it lost to this one. Night 100 frames, both detectors, both metrics:
//   gamma 2.0  0.1876 / 0.3797 (YOLOv8n)   0.1250 / 0.2427 (SSDLite MNv3)
//   GAT        0.1775 / 0.3710             0.1145 / 0.2314
// GAT's a/b were calibrated on that very split, so this is a loss at home. The
// curve is kept in tools/gen_lowlight_isp_golden.py as an ablation arm only.
// Evidence: results/gat-tone-ablation-2026-08-06.md
static const uint8_t GAMMA2_LUT[256] = {
      0, 15, 22, 27, 31, 35, 39, 42, 45, 47, 50, 52, 55, 57, 59, 61,
     63, 65, 67, 69, 71, 73, 74, 76, 78, 79, 81, 82, 84, 85, 87, 88,
     90, 91, 93, 94, 95, 97, 98, 99,100,102,103,104,105,107,108,109,
    110,111,112,114,115,116,117,118,119,120,121,122,123,124,125,126,
    127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,141,
    142,143,144,145,146,147,148,148,149,150,151,152,153,153,154,155,
    156,157,158,158,159,160,161,162,162,163,164,165,165,166,167,168,
    168,169,170,171,171,172,173,174,174,175,176,177,177,178,179,179,
    180,181,182,182,183,184,184,185,186,186,187,188,188,189,190,190,
    191,192,192,193,194,194,195,196,196,197,198,198,199,200,200,201,
    201,202,203,203,204,205,205,206,206,207,208,208,209,210,210,211,
    211,212,213,213,214,214,215,216,216,217,217,218,218,219,220,220,
    221,221,222,222,223,224,224,225,225,226,226,227,228,228,229,229,
    230,230,231,231,232,233,233,234,234,235,235,236,236,237,237,238,
    238,239,240,240,241,241,242,242,243,243,244,244,245,245,246,246,
    247,247,248,248,249,249,250,250,251,251,252,252,253,253,254,255,
};

static inline int clamp_i(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static inline uint32_t pack_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (uint32_t(r) << 16) | (uint32_t(g) << 8) | uint32_t(b);
}

static inline int bin_dim(int d) { return d / 2 < 1 ? 1 : d / 2; }

// The four Bayer sites of cell (cx, cy): R, G(top-right), G(bottom-left), B.
static inline void cell_sites(const uint16_t* raw, int width, int height,
                              int cx, int cy, int& r, int& g0, int& g1, int& b) {
#pragma HLS INLINE
    const int x0 = 2 * cx;
    const int x1 = (2 * cx + 1 < width) ? 2 * cx + 1 : width - 1;
    const int y0 = 2 * cy;
    const int y1 = (2 * cy + 1 < height) ? 2 * cy + 1 : height - 1;
    r = raw[y0 * width + x0];
    g0 = raw[y0 * width + x1];
    g1 = raw[y1 * width + x0];
    b = raw[y1 * width + x1];
}

// Stage (1): binning, in the RAW domain with NO correction applied yet.
//
// BINNING is real same-colour 2x2 binning: it averages the R sites of a 2x2
// neighbourhood of Bayer cells (4 samples -> sigma/2 -> +6 dB), the B sites
// likewise, and all 8 G sites (+9 dB). The windows overlap, so the output stays
// H/2 x W/2 and adjacent outputs are correlated -- the price of keeping the
// resolution. Measured on synthetic Poisson-Gaussian frames: +5.6 to +7.1 dB.
//
// SUBSAMPLE is the legacy path (one R and one B sample from the cell itself,
// 0 dB; the cell's 2 G samples, +3 dB). It is kept ONLY as the ablation
// baseline so binning's SNR contribution can be measured directly.
static inline void binned_raw(const uint16_t* raw, int width, int height,
                              int bw, int bh, int bx, int by, int bin_mode,
                              int& r12, int& g12, int& b12) {
#pragma HLS INLINE
    int r, g0, g1, b;
    if (bin_mode == LOWLIGHT_ISP_BIN_SUBSAMPLE) {
        cell_sites(raw, width, height, bx, by, r, g0, g1, b);
        r12 = r;
        g12 = (g0 + g1) / 2;
        b12 = b;
        return;
    }
    int sum_r = 0, sum_g = 0, sum_b = 0;
    for (int dy = 0; dy < 2; ++dy) {
        const int cy = clamp_i(by + dy, 0, bh - 1);
        for (int dx = 0; dx < 2; ++dx) {
            const int cx = clamp_i(bx + dx, 0, bw - 1);
            cell_sites(raw, width, height, cx, cy, r, g0, g1, b);
            sum_r += r;
            sum_g += g0 + g1;
            sum_b += b;
        }
    }
    r12 = sum_r / 4;
    g12 = sum_g / 8;
    b12 = sum_b / 4;
}

// Stages (2) black level and (3) gain, applied ONCE to the binned value.
// Subtracting the pedestal AFTER averaging is the unbiased order: clipping each
// noisy sample at zero first rectifies the noise and adds a positive bias --
// exactly the "noise floor lifted into visible grey" failure mode this arm is
// built to avoid (lowlight_isp.md §2.5).
static inline int correct_channel(int v, int wb_q8) {
#pragma HLS INLINE
    v = v > BLC_LEVEL12 ? v - BLC_LEVEL12 : 0;
    v = clamp_i((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX);
    const int gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8;
    return clamp_i((v * gain_q8) >> 8, 0, RAW12_MAX);
}

// Stages (1)-(3).
static inline void binned_rgb(const uint16_t* raw, int width, int height,
                              int bw, int bh, int bx, int by, int bin_mode,
                              int& r12, int& g12, int& b12) {
#pragma HLS INLINE
    binned_raw(raw, width, height, bw, bh, bx, by, bin_mode, r12, g12, b12);
    r12 = correct_channel(r12, WB_R_Q8);
    g12 = correct_channel(g12, WB_G_Q8);
    b12 = correct_channel(b12, WB_B_Q8);
}

// Stage (4). Negative CCM coefficients can drive the accumulator below zero; it
// is floored before the shift so C++ and the Python golden agree bit-for-bit
// without relying on arithmetic-shift-of-negative behaviour.
static inline int ccm_channel(int row, int r12, int g12, int b12) {
#pragma HLS INLINE
    int acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12;
    if (acc < 0) acc = 0;
    return clamp_i(acc >> 8, 0, RAW12_MAX);
}

// Stage (5): the CCM output is already clamped to [0, RAW12_MAX], so the >>4
// index is in range by construction.
static inline uint8_t tone(int v12) {
#pragma HLS INLINE
    return GAMMA2_LUT[v12 >> 4];
}

// Every stage is point-wise on the binned cell, so a binned pixel is produced
// and emitted in the same iteration -- no line buffer, no row latency. The
// three-row sliding window this loop used to carry existed only to feed the
// 3x3 denoise; removing that stage removed the storage with it.
static void run_lowlight_isp(const uint16_t* raw, uint32_t* rgb_out,
                             int width, int height, int bin_mode,
                             int& out_width, int& out_height) {
    const int bw = bin_dim(width);
    const int bh = bin_dim(height);
    out_width = bw;
    out_height = bh;

    for (int by = 0; by < bh; ++by) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=540
        for (int bx = 0; bx < bw; ++bx) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=2 max=960
            int r12 = 0, g12 = 0, b12 = 0;
            binned_rgb(raw, width, height, bw, bh, bx, by, bin_mode, r12, g12, b12);
            rgb_out[by * bw + bx] = pack_rgb(tone(ccm_channel(0, r12, g12, b12)),
                                             tone(ccm_channel(1, r12, g12, b12)),
                                             tone(ccm_channel(2, r12, g12, b12)));
        }
    }
}

}  // namespace

extern "C" void lowlight_isp(
    const uint16_t* raw_bayer, uint32_t* rgb_out, int width, int height,
    int bin_mode, int* out_width, int* out_height) {
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0 depth=2048
#pragma HLS INTERFACE m_axi port=rgb_out offset=slave bundle=gmem1 depth=2048
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=rgb_out bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=bin_mode bundle=control
#pragma HLS INTERFACE s_axilite port=out_width bundle=control
#pragma HLS INTERFACE s_axilite port=out_height bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    if (!raw_bayer || !rgb_out || width <= 0 || height <= 0) {
        if (out_width) *out_width = 0;
        if (out_height) *out_height = 0;
        return;
    }
    int ow = 0, oh = 0;
    run_lowlight_isp(raw_bayer, rgb_out, width, height, bin_mode, ow, oh);
    if (out_width) *out_width = ow;
    if (out_height) *out_height = oh;
}

// Port list matches the other RM tops exactly -- drop-in for the same RP slot.
extern "C" void rm_lowlight_isp_top(
    const uint16_t* raw_bayer, uint32_t* rgb_out, int width, int height,
    int* out_width, int* out_height) {
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0 depth=2048
#pragma HLS INTERFACE m_axi port=rgb_out offset=slave bundle=gmem1 depth=2048
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=rgb_out bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=out_width bundle=control
#pragma HLS INTERFACE s_axilite port=out_height bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    if (!raw_bayer || !rgb_out || width <= 0 || height <= 0) {
        if (out_width) *out_width = 0;
        if (out_height) *out_height = 0;
        return;
    }
    int ow = 0, oh = 0;
    run_lowlight_isp(raw_bayer, rgb_out, width, height,
                     LOWLIGHT_ISP_BIN_BINNING, ow, oh);
    if (out_width) *out_width = ow;
    if (out_height) *out_height = oh;
}
