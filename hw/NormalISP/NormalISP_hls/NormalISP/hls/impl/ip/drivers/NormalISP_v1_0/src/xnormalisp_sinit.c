// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "xnormalisp.h"

extern XNormalisp_Config XNormalisp_ConfigTable[];

#ifdef SDT
XNormalisp_Config *XNormalisp_LookupConfig(UINTPTR BaseAddress) {
	XNormalisp_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XNormalisp_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XNormalisp_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XNormalisp_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XNormalisp_Initialize(XNormalisp *InstancePtr, UINTPTR BaseAddress) {
	XNormalisp_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XNormalisp_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XNormalisp_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XNormalisp_Config *XNormalisp_LookupConfig(u16 DeviceId) {
	XNormalisp_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XNORMALISP_NUM_INSTANCES; Index++) {
		if (XNormalisp_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XNormalisp_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XNormalisp_Initialize(XNormalisp *InstancePtr, u16 DeviceId) {
	XNormalisp_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XNormalisp_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XNormalisp_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

