#include "dfxisp_accel.hpp"

#include <cstdint>

// DFXISP core C-sim: shared baseline ISP core + mutually exclusive tone RM slot.
// Integer-only; bit-exact mirror of tools/gen_golden_vectors.py.
//
// Ordering (confirmed 2026-07-01): the tone RM slot wraps the shared baseline
// core. Low-light 2x2 binning runs on RAW (before precision loss, RESEARCH.md
// §4.2); low-light gain + gamma run as an 8-bit tone stage after the core.
// gain/gamma never appear inside the baseline core (no duplication).

namespace {

// --- shared baseline-core parameters (mode independent) ---
constexpr int BLC_OFFSET = 16;      // black-level correction
constexpr int AWB_R = 286;          // Q8 per-channel color calibration
constexpr int AWB_G = 256;
constexpr int AWB_B = 307;
// --- low-light tone RM parameters ---
constexpr int LL_GAIN_NUM = 5;      // low-light exposure gain 1.25x
constexpr int LL_GAIN_DEN = 4;
// gamma 4.0 realized exactly as the integer 4th root: 255*(v/255)^(1/4)
//   = (255^3 * v)^(1/4),  255^3 = 16581375
constexpr uint64_t GAMMA4_SCALE = 16581375ull;
// --- checker ---
constexpr int DARK_RATIO_PCT = 40;  // AUTO -> LOW_LIGHT when dark pixels > 40%

static inline uint8_t clamp_u8(int v) {
    return static_cast<uint8_t>(v < 0 ? 0 : (v > 255 ? 255 : v));
}

static inline uint8_t raw12_to_u8(uint16_t v) {
    return static_cast<uint8_t>((v > 4095u ? 4095u : v) >> 4);
}

static inline uint32_t pack_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (uint32_t(r) << 16) | (uint32_t(g) << 8) | uint32_t(b);
}

// Exact integer floor sqrt (matches Python math.isqrt).
static uint64_t isqrt_u64(uint64_t n) {
    if (n == 0) return 0;
    uint64_t x = n, y = (x + 1) / 2;
    while (y < x) { x = y; y = (x + n / x) / 2; }
    return x;  // floor(sqrt(n))
}

// gamma 4.0 low-light tone: out = floor((255^3 * v)^(1/4)), exact & bit-exact.
static inline uint8_t gamma4(uint8_t v) {
    const uint64_t n = GAMMA4_SCALE * static_cast<uint64_t>(v);
    return clamp_u8(static_cast<int>(isqrt_u64(isqrt_u64(n))));
}

static inline uint16_t sample_clamped(const uint16_t* raw, int width, int height, int x, int y) {
    x = x < 0 ? 0 : (x >= width ? width - 1 : x);
    y = y < 0 ? 0 : (y >= height ? height - 1 : y);
    return raw[y * width + x];
}

// ---------------------------------------------------------------------------
// Scene checker / mode decision (static region). Uses dark-pixel ratio on RAW.
// Per-frame decision; scene-level hysteresis is handled by the sequence
// scheduler (RESEARCH.md §5.2), not by this single-frame C-sim entry point.
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
    // dark_ratio > 40%  <=>  dark*100 > 40*n
    return (dark * 100 > DARK_RATIO_PCT * n) ? DFXISP_MODE_LOW_LIGHT : DFXISP_MODE_NORMAL;
}

// ---------------------------------------------------------------------------
// Shared baseline ISP core: demosaic + BLC + AWB + CCM. No gain/gamma.
// ---------------------------------------------------------------------------
static void demosaic_grbg(const uint16_t* raw, int width, int height, int x, int y,
                          uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    uint16_t win[3][3];
    for (int wy = 0; wy < 3; ++wy)
        for (int wx = 0; wx < 3; ++wx)
            win[wy][wx] = sample_clamped(raw, width, height, x + wx - 1, y + wy - 1);

    const bool even_y = (y & 1) == 0;
    const bool even_x = (x & 1) == 0;
    const uint16_t c = win[1][1];
    uint16_t rr = 0, gg = 0, bb = 0;

    if (even_y && even_x) {          // G on R row
        gg = c;
        rr = (win[1][0] + win[1][2]) / 2;
        bb = (win[0][1] + win[2][1]) / 2;
    } else if (even_y && !even_x) {  // R
        rr = c;
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) / 4;
        bb = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) / 4;
    } else if (!even_y && even_x) {  // B
        bb = c;
        gg = (win[1][0] + win[1][2] + win[0][1] + win[2][1]) / 4;
        rr = (win[0][0] + win[0][2] + win[2][0] + win[2][2]) / 4;
    } else {                         // G on B row
        gg = c;
        rr = (win[0][1] + win[2][1]) / 2;
        bb = (win[1][0] + win[1][2]) / 2;
    }
    r = raw12_to_u8(rr);
    g = raw12_to_u8(gg);
    b = raw12_to_u8(bb);
}

static void baseline_isp_core_pixel(const uint16_t* raw, int width, int height, int x, int y,
                                    uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    uint8_t dr, dg, db;
    demosaic_grbg(raw, width, height, x, y, dr, dg, db);
    // BLC
    int br = dr - BLC_OFFSET, bg = dg - BLC_OFFSET, bb = db - BLC_OFFSET;
    // AWB (Q8 per-channel color calibration)
    br = (clamp_u8(br) * AWB_R) / 256;
    bg = (clamp_u8(bg) * AWB_G) / 256;
    bb = (clamp_u8(bb) * AWB_B) / 256;
    // CCM (identity placeholder in the shared core; still no gain/gamma here)
    r = clamp_u8(br);
    g = clamp_u8(bg);
    b = clamp_u8(bb);
}

// ---------------------------------------------------------------------------
// RM_NORMAL_TONE = identity bypass. Baseline core over the full-res frame.
// ---------------------------------------------------------------------------
static void run_normal(const uint16_t* raw, uint32_t* rgb_out, int width, int height) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            baseline_isp_core_pixel(raw, width, height, x, y, r, g, b);  // no gain/gamma
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

// ---------------------------------------------------------------------------
// RM_LOW_LIGHT_TONE (Policy A, shape-changing H/2 x W/2):
//   front: 2x2 RAW binning  ->  baseline core  ->  back: gain + gamma-4.0 tone
// ---------------------------------------------------------------------------
static inline int bin_dim(int d) { return d / 2 < 1 ? 1 : d / 2; }

static void run_low_light(const uint16_t* raw, uint32_t* rgb_out, int width, int height,
                          int& out_width, int& out_height) {
    const int bw = bin_dim(width);
    const int bh = bin_dim(height);
    out_width = bw;
    out_height = bh;

    // front: 2x2 RAW binning (candidate formula (p00+p01+p10+p11)/4), RESEARCH §4.1
    // Small scratch sized to the C-sim fixtures; HW uses a streaming line buffer.
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

    // baseline core over the binned RAW, then low-light tone (gain + gamma).
    for (int y = 0; y < bh; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=2 max=540
        for (int x = 0; x < bw; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=2 max=960
            uint8_t r = 0, g = 0, b = 0;
            baseline_isp_core_pixel(binned, bw, bh, x, y, r, g, b);
            // back: low-light gain then gamma-4.0 (the only gain/gamma in the pipeline)
            r = gamma4(clamp_u8((int(r) * LL_GAIN_NUM) / LL_GAIN_DEN));
            g = gamma4(clamp_u8((int(g) * LL_GAIN_NUM) / LL_GAIN_DEN));
            b = gamma4(clamp_u8((int(b) * LL_GAIN_NUM) / LL_GAIN_DEN));
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
        run_low_light(raw_bayer, rgb_out, width, height, out_w, out_h);  // 2x2 bin + gain + gamma
        sel_rm = DFXISP_RM_LOW_LIGHT_TONE;
    } else {
        run_normal(raw_bayer, rgb_out, width, height);                    // identity tone
        sel_rm = DFXISP_RM_NORMAL_TONE;
    }

    if (result) {
        result->out_width = out_w;
        result->out_height = out_h;
        result->selected_mode = selected;
        result->selected_rm = sel_rm;
    }
}
