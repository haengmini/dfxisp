// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XNORMALISP_H
#define XNORMALISP_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xnormalisp_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Control_BaseAddress;
} XNormalisp_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XNormalisp;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XNormalisp_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XNormalisp_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XNormalisp_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XNormalisp_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XNormalisp_Initialize(XNormalisp *InstancePtr, UINTPTR BaseAddress);
XNormalisp_Config* XNormalisp_LookupConfig(UINTPTR BaseAddress);
#else
int XNormalisp_Initialize(XNormalisp *InstancePtr, u16 DeviceId);
XNormalisp_Config* XNormalisp_LookupConfig(u16 DeviceId);
#endif
int XNormalisp_CfgInitialize(XNormalisp *InstancePtr, XNormalisp_Config *ConfigPtr);
#else
int XNormalisp_Initialize(XNormalisp *InstancePtr, const char* InstanceName);
int XNormalisp_Release(XNormalisp *InstancePtr);
#endif

void XNormalisp_Start(XNormalisp *InstancePtr);
u32 XNormalisp_IsDone(XNormalisp *InstancePtr);
u32 XNormalisp_IsIdle(XNormalisp *InstancePtr);
u32 XNormalisp_IsReady(XNormalisp *InstancePtr);
void XNormalisp_EnableAutoRestart(XNormalisp *InstancePtr);
void XNormalisp_DisableAutoRestart(XNormalisp *InstancePtr);

void XNormalisp_Set_raw_bayer(XNormalisp *InstancePtr, u64 Data);
u64 XNormalisp_Get_raw_bayer(XNormalisp *InstancePtr);
void XNormalisp_Set_rgb_out(XNormalisp *InstancePtr, u64 Data);
u64 XNormalisp_Get_rgb_out(XNormalisp *InstancePtr);
void XNormalisp_Set_width(XNormalisp *InstancePtr, u32 Data);
u32 XNormalisp_Get_width(XNormalisp *InstancePtr);
void XNormalisp_Set_height(XNormalisp *InstancePtr, u32 Data);
u32 XNormalisp_Get_height(XNormalisp *InstancePtr);
u32 XNormalisp_Get_out_width(XNormalisp *InstancePtr);
u32 XNormalisp_Get_out_width_vld(XNormalisp *InstancePtr);
u32 XNormalisp_Get_out_height(XNormalisp *InstancePtr);
u32 XNormalisp_Get_out_height_vld(XNormalisp *InstancePtr);

void XNormalisp_InterruptGlobalEnable(XNormalisp *InstancePtr);
void XNormalisp_InterruptGlobalDisable(XNormalisp *InstancePtr);
void XNormalisp_InterruptEnable(XNormalisp *InstancePtr, u32 Mask);
void XNormalisp_InterruptDisable(XNormalisp *InstancePtr, u32 Mask);
void XNormalisp_InterruptClear(XNormalisp *InstancePtr, u32 Mask);
u32 XNormalisp_InterruptGetEnabled(XNormalisp *InstancePtr);
u32 XNormalisp_InterruptGetStatus(XNormalisp *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
