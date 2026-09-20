// =============================================================================
// File   : LowlightISP/LowlightISP_tb.cpp
// Function: Vitis HLS C-simulation testbench for LowlightISP / LowlightISP_dev.
//
// Mirrors NormalISP/NormalISP_tb.cpp's approach: this repo carries only
// LowlightISP.cpp/.hpp (docs/LowlightISP.md), not the origin repo's Python
// golden generator (tools/gen_lowlight_isp_golden.py, haengmini/dfxisp) that
// produces the bit-exact reference vectors. This testbench is therefore a
// STRUCTURAL/SANITY check, not a bit-exact golden comparison:
//   - output shape is Policy A: out_width/out_height == bin_dim(width/height)
//     == max(1, dim/2), for even, odd and 1-pixel dimensions
//   - packed RGB888 0x00RRGGBB format (no stray high byte)
//   - guarded inputs (null pointers, non-positive width/height)
//   - a flat Bayer scene bins to a spatially uniform output (every binned
//     pixel identical, no border caveat -- unlike NormalISP's 3x3 demosaic
//     window, binning has no cross-color-parity clamp artifact)
//   - a green-channel ramp stays non-decreasing after the full pipeline
//   - saturated (4095) input lands EXACTLY on 0x00FFFFFF: BLC+gain clamp
//     every channel to RAW12_MAX before the CCM (whose rows sum to 256), and
//     gamma's LUT[255] == 255, so this is an exact check, not a tolerance
//   - BINNING and SUBSAMPLE modes produce different output on a scene with
//     cell-to-cell variation (binning averages a 2x2 neighborhood of cells;
//     subsample reads a single site) -- guards against the two modes
//     silently collapsing into the same computation
//   - the board top LowlightISP() is bit-identical to
//     LowlightISP_dev(..., LOWLIGHT_ISP_BIN_BINNING, ...), since that is its
//     definition
//
// Bit-exact verification against the Python golden still requires the
// original generator; run this first as a fast structural gate before that.
//
// Vitis HLS C-sim convention: main() returns 0 on PASS, nonzero on FAIL.
// =============================================================================

#include "LowlightISP.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

int g_failures = 0;

void check(bool cond, const char* what) {
    if (cond) {
        std::printf("[ OK ] %s\n", what);
    } else {
        std::printf("[FAIL] %s\n", what);
        ++g_failures;
    }
}

inline int bin_dim_ref(int d) { return d / 2 < 1 ? 1 : d / 2; }

// RGGB parity: (even_y, even_x)=R ; (even_y,!even_x)=G ; (!even_y,even_x)=G ; else B
inline bool is_r_site(int x, int y) { return (y % 2 == 0) && (x % 2 == 0); }
inline bool is_b_site(int x, int y) { return (y % 2 != 0) && (x % 2 != 0); }

// Every site of a given color holds the same 12-bit value -> a spatially flat
// scene once binned.
std::vector<uint16_t> make_flat(int w, int h, int r12, int g12, int b12) {
    std::vector<uint16_t> raw(static_cast<size_t>(w) * h);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            int v = is_r_site(x, y) ? r12 : (is_b_site(x, y) ? b12 : g12);
            raw[y * w + x] = static_cast<uint16_t>(v);
        }
    return raw;
}

// Horizontal ramp written into every G site (indexed by the site's own x);
// R/B sites held flat so the ramp is isolated to the green channel.
std::vector<uint16_t> make_gradient(int w, int h) {
    std::vector<uint16_t> raw(static_cast<size_t>(w) * h);
    const int denom = (w > 1) ? (w - 1) : 1;
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            int ramp = 512 + (3072 * x) / denom;  // 512..3584, monotonic in x
            int v = is_r_site(x, y) ? 800 : (is_b_site(x, y) ? 800 : ramp);
            raw[y * w + x] = static_cast<uint16_t>(v);
        }
    return raw;
}

// Checkerboard by binning-CELL index (not by raw pixel), so BINNING's
// cross-cell averaging and SUBSAMPLE's single-site read see different data:
// every 2x2 raw block (one binning cell) is uniform inside, but neighboring
// cells alternate between two value sets.
std::vector<uint16_t> make_cell_checkerboard(int w, int h) {
    std::vector<uint16_t> raw(static_cast<size_t>(w) * h);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            const int cx = x / 2, cy = y / 2;
            const bool odd_cell = ((cx + cy) & 1) != 0;
            const int r = odd_cell ? 3000 : 1000;
            const int b = odd_cell ? 2800 : 1200;
            const int g = odd_cell ? 2600 : 1400;
            int v = is_r_site(x, y) ? r : (is_b_site(x, y) ? b : g);
            raw[y * w + x] = static_cast<uint16_t>(v);
        }
    return raw;
}

inline uint8_t r_of(uint32_t p) { return static_cast<uint8_t>((p >> 16) & 0xFF); }
inline uint8_t g_of(uint32_t p) { return static_cast<uint8_t>((p >> 8) & 0xFF); }
inline uint8_t b_of(uint32_t p) { return static_cast<uint8_t>(p & 0xFF); }

void case_shape_and_format() {
    std::printf("-- case: Policy A shape (bin_dim) + packed RGB888 format --\n");
    static const int dims[][2] = {{16, 12}, {1, 1}, {2, 2}, {9, 7}, {64, 48}};
    for (const auto& d : dims) {
        const int w = d[0], h = d[1];
        const int expect_w = bin_dim_ref(w), expect_h = bin_dim_ref(h);
        std::vector<uint16_t> raw = make_gradient(w, h);
        std::vector<uint32_t> out(static_cast<size_t>(expect_w) * expect_h, 0xFFFFFFFFu);
        int ow = -1, oh = -1;
        LowlightISP(raw.data(), out.data(), w, h, &ow, &oh);

        char msg[160];
        std::snprintf(msg, sizeof(msg), "out_width/out_height == bin_dim(%d,%d) == %dx%d",
                      w, h, expect_w, expect_h);
        check(ow == expect_w && oh == expect_h, msg);

        bool fmt_ok = true;
        for (size_t i = 0; i < out.size(); ++i)
            if (out[i] > 0x00FFFFFFu) fmt_ok = false;
        std::snprintf(msg, sizeof(msg), "all pixels fit 0x00RRGGBB for %dx%d input", w, h);
        check(fmt_ok, msg);
    }
}

void case_null_and_invalid_args() {
    std::printf("-- case: guarded inputs (null pointers / non-positive dims) --\n");
    int ow = 123, oh = 456;
    LowlightISP(nullptr, nullptr, 16, 16, &ow, &oh);
    check(ow == 0 && oh == 0, "null raw_bayer/rgb_out -> out_width/out_height cleared to 0");

    std::vector<uint16_t> raw = make_flat(4, 4, 1000, 1000, 1000);
    std::vector<uint32_t> out(4, 0);
    ow = 123; oh = 456;
    LowlightISP(raw.data(), out.data(), 0, 4, &ow, &oh);
    check(ow == 0 && oh == 0, "width <= 0 -> out_width/out_height cleared to 0");
}

void case_flat_frame_uniform_output() {
    std::printf("-- case: flat scene bins to a spatially uniform output (no border caveat) --\n");
    const int w = 16, h = 12;
    std::vector<uint16_t> raw = make_flat(w, h, 1500, 1400, 1300);
    const int bw = bin_dim_ref(w), bh = bin_dim_ref(h);
    std::vector<uint32_t> out(static_cast<size_t>(bw) * bh);
    int ow, oh;
    LowlightISP_dev(raw.data(), out.data(), w, h, LOWLIGHT_ISP_BIN_BINNING, &ow, &oh);

    const uint32_t first = out[0];
    bool uniform = true;
    for (int y = 0; y < bh; ++y)
        for (int x = 0; x < bw; ++x)
            if (out[y * bw + x] != first) uniform = false;
    check(uniform, "flat Bayer input (BINNING) -> identical packed RGB at every binned pixel");
}

void case_gradient_nondecreasing() {
    std::printf("-- case: green-channel ramp stays non-decreasing after the pipeline --\n");
    const int w = 32, h = 8;
    std::vector<uint16_t> raw = make_gradient(w, h);
    const int bw = bin_dim_ref(w), bh = bin_dim_ref(h);
    std::vector<uint32_t> out(static_cast<size_t>(bw) * bh);
    int ow, oh;
    LowlightISP_dev(raw.data(), out.data(), w, h, LOWLIGHT_ISP_BIN_BINNING, &ow, &oh);

    static const int fractions[] = {0, 1, 2, 3, 4};  // of bw/4
    int prev = -1;
    bool nondecreasing = true;
    for (int f : fractions) {
        int x = (f * (bw - 1)) / 4;
        int g = g_of(out[x]);
        if (prev >= 0 && g < prev) nondecreasing = false;
        prev = g;
    }
    check(nondecreasing, "green channel non-decreasing across sparse binned samples left-to-right");
}

void case_saturation_clamped_exact() {
    std::printf("-- case: saturated (4095) input lands exactly on 0x00FFFFFF --\n");
    // BLC+gain clamp every channel to RAW12_MAX=4095 before the CCM (rows sum
    // to 256, so 4095 in -> 4095 out on every row), and GAMMA2_LUT[4095>>4]
    // == GAMMA2_LUT[255] == 255. This holds for both bin modes since a flat
    // input makes binning's average equal subsample's single site.
    const int w = 8, h = 8;
    std::vector<uint16_t> raw = make_flat(w, h, 4095, 4095, 4095);
    const int bw = bin_dim_ref(w), bh = bin_dim_ref(h);
    std::vector<uint32_t> out_bin(static_cast<size_t>(bw) * bh);
    std::vector<uint32_t> out_sub(static_cast<size_t>(bw) * bh);
    int ow, oh;
    LowlightISP_dev(raw.data(), out_bin.data(), w, h, LOWLIGHT_ISP_BIN_BINNING, &ow, &oh);
    LowlightISP_dev(raw.data(), out_sub.data(), w, h, LOWLIGHT_ISP_BIN_SUBSAMPLE, &ow, &oh);

    bool all_white_bin = true, all_white_sub = true;
    for (size_t i = 0; i < out_bin.size(); ++i) if (out_bin[i] != 0x00FFFFFFu) all_white_bin = false;
    for (size_t i = 0; i < out_sub.size(); ++i) if (out_sub[i] != 0x00FFFFFFu) all_white_sub = false;
    check(all_white_bin, "fully saturated raw (BINNING) -> every pixel == 0x00FFFFFF exactly");
    check(all_white_sub, "fully saturated raw (SUBSAMPLE) -> every pixel == 0x00FFFFFF exactly");
}

void case_binning_vs_subsample_differ() {
    std::printf("-- case: BINNING and SUBSAMPLE diverge on cell-to-cell variation --\n");
    const int w = 16, h = 16;
    std::vector<uint16_t> raw = make_cell_checkerboard(w, h);
    const int bw = bin_dim_ref(w), bh = bin_dim_ref(h);
    std::vector<uint32_t> out_bin(static_cast<size_t>(bw) * bh);
    std::vector<uint32_t> out_sub(static_cast<size_t>(bw) * bh);
    int ow, oh;
    LowlightISP_dev(raw.data(), out_bin.data(), w, h, LOWLIGHT_ISP_BIN_BINNING, &ow, &oh);
    LowlightISP_dev(raw.data(), out_sub.data(), w, h, LOWLIGHT_ISP_BIN_SUBSAMPLE, &ow, &oh);

    const bool differ = std::memcmp(out_bin.data(), out_sub.data(),
                                    sizeof(uint32_t) * out_bin.size()) != 0;
    check(differ, "BINNING output != SUBSAMPLE output on a scene with cell-to-cell variation");
}

void case_board_top_matches_dev_binning() {
    std::printf("-- case: board top LowlightISP() matches LowlightISP_dev(..., BINNING, ...) exactly --\n");
    const int w = 20, h = 15;
    std::vector<uint16_t> raw = make_gradient(w, h);
    const int bw = bin_dim_ref(w), bh = bin_dim_ref(h);
    std::vector<uint32_t> out_board(static_cast<size_t>(bw) * bh);
    std::vector<uint32_t> out_dev(static_cast<size_t>(bw) * bh);
    int ow1, oh1, ow2, oh2;
    LowlightISP(raw.data(), out_board.data(), w, h, &ow1, &oh1);
    LowlightISP_dev(raw.data(), out_dev.data(), w, h, LOWLIGHT_ISP_BIN_BINNING, &ow2, &oh2);

    const bool same = (ow1 == ow2) && (oh1 == oh2) &&
                       (std::memcmp(out_board.data(), out_dev.data(),
                                    sizeof(uint32_t) * out_board.size()) == 0);
    check(same, "LowlightISP() output == LowlightISP_dev(BINNING) output, bit-for-bit");
}

}  // namespace

int main() {
    case_shape_and_format();
    case_null_and_invalid_args();
    case_flat_frame_uniform_output();
    case_gradient_nondecreasing();
    case_saturation_clamped_exact();
    case_binning_vs_subsample_differ();
    case_board_top_matches_dev_binning();

    if (g_failures == 0) {
        std::printf("=== LowlightISP_tb: ALL CHECKS PASSED ===\n");
        return 0;
    }
    std::printf("=== LowlightISP_tb: %d CHECK(S) FAILED ===\n", g_failures);
    return 1;
}
