#include "dfxisp_accel.hpp"

#include <cstdint>
#include <iostream>

namespace {

constexpr int W = 8;
constexpr int H = 8;

bool run_case(uint16_t value, int requested_mode, int expected_mode) {
    uint16_t raw[W * H];
    uint32_t rgb[W * H] = {};
    for (int i = 0; i < W * H; ++i) raw[i] = value;

    // Every pointer on the synthesized top-level interface must designate
    // valid storage. In particular, do not pass nullptr for the ap_vld output:
    // the generated co-simulation wrapper records and post-checks that port.
    int out_width = 0;
    int out_height = 0;
    int selected_mode = -1;
    int selected_rm = -1;
    int hyst_flags = -1;
    dfxisp_accel(raw, rgb, W, H, requested_mode, 512,
                 &out_width, &out_height, &selected_mode, &selected_rm,
                 &hyst_flags);

    const int expected_width = expected_mode == DFXISP_MODE_LOW_LIGHT ? W / 2 : W;
    const int expected_height = expected_mode == DFXISP_MODE_LOW_LIGHT ? H / 2 : H;
    const int expected_rm = expected_mode == DFXISP_MODE_LOW_LIGHT
                                ? DFXISP_RM_LOW_LIGHT_TONE
                                : DFXISP_RM_NORMAL_TONE;
    return selected_mode == expected_mode && selected_rm == expected_rm &&
           out_width == expected_width && out_height == expected_height &&
           rgb[0] != 0 && hyst_flags >= 0;
}

}  // namespace

int main() {
    // Two transactions exercise both datapaths and let the co-sim report an
    // interval, while keeping this wrapper-facing test deterministic and small.
    const bool normal_ok = run_case(1600, DFXISP_MODE_NORMAL, DFXISP_MODE_NORMAL);
    const bool low_ok = run_case(200, DFXISP_MODE_LOW_LIGHT, DFXISP_MODE_LOW_LIGHT);
    if (!normal_ok || !low_ok) {
        std::cerr << "DFXISP C/RTL co-simulation checks failed\n";
        return 1;
    }
    std::cout << "DFXISP C/RTL co-simulation checks passed\n";
    return 0;
}
