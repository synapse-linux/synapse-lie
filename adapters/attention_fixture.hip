/* SPDX-License-Identifier: MIT */
/* Generated component data only. Upstream types stay in this private adapter. */
#include "attention.h"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
#include <cstdio>
#include <cstring>

extern "C" void lie_gufo_quiesce_or_exit(void) noexcept;
namespace {
__global__ void fill_cache(const uint32_t *blocks, uint32_t count,
                          uint32_t short_base, __half *deep_k, __half *deep_v,
                          __half *short_k, __half *short_v) {
  const size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x;
  if (i >= size_t(count) * 4 * 512) return;
  const uint32_t rank = i / (4 * 512), key = (i / 512) % 4;
  const uint32_t column = i % 512, head = column / 256, dim = column % 256;
  const uint32_t logical = rank * 4 + key;
  const float k = dim ? 0.0f : float(int(logical % 17) - 8) / 8.0f;
  const float v = float(int(logical % 31) - 15) / 16.0f +
                  float(head * 3 + dim % 11) / 32.0f;
  const size_t deep = (size_t(blocks[rank]) * 4 + key) * 512 + column;
  const size_t short_at = (size_t(short_base + rank) * 4 + key) * 512 + column;
  deep_k[deep] = short_k[short_at] = __float2half(k);
  deep_v[deep] = short_v[short_at] = __float2half(v);
}
} // namespace

extern "C" int lie_attention_fixture_gpu(const lie_attention_fixture_plan *p,
                                          float *deep, float *short_out,
                                          lie_attention_fixture_result *r) {
  if (!p || !deep || !short_out || !r) return 1;
  *r = {};
  hipStream_t stream = nullptr;
  void *buffers[11]{};
  const size_t values = size_t(p->spec.rows) * LIE_ATTENTION_FIXTURE_WIDTH;
  const size_t output_bytes = values * sizeof(float);
  const size_t bytes[] = {
      size_t(p->deep_capacity) * 512 * sizeof(__half),
      size_t(p->deep_capacity) * 512 * sizeof(__half),
      size_t(p->short_capacity) * 512 * sizeof(__half),
      size_t(p->short_capacity) * 512 * sizeof(__half),
      size_t(p->spec.rows) * p->deep_pitch * sizeof(uint32_t),
      size_t(p->spec.rows) * p->short_pitch * sizeof(uint32_t),
      output_bytes, output_bytes, output_bytes, output_bytes,
      size_t(p->block_count) * sizeof(uint32_t)};
  for (size_t n : bytes) r->requested_device_bytes += n;
  float query[8 * LIE_ATTENTION_FIXTURE_WIDTH]{}, gate[8 * LIE_ATTENTION_FIXTURE_WIDTH]{};
  if (!p->spec.zero_query)
    for (uint32_t row = 0; row < p->spec.rows; ++row)
      for (uint32_t head = 0; head < 24; ++head)
        query[size_t(row) * LIE_ATTENTION_FIXTURE_WIDTH + head * 256] =
            16.0f * (1.0f + float(row) / 8.0f + float(head) / 16.0f);
  hipDeviceProp_t properties{};
  lie_attention_refusal refusal = LIE_ATTENTION_REFUSAL_NONE;
  bool short_ok = false, deep_ok = false;
  int code = 1;
#define HIP_CHECK(call) do { const hipError_t status = (call); \
    if (status != hipSuccess) { r->primary_error = uint32_t(status); goto done; } } while (0)
  HIP_CHECK(hipSetDevice(0));
  HIP_CHECK(hipGetDeviceProperties(&properties, 0));
  std::snprintf(r->device_arch, sizeof(r->device_arch), "%s", properties.gcnArchName);
  if (std::strncmp(properties.gcnArchName, LIE_HIP_ARCHITECTURE,
                   std::strlen(LIE_HIP_ARCHITECTURE)) ||
      (properties.gcnArchName[std::strlen(LIE_HIP_ARCHITECTURE)] != '\0' &&
       properties.gcnArchName[std::strlen(LIE_HIP_ARCHITECTURE)] != ':')) goto done;
  HIP_CHECK(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
  for (unsigned i = 0; i < 11; ++i) HIP_CHECK(hipMalloc(&buffers[i], bytes[i]));
  for (unsigned i = 0; i < 4; ++i) HIP_CHECK(hipMemsetAsync(buffers[i], 0, bytes[i], stream));
  HIP_CHECK(hipMemcpyAsync(buffers[4], p->deep_mask, bytes[4], hipMemcpyHostToDevice, stream));
  HIP_CHECK(hipMemcpyAsync(buffers[5], p->short_mask, bytes[5], hipMemcpyHostToDevice, stream));
  HIP_CHECK(hipMemcpyAsync(buffers[6], query, bytes[6], hipMemcpyHostToDevice, stream));
  HIP_CHECK(hipMemcpyAsync(buffers[7], gate, bytes[7], hipMemcpyHostToDevice, stream));
  HIP_CHECK(hipMemsetAsync(buffers[8], 0xff, bytes[8], stream));
  HIP_CHECK(hipMemsetAsync(buffers[9], 0xff, bytes[9], stream));
  HIP_CHECK(hipMemcpyAsync(buffers[10], p->blocks, bytes[10], hipMemcpyHostToDevice, stream));
  hipLaunchKernelGGL(fill_cache, dim3((size_t(p->block_count) * 4 * 512 + 255) / 256),
                     dim3(256), 0, stream, static_cast<uint32_t *>(buffers[10]),
                     p->block_count, p->short_base, static_cast<__half *>(buffers[0]),
                     static_cast<__half *>(buffers[1]), static_cast<__half *>(buffers[2]),
                     static_cast<__half *>(buffers[3]));
  HIP_CHECK(hipGetLastError());
  deep_ok = gufo::models::qwen38_flash_next::rocm::WmmaCausalAttention(
      static_cast<float *>(buffers[6]), static_cast<float *>(buffers[7]),
      static_cast<__half *>(buffers[0]), static_cast<__half *>(buffers[1]),
      static_cast<uint32_t *>(buffers[4]), p->deep_pitch,
      static_cast<float *>(buffers[8]), p->spec.rows, p->deep_start,
      24, 2, 256, 4, stream, false, &refusal);
  r->accepted = deep_ok; r->refusal = uint32_t(refusal);
  HIP_CHECK(hipGetLastError());
  short_ok = gufo::models::qwen38_flash_next::rocm::WmmaCausalAttention(
      static_cast<float *>(buffers[6]), static_cast<float *>(buffers[7]),
      static_cast<__half *>(buffers[2]), static_cast<__half *>(buffers[3]),
      static_cast<uint32_t *>(buffers[5]), p->short_pitch,
      static_cast<float *>(buffers[9]), p->spec.rows, p->short_start,
      24, 2, 256, 4, stream, false, nullptr);
  r->short_accepted = short_ok;
  HIP_CHECK(hipGetLastError());
  HIP_CHECK(hipMemcpyAsync(deep, buffers[8], output_bytes, hipMemcpyDeviceToHost, stream));
  HIP_CHECK(hipMemcpyAsync(short_out, buffers[9], output_bytes, hipMemcpyDeviceToHost, stream));
  HIP_CHECK(hipStreamSynchronize(stream));
  r->gpu_execution = true;
  r->output_unchanged = true;
  for (size_t i = 0; i < values; ++i) {
    uint32_t bits = 0; std::memcpy(&bits, deep + i, sizeof(bits));
    if (bits != UINT32_MAX) r->output_unchanged = false;
  }
  r->expected_refusal = !LIE_LONG_CONTEXT_WMMA && p->deep_pitch > 2048 &&
      !deep_ok && refusal == LIE_ATTENTION_REFUSAL_MASK_PITCH && r->output_unchanged;
  code = !short_ok || (!deep_ok && !r->expected_refusal);
done:
  /* If a failed asynchronous operation cannot retire, the process must exit
   * before any borrowed host memory or owned device allocation is released. */
  if (r->primary_error) lie_gufo_quiesce_or_exit();
  for (void *buffer : buffers) {
    if (!buffer) continue;
    const auto status = hipFree(buffer);
    if (status != hipSuccess && !r->cleanup_error) r->cleanup_error = uint32_t(status);
  }
  if (stream) {
    const auto status = hipStreamDestroy(stream);
    if (status != hipSuccess && !r->cleanup_error) r->cleanup_error = uint32_t(status);
  }
#undef HIP_CHECK
  return code || r->cleanup_error ? 1 : 0;
}
