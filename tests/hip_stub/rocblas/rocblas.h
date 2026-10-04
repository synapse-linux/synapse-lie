/* SPDX-License-Identifier: MIT */
/* Synthetic fixture; never a numerical reference implementation. */
#ifndef LIE_TEST_ROCBLAS_H
#define LIE_TEST_ROCBLAS_H
typedef void *rocblas_handle;
typedef int rocblas_status;
typedef int rocblas_operation;
enum { rocblas_status_success = 0, rocblas_operation_none = 0 };
rocblas_status rocblas_create_handle(rocblas_handle *handle);
rocblas_status rocblas_destroy_handle(rocblas_handle handle);
rocblas_status rocblas_sgemm(rocblas_handle handle, rocblas_operation a, rocblas_operation b,
    int m, int n, int k, const float *alpha, const float *x, int ldx,
    const float *y, int ldy, const float *beta, float *z, int ldz);
#endif
