// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xnormalisp.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XNormalisp_CfgInitialize(XNormalisp *InstancePtr, XNormalisp_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XNormalisp_Start(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL) & 0x80;
    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XNormalisp_IsDone(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XNormalisp_IsIdle(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XNormalisp_IsReady(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XNormalisp_EnableAutoRestart(XNormalisp *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XNormalisp_DisableAutoRestart(XNormalisp *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_AP_CTRL, 0);
}

void XNormalisp_Set_raw_bayer(XNormalisp *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RAW_BAYER_DATA, (u32)(Data));
    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RAW_BAYER_DATA + 4, (u32)(Data >> 32));
}

u64 XNormalisp_Get_raw_bayer(XNormalisp *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RAW_BAYER_DATA);
    Data += (u64)XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RAW_BAYER_DATA + 4) << 32;
    return Data;
}

void XNormalisp_Set_rgb_out(XNormalisp *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RGB_OUT_DATA, (u32)(Data));
    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RGB_OUT_DATA + 4, (u32)(Data >> 32));
}

u64 XNormalisp_Get_rgb_out(XNormalisp *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RGB_OUT_DATA);
    Data += (u64)XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_RGB_OUT_DATA + 4) << 32;
    return Data;
}

void XNormalisp_Set_width(XNormalisp *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_WIDTH_DATA, Data);
}

u32 XNormalisp_Get_width(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_WIDTH_DATA);
    return Data;
}

void XNormalisp_Set_height(XNormalisp *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_HEIGHT_DATA, Data);
}

u32 XNormalisp_Get_height(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_HEIGHT_DATA);
    return Data;
}

u32 XNormalisp_Get_out_width(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_OUT_WIDTH_DATA);
    return Data;
}

u32 XNormalisp_Get_out_width_vld(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_OUT_WIDTH_CTRL);
    return Data & 0x1;
}

u32 XNormalisp_Get_out_height(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_OUT_HEIGHT_DATA);
    return Data;
}

u32 XNormalisp_Get_out_height_vld(XNormalisp *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_OUT_HEIGHT_CTRL);
    return Data & 0x1;
}

void XNormalisp_InterruptGlobalEnable(XNormalisp *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_GIE, 1);
}

void XNormalisp_InterruptGlobalDisable(XNormalisp *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_GIE, 0);
}

void XNormalisp_InterruptEnable(XNormalisp *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_IER);
    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_IER, Register | Mask);
}

void XNormalisp_InterruptDisable(XNormalisp *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_IER);
    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_IER, Register & (~Mask));
}

void XNormalisp_InterruptClear(XNormalisp *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XNormalisp_WriteReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_ISR, Mask);
}

u32 XNormalisp_InterruptGetEnabled(XNormalisp *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_IER);
}

u32 XNormalisp_InterruptGetStatus(XNormalisp *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XNormalisp_ReadReg(InstancePtr->Control_BaseAddress, XNORMALISP_CONTROL_ADDR_ISR);
}

