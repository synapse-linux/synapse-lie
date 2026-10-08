// SPDX-License-Identifier: MIT
// Independent serial-per-block GPU format oracle; no upstream kernel helpers.
#include <hip/hip_runtime.h>
#include <cmath>
#include <cstdint>
#include <cstddef>

__global__ void ScalarQ8Format(const float* x, unsigned char* out,
                               std::size_t n, std::size_t k) {
  const std::size_t block = blockIdx.x * std::size_t(blockDim.x) + threadIdx.x;
  if (block >= n * (k / 32)) return;
  const std::size_t row = block / (k / 32), column_block = block % (k / 32);
  const float* src = x + row * k + column_block * 32;
  float maximum = 0.0f;
  for (unsigned i = 0; i < 32; ++i) maximum = fmaxf(maximum, fabsf(src[i]));
  const float d = maximum / 127.0f;
  const float inverse = d != 0.0f ? 1.0f / d : 0.0f;
  const std::size_t tile = ((row / 16) * (k / 32) + column_block) * 576;
  for (unsigned i = 0; i < 32; ++i)
    out[tile + (i / 16) * 256 + (row % 16) * 16 + i % 16] =
        static_cast<unsigned char>(static_cast<signed char>(roundf(src[i] * inverse)));
  *reinterpret_cast<float*>(out + tile + 512 + (row % 16) * 4) = d;
}

extern "C" hipError_t q2_shared_q8_scalar_oracle(const float* x, void* out,
                                                 std::size_t n, std::size_t k,
                                                 hipStream_t stream) {
  if (!x || !out || !n || !k || k % 32) return hipErrorInvalidValue;
  hipLaunchKernelGGL(ScalarQ8Format, dim3((n * (k / 32) + 127) / 128),
                     dim3(128), 0, stream, x, static_cast<unsigned char*>(out), n, k);
  return hipGetLastError();
}
