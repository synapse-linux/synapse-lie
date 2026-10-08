// SPDX-License-Identifier: MIT
// Independently written implementation of DS4's documented projection edit.
// No DS4/Gufo kernel source is copied. This is an activation primitive, not a
// CPU model executor. GPU numerical and performance qualification are separate.
#include "steering.hpp"
namespace {
constexpr unsigned kThreads = 256;
__global__ void remove_direction(float* activations, const float* direction,
                                 unsigned width, float scale) {
  __shared__ float sums[kThreads];
  float* row = activations + static_cast<size_t>(blockIdx.x) * width;
  float sum = 0.0f;
  for (unsigned long long i = threadIdx.x; i < width; i += kThreads)
    sum += row[i] * direction[i];
  sums[threadIdx.x] = sum;
  __syncthreads();
  for (unsigned stride = kThreads / 2; stride; stride /= 2) {
    if (threadIdx.x < stride)
      sums[threadIdx.x] += sums[threadIdx.x + stride];
    __syncthreads();
  }
  const float amount = scale * sums[0];
  for (unsigned long long i = threadIdx.x; i < width; i += kThreads)
    row[i] -= amount * direction[i];
}
}
hipError_t lie_hip_direction_remove(float* activations, const float* direction,
  const lie_steering_activation& plan, hipStream_t stream) {
  // Validate even a zero-scale descriptor, then bypass every GPU call. The
  // provider never substitutes a dummy direction allocation for steering off.
  lie_steering_activation checked{};
  checked.abi_version = LIE_STEERING_ACTIVATION_ABI;
  checked.struct_bytes = sizeof(checked);
  if (lie_steering_activation_prepare(plan.width, plan.tokens, plan.branches,
        plan.scale, plan.activation_bytes, plan.direction_bytes, &checked,
        nullptr) != LIE_OK || plan.abi_version != checked.abi_version ||
      plan.struct_bytes != checked.struct_bytes || plan.rows != checked.rows ||
      plan.elements != checked.elements ||
      plan.activation_bytes != checked.activation_bytes ||
      plan.direction_bytes != checked.direction_bytes)
    return hipErrorInvalidValue;
  if (checked.scale == 0.0f) return hipSuccess;
  if (!activations || !direction) return hipErrorInvalidValue;
  hipLaunchKernelGGL(remove_direction, dim3(checked.rows), dim3(kThreads),
                     0, stream, activations, direction, checked.width,
                     checked.scale);
  return hipGetLastError();
}
