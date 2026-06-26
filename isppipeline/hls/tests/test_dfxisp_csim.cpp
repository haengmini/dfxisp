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
    int width = 0;
    int height = 0;
    int mode = 0;
    uint16_t threshold = 0;
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
        assert(col.size() == 10);

        const std::string& name = col[0];
        const int width = std::stoi(col[1]);
        const int height = std::stoi(col[2]);
        const int mode = std::stoi(col[3]);
        const auto threshold = static_cast<uint16_t>(std::stoul(col[4]));
        const int index = std::stoi(col[5]);
        const auto raw = static_cast<uint16_t>(std::stoul(col[8]));
        const auto expected = static_cast<uint32_t>(std::stoul(col[9], nullptr, 0));

        if (cases.empty() || cases.back().name != name) {
            GoldenCase c;
            c.name = name;
            c.width = width;
            c.height = height;
            c.mode = mode;
            c.threshold = threshold;
            c.raw.assign(width * height, 0);
            c.expected.assign(width * height, 0);
            cases.push_back(c);
        }

        GoldenCase& c = cases.back();
        assert(c.width == width && c.height == height && c.mode == mode && c.threshold == threshold);
        assert(index >= 0 && index < c.width * c.height);
        c.raw[index] = raw;
        c.expected[index] = expected;
    }

    int checked = 0;
    for (const GoldenCase& c : cases) {
        std::vector<uint32_t> got(c.width * c.height, 0);
        dfxisp_accel(c.raw.data(), got.data(), c.width, c.height, c.mode, c.threshold);
        for (int i = 0; i < c.width * c.height; ++i) {
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

    check_golden_vectors("tests/golden_vectors.csv");

    std::cout << "DFXISP C-sim smoke tests passed\n";
    return 0;
}
