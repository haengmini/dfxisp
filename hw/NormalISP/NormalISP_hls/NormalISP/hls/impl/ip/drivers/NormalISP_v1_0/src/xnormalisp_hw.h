// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// control
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read/COR)
//        bit 7  - auto_restart (Read/Write)
//        bit 9  - interrupt (Read)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0 - enable ap_done interrupt (Read/Write)
//        bit 1 - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0 - ap_done (Read/TOW)
//        bit 1 - ap_ready (Read/TOW)
//        others - reserved
// 0x10 : Data signal of raw_bayer
//        bit 31~0 - raw_bayer[31:0] (Read/Write)
// 0x14 : Data signal of raw_bayer
//        bit 31~0 - raw_bayer[63:32] (Read/Write)
// 0x18 : reserved
// 0x1c : Data signal of rgb_out
//        bit 31~0 - rgb_out[31:0] (Read/Write)
// 0x20 : Data signal of rgb_out
//        bit 31~0 - rgb_out[63:32] (Read/Write)
// 0x24 : reserved
// 0x28 : Data signal of width
//        bit 31~0 - width[31:0] (Read/Write)
// 0x2c : reserved
// 0x30 : Data signal of height
//        bit 31~0 - height[31:0] (Read/Write)
// 0x34 : reserved
// 0x38 : Data signal of out_width
//        bit 31~0 - out_width[31:0] (Read)
// 0x3c : Control signal of out_width
//        bit 0  - out_width_ap_vld (Read/COR)
//        others - reserved
// 0x48 : Data signal of out_height
//        bit 31~0 - out_height[31:0] (Read)
// 0x4c : Control signal of out_height
//        bit 0  - out_height_ap_vld (Read/COR)
//        others - reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XNORMALISP_CONTROL_ADDR_AP_CTRL         0x00
#define XNORMALISP_CONTROL_ADDR_GIE             0x04
#define XNORMALISP_CONTROL_ADDR_IER             0x08
#define XNORMALISP_CONTROL_ADDR_ISR             0x0c
#define XNORMALISP_CONTROL_ADDR_RAW_BAYER_DATA  0x10
#define XNORMALISP_CONTROL_BITS_RAW_BAYER_DATA  64
#define XNORMALISP_CONTROL_ADDR_RGB_OUT_DATA    0x1c
#define XNORMALISP_CONTROL_BITS_RGB_OUT_DATA    64
#define XNORMALISP_CONTROL_ADDR_WIDTH_DATA      0x28
#define XNORMALISP_CONTROL_BITS_WIDTH_DATA      32
#define XNORMALISP_CONTROL_ADDR_HEIGHT_DATA     0x30
#define XNORMALISP_CONTROL_BITS_HEIGHT_DATA     32
#define XNORMALISP_CONTROL_ADDR_OUT_WIDTH_DATA  0x38
#define XNORMALISP_CONTROL_BITS_OUT_WIDTH_DATA  32
#define XNORMALISP_CONTROL_ADDR_OUT_WIDTH_CTRL  0x3c
#define XNORMALISP_CONTROL_ADDR_OUT_HEIGHT_DATA 0x48
#define XNORMALISP_CONTROL_BITS_OUT_HEIGHT_DATA 32
#define XNORMALISP_CONTROL_ADDR_OUT_HEIGHT_CTRL 0x4c

