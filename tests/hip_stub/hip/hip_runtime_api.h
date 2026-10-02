/* SPDX-License-Identifier: MIT */
/* Synthetic HIP surface for the device admission test. No GPU calls. */
#ifndef LIE_TEST_HIP_RUNTIME_API_H
#define LIE_TEST_HIP_RUNTIME_API_H
typedef int hipError_t;
enum { hipSuccess = 0 };
typedef struct {
    char gcnArchName[256], name[256];
    int warpSize, pciDomainID, pciBusID, pciDeviceID;
} hipDeviceProp_t;
hipError_t hipGetDevice(int *device);
hipError_t hipGetDeviceProperties(hipDeviceProp_t *properties, int device);
hipError_t hipDriverGetVersion(int *version);
hipError_t hipRuntimeGetVersion(int *version);
hipError_t hipDeviceSynchronize(void);
#endif
