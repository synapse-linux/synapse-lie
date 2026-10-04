/* SPDX-License-Identifier: MIT */
/* Fault injection for probe lifetimes. This binary cannot access a GPU. */
#include <hip/hip_runtime_api.h>
#include <rocblas/rocblas.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int sync_calls;
static int fault(const char *name) {
    const char *value = getenv("LIE_PROBE_FAULT");
    return value && !strcmp(value, name);
}
hipError_t hipGetDevice(int *device) { *device = 0; return fault("device"); }
hipError_t hipGetDeviceProperties(hipDeviceProp_t *p, int device) {
    (void)device;
    memset(p, 0, sizeof(*p));
    strcpy(p->gcnArchName, fault("arch") ? "gfx1151" : "gfx1150");
    strcpy(p->name, "SYNTHETIC HIP fixture");
    p->warpSize = 32;
    return 0;
}
hipError_t hipDriverGetVersion(int *version) { *version = 70200; return fault("identity"); }
hipError_t hipRuntimeGetVersion(int *version) { *version = 70200; return 0; }
hipError_t hipMemGetInfo(size_t *f, size_t *t) { *f = 64; *t = 128; return fault("memory_info"); }
hipError_t hipMalloc(void **p, size_t n) {
    if (fault("allocate")) return 1;
    *p = malloc(n);
    return !*p;
}
hipError_t hipMemcpy(void *d, const void *s, size_t n, hipMemcpyKind k) {
    if (fault(k == hipMemcpyHostToDevice ? "copy_inputs" : "copy_output")) return 1;
    memcpy(d, s, n);
    return 0;
}
hipError_t hipMemset(void *p, int v, size_t n) {
    if (fault("zero_output")) return 1;
    memset(p, v, n);
    return 0;
}
hipError_t hipDeviceSynchronize(void) {
    ++sync_calls;
    return fault("quiesce") || (fault("complete") && sync_calls == 1);
}
hipError_t hipFree(void *p) { free(p); return fault("free"); }
rocblas_status rocblas_create_handle(rocblas_handle *h) {
    if (fault("create_blas")) return 1;
    *h = malloc(1);
    return !*h;
}
rocblas_status rocblas_destroy_handle(rocblas_handle h) { free(h); return fault("destroy_blas"); }
rocblas_status rocblas_sgemm(rocblas_handle h, rocblas_operation a, rocblas_operation b,
    int m, int n, int k, const float *alpha, const float *x, int ldx,
    const float *y, int ldy, const float *beta, float *z, int ldz) {
    if (!h || a || b || m != 2 || n != 2 || k != 2 || *alpha != 1 || *beta != 0 ||
        ldx != 2 || ldy != 2 || ldz != 2 || x[0] != 1 || y[0] != 5) abort();
    if (fault("sgemm")) return 1;
    /* Fixed fixture response, deliberately no CPU model or BLAS forward. */
    const float answer[4] = {19,43,22,50};
    memcpy(z, answer, sizeof(answer));
    if (fault("wrong_output")) z[0] = 20;
    if (fault("nan_output")) z[0] = NAN;
    return 0;
}
