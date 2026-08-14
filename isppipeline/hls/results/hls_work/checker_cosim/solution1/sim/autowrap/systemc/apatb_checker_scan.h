// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================

extern "C" void AESL_WRAP_checker_scan (
volatile void* raw_bayer,
int width,
int height,
int mode,
short dark_pixel_threshold,
int verdict_pct,
int enter_pct,
int exit_pct,
volatile void* selected_mode,
volatile void* hyst_flags,
volatile void* dark_count);
