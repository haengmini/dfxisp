// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XCHECKER_SCAN_H
#define XCHECKER_SCAN_H

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
#include "xchecker_scan_hw.h"

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
} XChecker_scan_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XChecker_scan;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XChecker_scan_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XChecker_scan_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XChecker_scan_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XChecker_scan_ReadReg(BaseAddress, RegOffset) \
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
int XChecker_scan_Initialize(XChecker_scan *InstancePtr, UINTPTR BaseAddress);
XChecker_scan_Config* XChecker_scan_LookupConfig(UINTPTR BaseAddress);
#else
int XChecker_scan_Initialize(XChecker_scan *InstancePtr, u16 DeviceId);
XChecker_scan_Config* XChecker_scan_LookupConfig(u16 DeviceId);
#endif
int XChecker_scan_CfgInitialize(XChecker_scan *InstancePtr, XChecker_scan_Config *ConfigPtr);
#else
int XChecker_scan_Initialize(XChecker_scan *InstancePtr, const char* InstanceName);
int XChecker_scan_Release(XChecker_scan *InstancePtr);
#endif

void XChecker_scan_Start(XChecker_scan *InstancePtr);
u32 XChecker_scan_IsDone(XChecker_scan *InstancePtr);
u32 XChecker_scan_IsIdle(XChecker_scan *InstancePtr);
u32 XChecker_scan_IsReady(XChecker_scan *InstancePtr);
void XChecker_scan_EnableAutoRestart(XChecker_scan *InstancePtr);
void XChecker_scan_DisableAutoRestart(XChecker_scan *InstancePtr);

void XChecker_scan_Set_raw_bayer(XChecker_scan *InstancePtr, u64 Data);
u64 XChecker_scan_Get_raw_bayer(XChecker_scan *InstancePtr);
void XChecker_scan_Set_width(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_width(XChecker_scan *InstancePtr);
void XChecker_scan_Set_height(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_height(XChecker_scan *InstancePtr);
void XChecker_scan_Set_mode(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_mode(XChecker_scan *InstancePtr);
void XChecker_scan_Set_dark_pixel_threshold(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_dark_pixel_threshold(XChecker_scan *InstancePtr);
void XChecker_scan_Set_verdict_pct(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_verdict_pct(XChecker_scan *InstancePtr);
void XChecker_scan_Set_enter_pct(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_enter_pct(XChecker_scan *InstancePtr);
void XChecker_scan_Set_exit_pct(XChecker_scan *InstancePtr, u32 Data);
u32 XChecker_scan_Get_exit_pct(XChecker_scan *InstancePtr);
u32 XChecker_scan_Get_selected_mode(XChecker_scan *InstancePtr);
u32 XChecker_scan_Get_selected_mode_vld(XChecker_scan *InstancePtr);
u32 XChecker_scan_Get_dark_count(XChecker_scan *InstancePtr);
u32 XChecker_scan_Get_dark_count_vld(XChecker_scan *InstancePtr);

void XChecker_scan_InterruptGlobalEnable(XChecker_scan *InstancePtr);
void XChecker_scan_InterruptGlobalDisable(XChecker_scan *InstancePtr);
void XChecker_scan_InterruptEnable(XChecker_scan *InstancePtr, u32 Mask);
void XChecker_scan_InterruptDisable(XChecker_scan *InstancePtr, u32 Mask);
void XChecker_scan_InterruptClear(XChecker_scan *InstancePtr, u32 Mask);
u32 XChecker_scan_InterruptGetEnabled(XChecker_scan *InstancePtr);
u32 XChecker_scan_InterruptGetStatus(XChecker_scan *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
