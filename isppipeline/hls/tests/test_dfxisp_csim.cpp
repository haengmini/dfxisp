#include "dfxisp_accel.hpp"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

static uint8_t red(uint32_t p) { return uint8_t((p >> 16) & 0xff); }
static uint8_t green(uint32_t p) { return uint8_t((p >> 8) & 0xff); }
static uint8_t blue(uint32_t p) { return uint8_t(p & 0xff); }

int main() {
    constexpr int W = 4;
    constexpr int H = 4;
    uint16_t raw[W * H] = {
        64, 128, 80, 160,
        96,  64, 120, 80,
        70, 140, 90, 180,
        100, 75, 130, 95,
    };
    uint32_t normal[W * H] = {};
    uint32_t lowlight[W * H] = {};

    dfxisp_accel(raw, normal, W, H, DFXISP_MODE_NORMAL, 90);
    dfxisp_accel(raw, lowlight, W, H, DFXISP_MODE_LOW_LIGHT, 90);

    // RED requirement: normal mode preserves spatial shape and emits nonzero RGB.
    assert(normal[0] != 0);
    assert(red(normal[0]) >= 0 && green(normal[0]) >= 0 && blue(normal[0]) >= 0);

    // RED requirement: low-light mode brightens dark pixels relative to normal.
    assert(red(lowlight[0]) > red(normal[0]));
    assert(green(lowlight[0]) > green(normal[0]));
    assert(blue(lowlight[0]) > blue(normal[0]));

    // RED requirement: auto mode uses scene brightness threshold to select low-light.
    uint32_t auto_out[W * H] = {};
    dfxisp_accel(raw, auto_out, W, H, DFXISP_MODE_AUTO, 120);
    assert(auto_out[0] == lowlight[0]);

    // RED requirement: normal mode does not overflow past RGB8 range.
    uint16_t bright[W * H];
    for (int i = 0; i < W * H; ++i) bright[i] = 4095;
    uint32_t bright_out[W * H] = {};
    dfxisp_accel(bright, bright_out, W, H, DFXISP_MODE_LOW_LIGHT, 90);
    assert(red(bright_out[0]) == 255);
    assert(green(bright_out[0]) == 255);
    assert(blue(bright_out[0]) == 255);

    std::cout << "DFXISP C-sim smoke tests passed\n";
    return 0;
}
