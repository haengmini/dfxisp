#include "dfxisp_accel.hpp"

#include <cstdint>

namespace {

static inline uint16_t clamp_u16(int v, int lo, int hi) {
    return static_cast<uint16_t>(v < lo ? lo : (v > hi ? hi : v));
}

static inline uint8_t raw12_to_u8(uint16_t v) {
    return static_cast<uint8_t>((v > 4095u ? 4095u : v) >> 4);
}

static inline uint8_t clamp_u8(int v) {
    return static_cast<uint8_t>(v < 0 ? 0 : (v > 255 ? 255 : v));
}

static inline uint32_t pack_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (uint32_t(r) << 16) | (uint32_t(g) << 8) | uint32_t(b);
}

struct BayerWindow3x3 {
    uint16_t p[3][3];
};

static inline uint16_t sample_clamped(const uint16_t* raw, int width, int height, int x, int y) {
    x = x < 0 ? 0 : (x >= width ? width - 1 : x);
    y = y < 0 ? 0 : (y >= height ? height - 1 : y);
    return raw[y * width + x];
}

// Scene checker: static-region logic that decides whether the frame should be
// routed to the low-light reconfigurable module in AUTO mode.
static uint16_t checker_scene_average(const uint16_t* raw, int width, int height) {
    uint64_t acc = 0;
    const int n = width * height;
    for (int i = 0; i < n; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=16 max=2073600
        acc += raw[i];
    }
    return n > 0 ? static_cast<uint16_t>(acc / static_cast<uint64_t>(n)) : 0;
}

static bool checker_select_low_light(const uint16_t* raw, int width, int height, int mode,
                                     uint16_t low_light_threshold) {
    const uint16_t avg = checker_scene_average(raw, width, height);
    return (mode == DFXISP_MODE_LOW_LIGHT) ||
           (mode == DFXISP_MODE_AUTO && avg < low_light_threshold);
}

// Window load is intentionally isolated from the pixel operator.  The current
// C-sim implementation uses clamped memory reads; the same function boundary can
// be replaced by a true streaming line buffer that produces this 3x3 window.
static void load_bayer_window3x3(const uint16_t* raw, int width, int height, int x, int y,
                                 BayerWindow3x3& win) {
#pragma HLS INLINE
    for (int wy = 0; wy < 3; ++wy) {
#pragma HLS UNROLL
        for (int wx = 0; wx < 3; ++wx) {
#pragma HLS UNROLL
            win.p[wy][wx] = sample_clamped(raw, width, height, x + wx - 1, y + wy - 1);
        }
    }
}

static void demosaic_grbg_window(const BayerWindow3x3& win, int x, int y,
                                 uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    const bool even_y = (y & 1) == 0;
    const bool even_x = (x & 1) == 0;
    const uint16_t c = win.p[1][1];
    uint16_t rr = 0, gg = 0, bb = 0;

    if (even_y && even_x) {          // G on R row
        gg = c;
        rr = (win.p[1][0] + win.p[1][2]) / 2;
        bb = (win.p[0][1] + win.p[2][1]) / 2;
    } else if (even_y && !even_x) {  // R
        rr = c;
        gg = (win.p[1][0] + win.p[1][2] + win.p[0][1] + win.p[2][1]) / 4;
        bb = (win.p[0][0] + win.p[0][2] + win.p[2][0] + win.p[2][2]) / 4;
    } else if (!even_y && even_x) {  // B
        bb = c;
        gg = (win.p[1][0] + win.p[1][2] + win.p[0][1] + win.p[2][1]) / 4;
        rr = (win.p[0][0] + win.p[0][2] + win.p[2][0] + win.p[2][2]) / 4;
    } else {                         // G on B row
        gg = c;
        rr = (win.p[0][1] + win.p[2][1]) / 2;
        bb = (win.p[1][0] + win.p[1][2]) / 2;
    }

    r = raw12_to_u8(rr);
    g = raw12_to_u8(gg);
    b = raw12_to_u8(bb);
}

static void normal_pixel_kernel(const uint16_t* raw, int width, int height, int x, int y,
                                uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    BayerWindow3x3 win = {};
    load_bayer_window3x3(raw, width, height, x, y, win);
    demosaic_grbg_window(win, x, y, r, g, b);
}

// DFX reconfigurable module boundary candidate.
// In the Vivado DFX floorplan this function should be synthesized/packaged as
// the low-light RM (or replaced by another compatible RM) while dfxisp_accel,
// checker_select_low_light, and normal_pipeline remain in the static region.
static void low_light_reconfigurable_module(uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE off
    // Low-cost approximation of low-light ISP: gain + mild gamma lift.
    // Integer-only to keep C-sim/HLS behavior deterministic.
    r = clamp_u8((int(r) * 3) / 2 + 8);
    g = clamp_u8((int(g) * 3) / 2 + 8);
    b = clamp_u8((int(b) * 3) / 2 + 8);
}

static void normal_pipeline(const uint16_t* raw, uint32_t* rgb_out, int width, int height) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            normal_pixel_kernel(raw, width, height, x, y, r, g, b);
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

static void low_light_pipeline(const uint16_t* raw, uint32_t* rgb_out, int width, int height) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            normal_pixel_kernel(raw, width, height, x, y, r, g, b);
            low_light_reconfigurable_module(r, g, b);
            rgb_out[y * width + x] = pack_rgb(r, g, b);
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
    uint16_t low_light_threshold) {
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=rgb_out offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=rgb_out bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=mode bundle=control
#pragma HLS INTERFACE s_axilite port=low_light_threshold bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    if (!raw_bayer || !rgb_out || width <= 0 || height <= 0) {
        return;
    }

    const bool low_light = checker_select_low_light(raw_bayer, width, height, mode, low_light_threshold);
    if (low_light) {
        low_light_pipeline(raw_bayer, rgb_out, width, height);
    } else {
        normal_pipeline(raw_bayer, rgb_out, width, height);
    }
}
