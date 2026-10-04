/* SPDX-License-Identifier: MIT */
/* Bounded device/runtime diagnostic. Never opens a model or an HTTP listener. */
#include <hip/hip_runtime_api.h>
#include <rocblas/rocblas.h>
#include <json-c/json.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "lie/executor.h"

extern lie_status lie_gufo_device_validate(lie_error *error);
extern int lie_gufo_device_identity(char *out, size_t cap);
extern void lie_gufo_quiesce_or_exit(void);

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--help")) {
        puts("Usage: lie-hip-probe --run\nRequires an admitted GPU lease. Checks target, HIP allocation/copy and rocBLAS SGEMM.\nNo model, model-fit, quantized-kernel or performance qualification.");
        return 0;
    }
    if (argc != 2 || strcmp(argv[1], "--run")) {
        fputs("Expected --run or --help\n", stderr);
        return 2;
    }
    lie_error error = {0};
    lie_status status = lie_gufo_device_validate(&error);
    if (status != LIE_OK) {
        fprintf(stderr, "Device admission failed (%d): %s\n", (int)status, error.message);
        return 1;
    }
    float *device = NULL;
    rocblas_handle handle = NULL;
    int code = 1;
    const char *stage = "identity";
    char identity[1024];
    size_t free_bytes = 0, total_bytes = 0;
    /* Column-major [[1,2],[3,4]] * [[5,6],[7,8]]. */
    const float inputs[8] = {1,3,2,4,5,7,6,8};
    const float expected[4] = {19,43,22,50};
    float output[4] = {0}, alpha = 1, beta = 0;
    if (!lie_gufo_device_identity(identity, sizeof(identity))) goto finish;
#define HIP_CHECK(label, call) do { stage = label; hipError_t e = (call); \
    if (e != hipSuccess) { fprintf(stderr, "%s: HIP status %d\n", stage, (int)e); goto finish; } } while (0)
#define BLAS_CHECK(label, call) do { stage = label; rocblas_status e = (call); \
    if (e != rocblas_status_success) { fprintf(stderr, "%s: rocBLAS status %d\n", stage, (int)e); goto finish; } } while (0)
    HIP_CHECK("memory_info", hipMemGetInfo(&free_bytes, &total_bytes));
    HIP_CHECK("allocate", hipMalloc((void **)&device, 12 * sizeof(float)));
    HIP_CHECK("copy_inputs", hipMemcpy(device, inputs, sizeof(inputs), hipMemcpyHostToDevice));
    HIP_CHECK("zero_output", hipMemset(device + 8, 0, 4 * sizeof(float)));
    BLAS_CHECK("create_blas", rocblas_create_handle(&handle));
    BLAS_CHECK("sgemm", rocblas_sgemm(handle, rocblas_operation_none, rocblas_operation_none,
               2, 2, 2, &alpha, device, 2, device + 4, 2, &beta, device + 8, 2));
    HIP_CHECK("complete", hipDeviceSynchronize());
    HIP_CHECK("copy_output", hipMemcpy(output, device + 8, sizeof(output), hipMemcpyDeviceToHost));
    stage = "numerical_check";
    for (size_t i = 0; i < 4; ++i)
        if (!isfinite(output[i]) || output[i] != expected[i]) goto finish;
    code = 0;
finish:
    /* Failed launches must retire before buffers/handles can be released. */
    if (code) lie_gufo_quiesce_or_exit();
    if (handle && rocblas_destroy_handle(handle) != rocblas_status_success) code = 1;
    if (device && hipFree(device) != hipSuccess) code = 1;
    if (code) {
        fprintf(stderr, "GPU runtime probe failed at %s; no model attempted\n", stage);
        return code;
    }
    struct json_object *record = json_object_new_object();
    if (!record) return 1;
#ifdef LIE_HIP_PROBE_SYNTHETIC
    json_object_object_add(record, "scope", json_object_new_string("SYNTHETIC_CPU_NOT_INFERENCE"));
#else
    json_object_object_add(record, "scope", json_object_new_string("GPU_RUNTIME_PROBE_NOT_MODEL_INFERENCE"));
#endif
    json_object_object_add(record, "build_id", json_object_new_string(LIE_BUILD_ID));
    json_object_object_add(record, "device", json_object_new_string(identity));
    json_object_object_add(record, "hip_free_bytes_before", json_object_new_uint64(free_bytes));
    json_object_object_add(record, "hip_total_bytes", json_object_new_uint64(total_bytes));
    json_object_object_add(record, "explicit_allocation_bytes", json_object_new_int(48));
    json_object_object_add(record, "sgemm_elements_verified", json_object_new_int(4));
    puts(json_object_to_json_string_ext(record, JSON_C_TO_STRING_PLAIN));
    json_object_put(record);
    return 0;
}
