#pragma once

#include <cstdint>

// 설계 근거·파이프라인 유도·상수 출처: docs/LowlightISP.md

enum LowlightISPBinning : int {
    LOWLIGHT_ISP_BIN_SUBSAMPLE = 0,
    LOWLIGHT_ISP_BIN_BINNING = 1,
};

extern "C" void LowlightISP_dev(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int bin_mode,
    int* out_width,
    int* out_height);

extern "C" void LowlightISP(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int* out_width,
    int* out_height);
