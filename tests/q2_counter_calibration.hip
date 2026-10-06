// SPDX-License-Identifier: MIT
// Synthetic profiler calibration only; no model or inference implementation.
#include <hip/hip_runtime.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

constexpr unsigned threads = 16384;
constexpr unsigned block_threads = 256;
constexpr unsigned guard = 32;
constexpr size_t input_bytes = 256u * 1024u * 1024u;
constexpr size_t vectors = input_bytes / sizeof(uint4);
constexpr uint32_t sentinel = 0xfedcba98u;
static_assert(threads % block_threads == 0 && vectors % threads == 0);

static void check(hipError_t code, const char *what) {
    if (code != hipSuccess) {
        std::fprintf(stderr, "HIP failure: %s: %s\n", what, hipGetErrorString(code));
        std::exit(2);
    }
}
#define HIP(call) check((call), #call)

__host__ __device__ static uint32_t mix(uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352du;
    x ^= x >> 15;
    x *= 0x846ca68bu;
    return x ^ (x >> 16);
}

extern "C" __global__ __launch_bounds__(block_threads)
void q2_counter_wave_probe(uint32_t *out, uint32_t salt) {
    const unsigned id = blockIdx.x * blockDim.x + threadIdx.x;
    out[id] = mix(id ^ salt);
}

extern "C" __global__ __launch_bounds__(block_threads)
void q2_counter_read_probe(const uint4 *__restrict__ in, uint32_t *out) {
    const unsigned id = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t sum = 0;
    for (size_t i = id; i < vectors; i += threads) {
        const uint4 v = in[i];
        sum += v.x + v.y + v.z + v.w;
    }
    out[id] = sum;
}

int main(int argc, char **argv) {
    if (argc != 2 || (std::strcmp(argv[1], "waves") && std::strcmp(argv[1], "read"))) {
        std::fprintf(stderr, "Usage: q2-counter-calibration waves|read\n");
        return 2;
    }
    const bool read_mode = !std::strcmp(argv[1], "read");
    hipDeviceProp_t properties{};
    HIP(hipGetDeviceProperties(&properties, 0));
    if (std::strncmp(properties.gcnArchName, "gfx1151", 7) || properties.warpSize != 32) {
        std::fprintf(stderr, "Expected gfx1151 with wave size 32\n");
        return 2;
    }
    std::vector<uint32_t> actual(threads + 2 * guard, sentinel);
    std::vector<uint32_t> expected(threads, 0);
    uint32_t *device_out = nullptr;
    uint4 *device_in = nullptr;
    HIP(hipMalloc(&device_out, actual.size() * sizeof(uint32_t)));
    if (read_mode) {
        std::vector<uint4> input(vectors);
        for (size_t i = 0; i < vectors; ++i) {
            const uint32_t base = static_cast<uint32_t>(i * 4);
            input[i] = {mix(base), mix(base + 1), mix(base + 2), mix(base + 3)};
            const uint4 v = input[i];
            expected[i % threads] += v.x + v.y + v.z + v.w;
        }
        HIP(hipMalloc(&device_in, input_bytes));
        HIP(hipMemcpy(device_in, input.data(), input_bytes, hipMemcpyHostToDevice));
    }
    std::printf("{\"event\":\"geometry\",\"mode\":\"%s\",\"threads\":%u,"
                "\"block_threads\":%u,\"expected_waves\":%u,\"input_bytes\":%zu,"
                "\"compute_units\":%d,\"iterations\":10}\n",
                argv[1], threads, block_threads, threads / 32,
                read_mode ? input_bytes : size_t{0}, properties.multiProcessorCount);
    for (unsigned rep = 0; rep < 10; ++rep) {
        const uint32_t salt = 0x1f2e3d4cu + rep;
        std::fill(actual.begin(), actual.end(), sentinel);
        HIP(hipMemcpy(device_out, actual.data(), actual.size() * sizeof(uint32_t), hipMemcpyHostToDevice));
        if (read_mode) {
            hipLaunchKernelGGL(q2_counter_read_probe, dim3(threads / block_threads), dim3(block_threads),
                               0, 0, device_in, device_out + guard);
        } else {
            hipLaunchKernelGGL(q2_counter_wave_probe, dim3(threads / block_threads), dim3(block_threads),
                               0, 0, device_out + guard, salt);
            for (unsigned i = 0; i < threads; ++i) expected[i] = mix(i ^ salt);
        }
        HIP(hipGetLastError());
        HIP(hipDeviceSynchronize());
        HIP(hipMemcpy(actual.data(), device_out, actual.size() * sizeof(uint32_t), hipMemcpyDeviceToHost));
        for (unsigned i = 0; i < actual.size(); ++i) {
            const uint32_t wanted = i < guard || i >= guard + threads ? sentinel : expected[i - guard];
            if (actual[i] != wanted) {
                std::fprintf(stderr, "Output mismatch: iteration %u index %u actual %u expected %u\n",
                             rep, i, actual[i], wanted);
                return 2;
            }
        }
        std::printf("{\"event\":\"check\",\"mode\":\"%s\",\"rep\":%u,"
                    "\"output_words\":%u,\"guard_words\":%u,\"exact\":true}\n",
                    argv[1], rep, threads, 2 * guard);
        std::fflush(stdout);
    }
    if (device_in) HIP(hipFree(device_in));
    HIP(hipFree(device_out));
    return 0;
}
