#include "dfxisp_accel.hpp"

#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static uint8_t red(uint32_t p) { return uint8_t((p >> 16) & 0xff); }
static uint8_t green(uint32_t p) { return uint8_t((p >> 8) & 0xff); }
static uint8_t blue(uint32_t p) { return uint8_t(p & 0xff); }

struct GoldenCase {
    std::string name;
    int in_w = 0, in_h = 0, mode = 0;
    uint16_t threshold = 0;
    int out_w = 0, out_h = 0, sel_mode = 0, sel_rm = 0;
    std::vector<uint16_t> raw;
    std::vector<uint32_t> expected;
};

static void check_golden_vectors(const char* path) {
    std::ifstream f(path);
    if (!f) {
        std::cout << "DFXISP golden vector compare skipped (" << path << " not found)\n";
        return;
    }
    std::string line;
    std::getline(f, line);  // header
    std::vector<GoldenCase> cases;
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::vector<std::string> col;
        std::string cell;
        while (std::getline(ss, cell, ',')) col.push_back(cell);
        assert(col.size() == 12);

        const std::string& name = col[0];
        if (cases.empty() || cases.back().name != name) {
            GoldenCase c;
            c.name = name;
            c.in_w = std::stoi(col[1]);
            c.in_h = std::stoi(col[2]);
            c.mode = std::stoi(col[3]);
            c.threshold = static_cast<uint16_t>(std::stoul(col[4]));
            c.out_w = std::stoi(col[5]);
            c.out_h = std::stoi(col[6]);
            c.sel_mode = std::stoi(col[7]);
            c.sel_rm = std::stoi(col[8]);
            c.raw.assign(c.in_w * c.in_h, 0);
            c.expected.assign(c.out_w * c.out_h, 0);
            cases.push_back(c);
        }
        GoldenCase& c = cases.back();
        const std::string& kind = col[9];
        const int idx = std::stoi(col[10]);
        if (kind == "raw") {
            assert(idx >= 0 && idx < c.in_w * c.in_h);
            c.raw[idx] = static_cast<uint16_t>(std::stoul(col[11]));
        } else {
            assert(idx >= 0 && idx < c.out_w * c.out_h);
            c.expected[idx] = static_cast<uint32_t>(std::stoul(col[11], nullptr, 0));
        }
    }

    int checked = 0;
    for (const GoldenCase& c : cases) {
        std::vector<uint32_t> got(c.in_w * c.in_h, 0);  // capacity >= out
        DfxIspResult res{};
        dfxisp_accel(c.raw.data(), got.data(), c.in_w, c.in_h, c.mode, c.threshold, &res);

        // metadata gates (mode / selected RM / output shape)
        assert(res.selected_mode == c.sel_mode);
        assert(res.selected_rm == c.sel_rm);
        assert(res.out_width == c.out_w && res.out_height == c.out_h);
        // mutually exclusive tone RM: exactly one selected, consistent with mode
        assert(res.selected_rm == (res.selected_mode == DFXISP_MODE_LOW_LIGHT
                                       ? DFXISP_RM_LOW_LIGHT_TONE : DFXISP_RM_NORMAL_TONE));
        // low-light is shape-changing (Policy A); normal preserves shape
        if (res.selected_mode == DFXISP_MODE_LOW_LIGHT) {
            assert(res.out_width == (c.in_w / 2 < 1 ? 1 : c.in_w / 2));
            assert(res.out_height == (c.in_h / 2 < 1 ? 1 : c.in_h / 2));
        } else {
            assert(res.out_width == c.in_w && res.out_height == c.in_h);
        }

        for (int i = 0; i < c.out_w * c.out_h; ++i) {
            if (got[i] != c.expected[i]) {
                std::cerr << "golden mismatch case=" << c.name << " index=" << i
                          << " expected=0x" << std::hex << c.expected[i]
                          << " got=0x" << got[i] << std::dec << "\n";
                assert(got[i] == c.expected[i]);
            }
            ++checked;
        }
    }
    std::cout << "DFXISP golden vector compare passed (" << checked << " pixels)\n";
}

int main() {
    constexpr int W = 8, H = 8;

    // Uniform mid-level frame: normal and low-light derive from the same baseline
    // value, isolating the tone RM effect (mutual exclusion + no double gain/gamma).
    uint16_t mid[W * H];
    for (int i = 0; i < W * H; ++i) mid[i] = 1600;

    uint32_t normal[W * H] = {};
    DfxIspResult rn{};
    dfxisp_accel(mid, normal, W, H, DFXISP_MODE_NORMAL, 512, &rn);
    // normal: identity tone RM, shape preserved, baseline output nonzero
    assert(rn.selected_mode == DFXISP_MODE_NORMAL);
    assert(rn.selected_rm == DFXISP_RM_NORMAL_TONE);
    assert(rn.out_width == W && rn.out_height == H);
    assert(normal[0] != 0);

    uint32_t low[W * H] = {};
    DfxIspResult rl{};
    dfxisp_accel(mid, low, W, H, DFXISP_MODE_LOW_LIGHT, 512, &rl);
    // low-light: low-light tone RM, shape halved (Policy A)
    assert(rl.selected_mode == DFXISP_MODE_LOW_LIGHT);
    assert(rl.selected_rm == DFXISP_RM_LOW_LIGHT_TONE);
    assert(rl.out_width == W / 2 && rl.out_height == H / 2);
    // low-light tone (gain 2.0x + gamma2.0) brightens vs normal tone (gain 1.25x + gamma2.0).
    assert(red(low[0]) > red(normal[0]));
    assert(green(low[0]) > green(normal[0]));
    assert(blue(low[0]) > blue(normal[0]));

    // AUTO on a dark frame selects the low-light tone RM.
    uint16_t dark[W * H];
    for (int i = 0; i < W * H; ++i) dark[i] = 200;
    uint32_t adark[W * H] = {};
    DfxIspResult rad{};
    dfxisp_accel(dark, adark, W, H, DFXISP_MODE_AUTO, 512, &rad);
    assert(rad.selected_mode == DFXISP_MODE_LOW_LIGHT);
    assert(rad.selected_rm == DFXISP_RM_LOW_LIGHT_TONE);

    // AUTO on a bright frame stays normal (identity tone RM).
    uint16_t bright[W * H];
    for (int i = 0; i < W * H; ++i) bright[i] = 3000;
    uint32_t abright[W * H] = {};
    DfxIspResult rab{};
    dfxisp_accel(bright, abright, W, H, DFXISP_MODE_AUTO, 512, &rab);
    assert(rab.selected_mode == DFXISP_MODE_NORMAL);
    assert(rab.selected_rm == DFXISP_RM_NORMAL_TONE);

    // Saturation: gain + gamma2.0 tone never overflows RGB8.
    uint16_t sat[W * H];
    for (int i = 0; i < W * H; ++i) sat[i] = 4095;
    uint32_t sat_out[W * H] = {};
    DfxIspResult rs{};
    dfxisp_accel(sat, sat_out, W, H, DFXISP_MODE_LOW_LIGHT, 512, &rs);
    assert(red(sat_out[0]) == 255 && green(sat_out[0]) == 255 && blue(sat_out[0]) == 255);

    check_golden_vectors("tests/golden_vectors.csv");

    std::cout << "DFXISP C-sim smoke tests passed\n";
    return 0;
}
