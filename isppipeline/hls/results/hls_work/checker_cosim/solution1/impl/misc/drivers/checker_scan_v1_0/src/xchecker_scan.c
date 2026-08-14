// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xchecker_scan.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XChecker_scan_CfgInitialize(XChecker_scan *InstancePtr, XChecker_scan_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XChecker_scan_Start(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL) & 0x80;
    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XChecker_scan_IsDone(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XChecker_scan_IsIdle(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XChecker_scan_IsReady(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XChecker_scan_EnableAutoRestart(XChecker_scan *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XChecker_scan_DisableAutoRestart(XChecker_scan *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_AP_CTRL, 0);
}

void XChecker_scan_Set_raw_bayer(XChecker_scan *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_RAW_BAYER_DATA, (u32)(Data));
    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_RAW_BAYER_DATA + 4, (u32)(Data >> 32));
}

u64 XChecker_scan_Get_raw_bayer(XChecker_scan *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_RAW_BAYER_DATA);
    Data += (u64)XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_RAW_BAYER_DATA + 4) << 32;
    return Data;
}

void XChecker_scan_Set_width(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_WIDTH_DATA, Data);
}

u32 XChecker_scan_Get_width(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_WIDTH_DATA);
    return Data;
}

void XChecker_scan_Set_height(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_HEIGHT_DATA, Data);
}

u32 XChecker_scan_Get_height(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_HEIGHT_DATA);
    return Data;
}

void XChecker_scan_Set_mode(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_MODE_DATA, Data);
}

u32 XChecker_scan_Get_mode(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_MODE_DATA);
    return Data;
}

void XChecker_scan_Set_dark_pixel_threshold(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_DARK_PIXEL_THRESHOLD_DATA, Data);
}

u32 XChecker_scan_Get_dark_pixel_threshold(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_DARK_PIXEL_THRESHOLD_DATA);
    return Data;
}

void XChecker_scan_Set_verdict_pct(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_VERDICT_PCT_DATA, Data);
}

u32 XChecker_scan_Get_verdict_pct(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_VERDICT_PCT_DATA);
    return Data;
}

void XChecker_scan_Set_enter_pct(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_ENTER_PCT_DATA, Data);
}

u32 XChecker_scan_Get_enter_pct(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_ENTER_PCT_DATA);
    return Data;
}

void XChecker_scan_Set_exit_pct(XChecker_scan *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_EXIT_PCT_DATA, Data);
}

u32 XChecker_scan_Get_exit_pct(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_EXIT_PCT_DATA);
    return Data;
}

u32 XChecker_scan_Get_selected_mode(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_SELECTED_MODE_DATA);
    return Data;
}

u32 XChecker_scan_Get_selected_mode_vld(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_SELECTED_MODE_CTRL);
    return Data & 0x1;
}

u32 XChecker_scan_Get_dark_count(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_DARK_COUNT_DATA);
    return Data;
}

u32 XChecker_scan_Get_dark_count_vld(XChecker_scan *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_DARK_COUNT_CTRL);
    return Data & 0x1;
}

void XChecker_scan_InterruptGlobalEnable(XChecker_scan *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_GIE, 1);
}

void XChecker_scan_InterruptGlobalDisable(XChecker_scan *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_GIE, 0);
}

void XChecker_scan_InterruptEnable(XChecker_scan *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_IER);
    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_IER, Register | Mask);
}

void XChecker_scan_InterruptDisable(XChecker_scan *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_IER);
    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_IER, Register & (~Mask));
}

void XChecker_scan_InterruptClear(XChecker_scan *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChecker_scan_WriteReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_ISR, Mask);
}

u32 XChecker_scan_InterruptGetEnabled(XChecker_scan *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_IER);
}

u32 XChecker_scan_InterruptGetStatus(XChecker_scan *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChecker_scan_ReadReg(InstancePtr->Control_BaseAddress, XCHECKER_SCAN_CONTROL_ADDR_ISR);
}

