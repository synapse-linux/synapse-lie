/* SPDX-License-Identifier: MIT */
/* Synthetic HIP surface for the device admission test. No GPU calls. */
#ifndef LIE_TEST_HIP_RUNTIME_API_H
#define LIE_TEST_HIP_RUNTIME_API_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
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
typedef enum { hipMemcpyHostToDevice, hipMemcpyDeviceToHost } hipMemcpyKind;
hipError_t hipMemGetInfo(size_t *free_bytes, size_t *total_bytes);
hipError_t hipMalloc(void **pointer, size_t bytes);
hipError_t hipMemcpy(void *destination, const void *source, size_t bytes, hipMemcpyKind kind);
hipError_t hipMemset(void *pointer, int value, size_t bytes);
hipError_t hipFree(void *pointer);
#ifdef __cplusplus
}
#endif
#endif
