// SPDX-License-Identifier: MIT
// Minimal native HIP gate. Built in the candidate image, run only under a lease.
#include <hip/hip_runtime_api.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

struct Step {
    const char *name;
    hipError_t code;
};

int main() {
    const char *window = std::getenv("LIE_GPU_DIAGNOSTIC_WINDOW");
    if (!window || std::strcmp(window, "admitted") || access("/dev/kfd", F_OK)) {
        std::fputs("An admitted device window is required\n", stderr);
        return 2;
    }
    Step steps[16] = {};
    int used = 0;
    auto record = [&](const char *name, hipError_t code) {
        steps[used++] = {name, code};
        return code == hipSuccess;
    };
    int count = 0;
    size_t free_bytes = 0, total_bytes = 0;
    void *device = nullptr, *pinned = nullptr;
    const float host[8] = {1, 3, 2, 4, 5, 7, 6, 8};
    float output[8] = {};
    if (record("device_count", hipGetDeviceCount(&count)) && count == 1 &&
        record("set_device", hipSetDevice(0))) {
        record("memory_info", hipMemGetInfo(&free_bytes, &total_bytes));
        if (record("malloc_48", hipMalloc(&device, 48))) {
            record("memset_48", hipMemset(device, 0, 48));
            record("copy_pageable_h2d_32", hipMemcpy(device, host, 32, hipMemcpyHostToDevice));
            record("copy_pageable_h2d_8", hipMemcpy(device, host, 8, hipMemcpyHostToDevice));
            if (record("host_malloc_32", hipHostMalloc(&pinned, 32, 0))) {
                std::memcpy(pinned, host, 32);
                record("copy_pinned_h2d_32", hipMemcpy(device, pinned, 32, hipMemcpyHostToDevice));
            }
            record("copy_d2h_32", hipMemcpy(output, device, 32, hipMemcpyDeviceToHost));
            record("synchronize", hipDeviceSynchronize());
        }
    }
    if (pinned) record("host_free", hipHostFree(pinned));
    if (device) record("device_free", hipFree(device));
    std::printf("{\"scope\":\"GPU_RUNTIME_DIAGNOSTIC_NO_MODEL\",\"device_count\":%d,"
                "\"hip_free_bytes\":%zu,\"hip_total_bytes\":%zu,\"steps\":[",
                count, free_bytes, total_bytes);
    for (int i = 0; i < used; ++i) {
        if (i) std::putchar(',');
        std::printf("{\"step\":\"%s\",\"code\":%d,\"name\":\"%s\"}",
                    steps[i].name, static_cast<int>(steps[i].code), hipGetErrorName(steps[i].code));
    }
    std::printf("],\"output\":[");
    for (int i = 0; i < 8; ++i) {
        if (i) std::putchar(',');
        std::printf("%.9g", static_cast<double>(output[i]));
    }
    std::puts("]}");
    return 0;
}
