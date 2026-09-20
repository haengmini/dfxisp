#include "LowlightISP.hpp"

#include <cstdint>

// 설계 근거·파이프라인 유도·상수 출처: docs/LowlightISP.md

namespace {

constexpr int RAW12_MAX = 4095;

constexpr int BLC_LEVEL12 = 2 << 4;
constexpr int BLC_MUL_Q8 = 258;

constexpr int EXPOSURE_GAIN_Q8 = 512;
constexpr int WB_R_Q8 = 286, WB_G_Q8 = 256, WB_B_Q8 = 307;

constexpr int CCM_Q8[3][3] = {
    {288, -24, -8},
    {-24, 296, -16},
    {-16, -32, 304},
};

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

static inline int correct_channel(int v, int wb_q8) {
#pragma HLS INLINE
    v = v > BLC_LEVEL12 ? v - BLC_LEVEL12 : 0;
    v = clamp_i((v * BLC_MUL_Q8) >> 8, 0, RAW12_MAX);
    const int gain_q8 = (EXPOSURE_GAIN_Q8 * wb_q8) >> 8;
    return clamp_i((v * gain_q8) >> 8, 0, RAW12_MAX);
}

static inline void binned_rgb(const uint16_t* raw, int width, int height,
                              int bw, int bh, int bx, int by, int bin_mode,
                              int& r12, int& g12, int& b12) {
#pragma HLS INLINE
    binned_raw(raw, width, height, bw, bh, bx, by, bin_mode, r12, g12, b12);
    r12 = correct_channel(r12, WB_R_Q8);
    g12 = correct_channel(g12, WB_G_Q8);
    b12 = correct_channel(b12, WB_B_Q8);
}

static inline int ccm_channel(int row, int r12, int g12, int b12) {
#pragma HLS INLINE
    int acc = CCM_Q8[row][0] * r12 + CCM_Q8[row][1] * g12 + CCM_Q8[row][2] * b12;
    if (acc < 0) acc = 0;
    return clamp_i(acc >> 8, 0, RAW12_MAX);
}

static inline uint8_t apply_gamma(int v12) {
#pragma HLS INLINE
    return GAMMA2_LUT[v12 >> 4];
}

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
            rgb_out[by * bw + bx] = pack_rgb(apply_gamma(ccm_channel(0, r12, g12, b12)),
                                             apply_gamma(ccm_channel(1, r12, g12, b12)),
                                             apply_gamma(ccm_channel(2, r12, g12, b12)));
        }
    }
}

}  // namespace

extern "C" void LowlightISP_dev(
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

extern "C" void LowlightISP(
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
