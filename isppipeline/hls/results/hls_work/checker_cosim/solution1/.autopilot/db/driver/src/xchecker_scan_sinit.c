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
#include "xchecker_scan.h"

extern XChecker_scan_Config XChecker_scan_ConfigTable[];

#ifdef SDT
XChecker_scan_Config *XChecker_scan_LookupConfig(UINTPTR BaseAddress) {
	XChecker_scan_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XChecker_scan_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XChecker_scan_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XChecker_scan_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChecker_scan_Initialize(XChecker_scan *InstancePtr, UINTPTR BaseAddress) {
	XChecker_scan_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChecker_scan_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChecker_scan_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XChecker_scan_Config *XChecker_scan_LookupConfig(u16 DeviceId) {
	XChecker_scan_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XCHECKER_SCAN_NUM_INSTANCES; Index++) {
		if (XChecker_scan_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XChecker_scan_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChecker_scan_Initialize(XChecker_scan *InstancePtr, u16 DeviceId) {
	XChecker_scan_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChecker_scan_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChecker_scan_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

