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

static inline uint16_t sample_clamped(const uint16_t* raw, int width, int height, int x, int y) {
    x = x < 0 ? 0 : (x >= width ? width - 1 : x);
    y = y < 0 ? 0 : (y >= height ? height - 1 : y);
    return raw[y * width + x];
}

static uint16_t scene_average(const uint16_t* raw, int width, int height) {
    uint64_t acc = 0;
    const int n = width * height;
    for (int i = 0; i < n; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=16 max=2073600
        acc += raw[i];
    }
    return n > 0 ? static_cast<uint16_t>(acc / static_cast<uint64_t>(n)) : 0;
}

static void demosaic_grbg_at(const uint16_t* raw, int width, int height, int x, int y,
                            uint8_t& r, uint8_t& g, uint8_t& b) {
    const bool even_y = (y & 1) == 0;
    const bool even_x = (x & 1) == 0;
    const uint16_t c = sample_clamped(raw, width, height, x, y);
    uint16_t rr = 0, gg = 0, bb = 0;

    if (even_y && even_x) {          // G on R row
        gg = c;
        rr = (sample_clamped(raw, width, height, x - 1, y) + sample_clamped(raw, width, height, x + 1, y)) / 2;
        bb = (sample_clamped(raw, width, height, x, y - 1) + sample_clamped(raw, width, height, x, y + 1)) / 2;
    } else if (even_y && !even_x) {  // R
        rr = c;
        gg = (sample_clamped(raw, width, height, x - 1, y) + sample_clamped(raw, width, height, x + 1, y) +
              sample_clamped(raw, width, height, x, y - 1) + sample_clamped(raw, width, height, x, y + 1)) / 4;
        bb = (sample_clamped(raw, width, height, x - 1, y - 1) + sample_clamped(raw, width, height, x + 1, y - 1) +
              sample_clamped(raw, width, height, x - 1, y + 1) + sample_clamped(raw, width, height, x + 1, y + 1)) / 4;
    } else if (!even_y && even_x) {  // B
        bb = c;
        gg = (sample_clamped(raw, width, height, x - 1, y) + sample_clamped(raw, width, height, x + 1, y) +
              sample_clamped(raw, width, height, x, y - 1) + sample_clamped(raw, width, height, x, y + 1)) / 4;
        rr = (sample_clamped(raw, width, height, x - 1, y - 1) + sample_clamped(raw, width, height, x + 1, y - 1) +
              sample_clamped(raw, width, height, x - 1, y + 1) + sample_clamped(raw, width, height, x + 1, y + 1)) / 4;
    } else {                         // G on B row
        gg = c;
        rr = (sample_clamped(raw, width, height, x, y - 1) + sample_clamped(raw, width, height, x, y + 1)) / 2;
        bb = (sample_clamped(raw, width, height, x - 1, y) + sample_clamped(raw, width, height, x + 1, y)) / 2;
    }

    r = raw12_to_u8(rr);
    g = raw12_to_u8(gg);
    b = raw12_to_u8(bb);
}

static inline void apply_low_light(uint8_t& r, uint8_t& g, uint8_t& b) {
    // Low-cost approximation of low-light ISP: gain + mild gamma lift.
    // Integer-only to keep C-sim/HLS behavior deterministic.
    r = clamp_u8((int(r) * 3) / 2 + 8);
    g = clamp_u8((int(g) * 3) / 2 + 8);
    b = clamp_u8((int(b) * 3) / 2 + 8);
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

    const uint16_t avg = scene_average(raw_bayer, width, height);
    const bool low_light = (mode == DFXISP_MODE_LOW_LIGHT) ||
                           (mode == DFXISP_MODE_AUTO && avg < low_light_threshold);

    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            demosaic_grbg_at(raw_bayer, width, height, x, y, r, g, b);
            if (low_light) {
                apply_low_light(r, g, b);
            }
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}
