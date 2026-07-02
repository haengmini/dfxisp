#include "dfxisp_accel.hpp"

#include <cstdint>

// =============================================================================
// File   : isppipeline/hls/src/dfxisp_accel.cpp
// Updated: 2026-07-02 12:40 KST
// Function: DFXISP core C-sim — shared baseline ISP core + mutually exclusive
//           tone RM slot. Integer-only; bit-exact mirror of gen_golden_vectors.py.
// Goal   : Reflect the ver1 RAW-domain-first ordering into HW/C-sim:
//             baseline core = demosaic -> BLC -> WB -> CCM   (12-bit, no gain/gamma)
//             RM_NORMAL_TONE     = gain(1.25x) + gamma        (was identity)
//             RM_LOW_LIGHT_TONE  = 2x2 bin(front) + gain(2.0x) + gamma(back)
//           Corrections stay in 12-bit before the final >>4 (precision preserved);
//           gamma via integer sqrt (gamma 2.0) so it is bit-exact & HLS-friendly.
//           Bayer pattern RGGB (unified with the SW dataset).
// =============================================================================
//
// Ordering: tone RM slot wraps the shared baseline core. Low-light 2x2 binning
// runs on RAW (before precision loss); gain/gamma are the tone stages and never
// appear inside the baseline core (no duplication, RESEARCH.md de-dup rule).

namespace {

// --- shared baseline-core parameters (mode independent, 12-bit RAW domain) ---
constexpr int BLC_OFFSET12 = 16 << 4;   // black level 16 (8-bit) -> 256 (12-bit)
constexpr int RAW12_MAX = 4095;
constexpr int AWB_R = 286;              // Q8 per-channel white balance (color)
constexpr int AWB_G = 256;
constexpr int AWB_B = 307;
// --- tone RM parameters (exposure gain per mode + gamma) ---
constexpr int GAIN_NORMAL_NUM = 5, GAIN_NORMAL_DEN = 4;      // normal 1.25x
constexpr int GAIN_LOWLIGHT_NUM = 2, GAIN_LOWLIGHT_DEN = 1;  // low-light 2.0x
// gamma 2.0 realized exactly as integer sqrt: 255*(v/255)^(1/2) = floor(sqrt(255*v))
// --- checker ---
// Recalibrated 2026-07-02 from measured dataset separation (Youden's J sweep,
// data/{coco_val,exdark_val}): old 40% gave ExDark recall=1.00 but COCO
// false-trigger=0.80 (checker almost never says NORMAL). 80% gives recall=0.90,
// false-trigger=0.11 (near-optimal J=0.79, close to the J-max at 83%).
constexpr int DARK_RATIO_PCT = 80;      // AUTO -> LOW_LIGHT when dark pixels > 80%

static inline int clamp_i(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
static inline uint8_t clamp_u8(int v) { return static_cast<uint8_t>(clamp_i(v, 0, 255)); }

static inline uint32_t pack_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (uint32_t(r) << 16) | (uint32_t(g) << 8) | uint32_t(b);
}

// Exact integer floor sqrt (matches Python math.isqrt).
static uint64_t isqrt_u64(uint64_t n) {
    if (n == 0) return 0;
    uint64_t x = n, y = (x + 1) / 2;
    while (y < x) { x = y; y = (x + n / x) / 2; }
    return x;
}

// gamma 2.0 tone: out = floor(sqrt(255 * v)), v,out in [0,255]. Exact & bit-exact.
static inline uint8_t gamma2(uint8_t v) {
    return clamp_u8(static_cast<int>(isqrt_u64(255ull * static_cast<uint64_t>(v))));
}

static inline uint16_t sample_clamped(const uint16_t* raw, int width, int height, int x, int y) {
    x = x < 0 ? 0 : (x >= width ? width - 1 : x);
    y = y < 0 ? 0 : (y >= height ? height - 1 : y);
    return raw[y * width + x];
}

// ---------------------------------------------------------------------------
// Scene checker / mode decision (static region). Dark-pixel ratio on RAW.
// ---------------------------------------------------------------------------
static int checker_select_mode(const uint16_t* raw, int width, int height, int mode,
                               uint16_t dark_pixel_threshold) {
    if (mode == DFXISP_MODE_NORMAL) return DFXISP_MODE_NORMAL;
    if (mode == DFXISP_MODE_LOW_LIGHT) return DFXISP_MODE_LOW_LIGHT;
    const int n = width * height;
    int dark = 0;
    for (int i = 0; i < n; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=16 max=2073600
        if (raw[i] < dark_pixel_threshold) ++dark;
    }
    return (dark * 100 > DARK_RATIO_PCT * n) ? DFXISP_MODE_LOW_LIGHT : DFXISP_MODE_NORMAL;
}

// ---------------------------------------------------------------------------
// RGGB demosaic keeping 12-bit precision (no >>4 here). Pattern:
//   (0,0)=R (0,1)=G (1,0)=G (1,1)=B
// ---------------------------------------------------------------------------
static void demosaic_rggb12(const uint16_t* raw, int width, int height, int x, int y,
                            int& r12, int& g12, int& b12) {
#pragma HLS INLINE
    uint16_t win[3][3];
    for (int wy = 0; wy < 3; ++wy)
        for (int wx = 0; wx < 3; ++wx)
            win[wy][wx] = sample_clamped(raw, width, height, x + wx - 1, y + wy - 1);

    const bool even_y = (y & 1) == 0;
    const bool even_x = (x & 1) == 0;
    const uint16_t c = win[1][1];
    int rr = 0, gg = 0, bb = 0;

    if (even_y && even_x) {          // R
        rr = c;
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) / 4;
        bb = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) / 4;
    } else if (even_y && !even_x) {  // G on R row (R horizontal, B vertical)
        gg = c;
        rr = (win[1][0] + win[1][2]) / 2;
        bb = (win[0][1] + win[2][1]) / 2;
    } else if (!even_y && even_x) {  // G on B row (R vertical, B horizontal)
        gg = c;
        rr = (win[0][1] + win[2][1]) / 2;
        bb = (win[1][0] + win[1][2]) / 2;
    } else {                         // B
        bb = c;
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) / 4;
        rr = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) / 4;
    }
    r12 = rr > RAW12_MAX ? RAW12_MAX : rr;
    g12 = gg > RAW12_MAX ? RAW12_MAX : gg;
    b12 = bb > RAW12_MAX ? RAW12_MAX : bb;
}

// ---------------------------------------------------------------------------
// Shared baseline ISP core (ver1): demosaic + BLC + WB + CCM, all in 12-bit.
// No gain/gamma. Returns 12-bit R,G,B (tone stage does >>4 + gamma).
// ---------------------------------------------------------------------------
static void baseline_core12(const uint16_t* raw, int width, int height, int x, int y,
                            int& r12, int& g12, int& b12) {
#pragma HLS INLINE
    int dr, dg, db;
    demosaic_rggb12(raw, width, height, x, y, dr, dg, db);         // demosaic (12-bit)
    dr = clamp_i(dr - BLC_OFFSET12, 0, RAW12_MAX);                 // BLC (subtract first)
    dg = clamp_i(dg - BLC_OFFSET12, 0, RAW12_MAX);
    db = clamp_i(db - BLC_OFFSET12, 0, RAW12_MAX);
    r12 = clamp_i(dr * AWB_R / 256, 0, RAW12_MAX);                 // WB per channel (Q8)
    g12 = clamp_i(dg * AWB_G / 256, 0, RAW12_MAX);
    b12 = clamp_i(db * AWB_B / 256, 0, RAW12_MAX);                 // CCM identity (no gain/gamma)
}

// tone RM: exposure gain (12-bit) -> >>4 to 8-bit -> gamma 2.0. Mode-specific gain.
static inline uint8_t tone(int v12, int gnum, int gden) {
#pragma HLS INLINE
    const int gained = clamp_i(v12 * gnum / gden, 0, RAW12_MAX);
    return gamma2(clamp_u8(gained >> 4));
}

// ---------------------------------------------------------------------------
// RM_NORMAL_TONE (NORMAL): gain 1.25x + gamma over the full-res baseline core.
// ---------------------------------------------------------------------------
static void run_normal(const uint16_t* raw, uint32_t* rgb_out, int width, int height) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            int r12, g12, b12;
            baseline_core12(raw, width, height, x, y, r12, g12, b12);     // no gain/gamma
            const uint8_t r = tone(r12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN);
            const uint8_t g = tone(g12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN);
            const uint8_t b = tone(b12, GAIN_NORMAL_NUM, GAIN_NORMAL_DEN);
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

// ---------------------------------------------------------------------------
// RM_LOW_LIGHT_TONE (Policy A, H/2 x W/2):
//   front: 2x2 RAW binning -> baseline core -> back: gain 2.0x + gamma
// ---------------------------------------------------------------------------
static inline int bin_dim(int d) { return d / 2 < 1 ? 1 : d / 2; }

static void run_low_light(const uint16_t* raw, uint32_t* rgb_out, int width, int height,
                          int& out_width, int& out_height) {
    const int bw = bin_dim(width);
    const int bh = bin_dim(height);
    out_width = bw;
    out_height = bh;

    // front: 2x2 RAW binning (sum/4), RESEARCH §4.2 — before precision loss.
    static uint16_t binned[1920 * 1080];
    for (int by = 0; by < bh; ++by) {
#pragma HLS LOOP_TRIPCOUNT min=2 max=540
        for (int bx = 0; bx < bw; ++bx) {
#pragma HLS LOOP_TRIPCOUNT min=2 max=960
            const int x0 = 2 * bx, x1 = (2 * bx + 1 < width) ? 2 * bx + 1 : width - 1;
            const int y0 = 2 * by, y1 = (2 * by + 1 < height) ? 2 * by + 1 : height - 1;
            const int s = raw[y0 * width + x0] + raw[y0 * width + x1] +
                          raw[y1 * width + x0] + raw[y1 * width + x1];
            binned[by * bw + bx] = static_cast<uint16_t>(s / 4);
        }
    }

    for (int y = 0; y < bh; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=2 max=540
        for (int x = 0; x < bw; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=2 max=960
            int r12, g12, b12;
            baseline_core12(binned, bw, bh, x, y, r12, g12, b12);              // shared core
            const uint8_t r = tone(r12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN);  // gain 2.0x + gamma
            const uint8_t g = tone(g12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN);
            const uint8_t b = tone(b12, GAIN_LOWLIGHT_NUM, GAIN_LOWLIGHT_DEN);
            rgb_out[y * bw + x] = pack_rgb(r, g, b);
        }
    }
}

}  // namespace

extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t dark_pixel_threshold,
    DfxIspResult* result) {
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=rgb_out offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=rgb_out bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=mode bundle=control
#pragma HLS INTERFACE s_axilite port=dark_pixel_threshold bundle=control
#pragma HLS INTERFACE s_axilite port=result bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    if (!raw_bayer || !rgb_out || width <= 0 || height <= 0) {
        if (result) { result->out_width = 0; result->out_height = 0;
                      result->selected_mode = DFXISP_MODE_NORMAL;
                      result->selected_rm = DFXISP_RM_NORMAL_TONE; }
        return;
    }

    const int selected = checker_select_mode(raw_bayer, width, height, mode, dark_pixel_threshold);

    int out_w = width, out_h = height, sel_rm = DFXISP_RM_NORMAL_TONE;
    if (selected == DFXISP_MODE_LOW_LIGHT) {
        run_low_light(raw_bayer, rgb_out, width, height, out_w, out_h);
        sel_rm = DFXISP_RM_LOW_LIGHT_TONE;
    } else {
        run_normal(raw_bayer, rgb_out, width, height);
        sel_rm = DFXISP_RM_NORMAL_TONE;
    }

    if (result) {
        result->out_width = out_w;
        result->out_height = out_h;
        result->selected_mode = selected;
        result->selected_rm = sel_rm;
    }
}
