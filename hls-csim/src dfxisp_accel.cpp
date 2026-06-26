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

// Scene checker: static-region logic
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

// 2x2 Bayer Binning implementation
static uint16_t bayer_binning_2x2(const uint16_t* raw, int width, int height, int x, int y) {
#pragma HLS INLINE
    // 4x4 block boundary for GRBG layout binning
    int bx = (x / 4) * 4;
    int by = (y / 4) * 4;
    int rx = x % 4;
    int ry = y % 4;
    
    int channel_y = ry % 2;
    int channel_x = rx % 2;
    
    uint32_t sum = 0;
    for (int dy = 0; dy < 4; dy += 2) {
        for (int dx = 0; dx < 4; dx += 2) {
            sum += sample_clamped(raw, width, height, bx + dx + channel_x, by + dy + channel_y);
        }
    }
    return static_cast<uint16_t>(sum / 4);
}

static void load_bayer_window3x3(const uint16_t* raw, int width, int height, int x, int y,
                                 bool use_binning, BayerWindow3x3& win) {
#pragma HLS INLINE
    for (int wy = 0; wy < 3; ++wy) {
#pragma HLS UNROLL
        for (int wx = 0; wx < 3; ++wx) {
#pragma HLS UNROLL
            int px = x + wx - 1;
            int py = y + wy - 1;
            if (use_binning) {
                win.p[wy][wx] = bayer_binning_2x2(raw, width, height, px, py);
            } else {
                win.p[wy][wx] = sample_clamped(raw, width, height, px, py);
            }
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

// Helper to perform Demosaic (optionally with Bayer Binning)
static void demosaic_pixel_core(const uint16_t* raw, int width, int height, int x, int y,
                                bool use_binning, uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    BayerWindow3x3 win = {};
    load_bayer_window3x3(raw, width, height, x, y, use_binning, win);
    demosaic_grbg_window(win, x, y, r, g, b);
}

// 3x3 Mean Filter Denoise - low-light RM candidate component
static void denoise_mean_3x3(const uint16_t* raw, int width, int height, int x, int y,
                             bool use_binning, uint8_t& r_out, uint8_t& g_out, uint8_t& b_out) {
#pragma HLS INLINE
    uint32_t sum_r = 0, sum_g = 0, sum_b = 0;
    for (int dy = -1; dy <= 1; ++dy) {
        for (int dx = -1; dx <= 1; ++dx) {
            uint8_t r = 0, g = 0, b = 0;
            demosaic_pixel_core(raw, width, height, x + dx, y + dy, use_binning, r, g, b);
            sum_r += r;
            sum_g += g;
            sum_b += b;
        }
    }
    r_out = static_cast<uint8_t>(sum_r / 9);
    g_out = static_cast<uint8_t>(sum_g / 9);
    b_out = static_cast<uint8_t>(sum_b / 9);
}

// Reconfigurable Module low-light pipeline
// Under DFX flow, the entire front-end (Binning + Denoise) is swapped.
static void low_light_reconfigurable_module(const uint16_t* raw, int width, int height, int x, int y,
                                            uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE off
    // Binning & Denoise combined into single RM block
    denoise_mean_3x3(raw, width, height, x, y, true, r, g, b);
}

// Dynamic register gain application (applied to both DFX low-light and Register-only low-light)
static inline void apply_low_light_gain(uint8_t& r, uint8_t& g, uint8_t& b) {
#pragma HLS INLINE
    r = clamp_u8((int(r) * 3) / 2 + 8);
    g = clamp_u8((int(g) * 3) / 2 + 8);
    b = clamp_u8((int(b) * 3) / 2 + 8);
}

// -------------------------------------------------------------
// Pipelines for the 3 Arms
// -------------------------------------------------------------

// Arm 0: Baseline (Fixed Normal ISP)
static void pipeline_baseline(const uint16_t* raw, uint32_t* rgb_out, int width, int height) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            demosaic_pixel_core(raw, width, height, x, y, false, r, g, b);
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

// Arm 1: Register-only Adaptive (Mux-based control)
static void pipeline_register_only(const uint16_t* raw, uint32_t* rgb_out, int width, int height, bool low_light) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            if (low_light) {
                // Low-light path enabled by register: 2x2 binning + Denoise
                denoise_mean_3x3(raw, width, height, x, y, true, r, g, b);
                apply_low_light_gain(r, g, b);
            } else {
                // Normal path
                demosaic_pixel_core(raw, width, height, x, y, false, r, g, b);
            }
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

// Arm 2: DFX Adaptive (Swappable Module Simulation)
static void pipeline_dfx(const uint16_t* raw, uint32_t* rgb_out, int width, int height, bool low_light) {
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=4 max=1080
        for (int x = 0; x < width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=1920
            uint8_t r = 0, g = 0, b = 0;
            if (low_light) {
                // Swapped Low-light RM active
                low_light_reconfigurable_module(raw, width, height, x, y, r, g, b);
                apply_low_light_gain(r, g, b);
            } else {
                // Swapped Normal RM active (Standard demosaic)
                demosaic_pixel_core(raw, width, height, x, y, false, r, g, b);
            }
            rgb_out[y * width + x] = pack_rgb(r, g, b);
        }
    }
}

// -------------------------------------------------------------
// pr_controller simulation (FSM Hysteresis)
// -------------------------------------------------------------
// FSM logic simulating the transition delay of DFX reconfiguration
enum ControllerState {
    STATE_NORMAL = 0,
    STATE_CONFIRM_LOW_LIGHT = 1,
    STATE_LOW_LIGHT = 2,
    STATE_CONFIRM_NORMAL = 3
};

static bool run_pr_controller(bool raw_low_light_trigger) {
    static ControllerState state = STATE_NORMAL;
    static int frame_counter = 0;
    
    // Hysteresis window: 30 frames (~1 sec at 30 fps) to prevent frequent thrashing
    const int TRANSITION_THRESHOLD = 30;

    switch (state) {
        case STATE_NORMAL:
            if (raw_low_light_trigger) {
                state = STATE_CONFIRM_LOW_LIGHT;
                frame_counter = 1;
            }
            break;
        case STATE_CONFIRM_LOW_LIGHT:
            if (raw_low_light_trigger) {
                frame_counter++;
                if (frame_counter >= TRANSITION_THRESHOLD) {
                    state = STATE_LOW_LIGHT;
                }
            } else {
                state = STATE_NORMAL;
            }
            break;
        case STATE_LOW_LIGHT:
            if (!raw_low_light_trigger) {
                state = STATE_CONFIRM_NORMAL;
                frame_counter = 1;
            }
            break;
        case STATE_CONFIRM_NORMAL:
            if (!raw_low_light_trigger) {
                frame_counter++;
                if (frame_counter >= TRANSITION_THRESHOLD) {
                    state = STATE_NORMAL;
                }
            } else {
                state = STATE_LOW_LIGHT;
            }
            break;
    }

    return (state == STATE_LOW_LIGHT || state == STATE_CONFIRM_NORMAL);
}

}  // namespace

extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold,
    int arm_select) {
#pragma HLS INTERFACE m_axi port=raw_bayer offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=rgb_out offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=raw_bayer bundle=control
#pragma HLS INTERFACE s_axilite port=rgb_out bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=mode bundle=control
#pragma HLS INTERFACE s_axilite port=low_light_threshold bundle=control
#pragma HLS INTERFACE s_axilite port=arm_select bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    if (!raw_bayer || !rgb_out || width <= 0 || height <= 0) {
        return;
    }

    const bool raw_low_light = checker_select_low_light(raw_bayer, width, height, mode, low_light_threshold);

    switch (arm_select) {
        case DFXISP_ARM_BASELINE:
            pipeline_baseline(raw_bayer, rgb_out, width, height);
            break;
            
        case DFXISP_ARM_REGISTER_ONLY:
            pipeline_register_only(raw_bayer, rgb_out, width, height, raw_low_light);
            break;
            
        case DFXISP_ARM_DFX:
        default:
            // DFX FSM with hysteresis
            bool dfx_low_light = run_pr_controller(raw_low_light);
            pipeline_dfx(raw_bayer, rgb_out, width, height, dfx_low_light);
            break;
    }
}
