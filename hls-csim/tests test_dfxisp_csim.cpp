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
        
        // Use Register-only arm to compare against golden vectors since Register-only mode 
        // does not have FSM hysteresis delay, allowing immediate frame evaluation.
        dfxisp_accel(c.raw.data(), got.data(), c.width, c.height, c.mode, c.threshold, DFXISP_ARM_REGISTER_ONLY);
        
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
    
    // -------------------------------------------------------------
    // Smoke Test 1: Arm 1 (Register-only Adaptive) instant mode transition
    // -------------------------------------------------------------
    uint32_t normal[W * H] = {};
    uint32_t lowlight[W * H] = {};

    dfxisp_accel(raw, normal, W, H, DFXISP_MODE_NORMAL, 90, DFXISP_ARM_REGISTER_ONLY);
    dfxisp_accel(raw, lowlight, W, H, DFXISP_MODE_LOW_LIGHT, 90, DFXISP_ARM_REGISTER_ONLY);

    // Normal mode outputs non-zero RGB
    assert(normal[0] != 0);
    assert(red(normal[0]) >= 0 && green(normal[0]) >= 0 && blue(normal[0]) >= 0);

    // Low-light mode brightens dark pixels relative to normal
    assert(red(lowlight[0]) > red(normal[0]));
    assert(green(lowlight[0]) > green(normal[0]));
    assert(blue(lowlight[0]) > blue(normal[0]));

    // Auto mode triggers low-light since scene average is low
    uint32_t auto_out[W * H] = {};
    dfxisp_accel(raw, auto_out, W, H, DFXISP_MODE_AUTO, 120, DFXISP_ARM_REGISTER_ONLY);
    assert(auto_out[0] == lowlight[0]);

    // High input saturation clamp check
    uint16_t bright[W * H];
    for (int i = 0; i < W * H; ++i) bright[i] = 4095;
    uint32_t bright_out[W * H] = {};
    dfxisp_accel(bright, bright_out, W, H, DFXISP_MODE_LOW_LIGHT, 90, DFXISP_ARM_REGISTER_ONLY);
    assert(red(bright_out[0]) == 255);
    assert(green(bright_out[0]) == 255);
    assert(blue(bright_out[0]) == 255);

    // -------------------------------------------------------------
    // Smoke Test 2: Arm 0 (Baseline Fixed)
    // -------------------------------------------------------------
    uint32_t baseline_normal[W * H] = {};
    uint32_t baseline_lowlight[W * H] = {};
    dfxisp_accel(raw, baseline_normal, W, H, DFXISP_MODE_NORMAL, 90, DFXISP_ARM_BASELINE);
    dfxisp_accel(raw, baseline_lowlight, W, H, DFXISP_MODE_LOW_LIGHT, 90, DFXISP_ARM_BASELINE);
    // Baseline should remain unchanged regardless of low-light trigger
    assert(baseline_normal[0] == baseline_lowlight[0]);
    assert(baseline_normal[0] == normal[0]);

    // -------------------------------------------------------------
    // Smoke Test 3: Arm 2 (DFX Adaptive) Hysteresis transition
    // -------------------------------------------------------------
    uint32_t dfx_out[W * H] = {};
    
    // Initial state: DFX in NORMAL state, should match baseline output
    dfxisp_accel(raw, dfx_out, W, H, DFXISP_MODE_LOW_LIGHT, 90, DFXISP_ARM_DFX);
    assert(dfx_out[0] == normal[0]); // Has not transitioned yet

    // Run 30 consecutive low-light frames to trigger reconfiguration transition
    for (int f = 0; f < 30; ++f) {
        dfxisp_accel(raw, dfx_out, W, H, DFXISP_MODE_LOW_LIGHT, 90, DFXISP_ARM_DFX);
    }
    // Now DFX should have reconfigured to low-light state, matching lowlight output
    assert(dfx_out[0] == lowlight[0]);

    // Check golden vector database values
    check_golden_vectors("tests/golden_vectors.csv");

    std::cout << "DFXISP C-sim smoke tests passed\n";
    return 0;
}
