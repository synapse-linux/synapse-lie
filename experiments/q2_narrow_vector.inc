// SPDX-License-Identifier: MIT
// Component-only experiment: same scalar F16 conversion, wider memory access.
__global__ void NarrowF16VectorKernel(const float* x, __half* out,
                                    std::size_t count) {
  const std::size_t i =
      4 * (blockIdx.x * static_cast<std::size_t>(blockDim.x) + threadIdx.x);
  if (i >= count)
    return;
  if (count - i >= 4) {
    const float4 values = *reinterpret_cast<const float4*>(x + i);
    const __half a(values.x), b(values.y), c(values.z), d(values.w);
    const auto lo = std::uint32_t(__builtin_bit_cast(std::uint16_t, a)) |
                    (std::uint32_t(__builtin_bit_cast(std::uint16_t, b)) << 16);
    const auto hi = std::uint32_t(__builtin_bit_cast(std::uint16_t, c)) |
                    (std::uint32_t(__builtin_bit_cast(std::uint16_t, d)) << 16);
    *reinterpret_cast<uint2*>(out + i) = make_uint2(lo, hi);
  } else {
    // The final allocation ends at count; no padded vector read or write.
    for (std::size_t j = i; j < count; ++j)
      out[j] = __half(x[j]);
  }
}

bool NarrowF16Vector(const float* x, __half* out, std::size_t count,
                     hipStream_t stream) {
  if (count == 0)
    return true;
  // Bound both vector launch and scalar alignment fallback before arithmetic.
  if (!x || !out || count > std::size_t{0xFFFFFFFFU} * kThreads)
    return false;
  if ((reinterpret_cast<std::uintptr_t>(x) & 15U) != 0 ||
      (reinterpret_cast<std::uintptr_t>(out) & 7U) != 0) {
    NarrowActivations(x, out, false, count, stream);
  } else {
    const std::size_t vectors = count / 4 + (count % 4 != 0);
    hipLaunchKernelGGL(NarrowF16VectorKernel, dim3(Blocks(vectors)),
                       dim3(kThreads), 0, stream, x, out, count);
  }
  return hipGetLastError() == hipSuccess;
}
