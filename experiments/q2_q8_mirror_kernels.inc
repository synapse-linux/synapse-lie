// SPDX-License-Identifier: MIT
// Exact GPU-only F16 mirror of original encoded Q8 weights. No file conversion.
__global__ void Q8MirrorWeightsKernel(const std::uint8_t* weights,
                                      __half* output, std::size_t blocks) {
  const std::size_t block = std::size_t(blockIdx.x) * blockDim.x + threadIdx.x;
  if (block >= blocks)
    return;
  const std::uint8_t* src = weights + block * 34;
  std::uint16_t d;
  __builtin_memcpy(&d, src, sizeof(d));
  const __half2 scale = __half2half2(__builtin_bit_cast(__half, d));
  const __half2 magic = __floats2half2_rn(-1152.0F, -1152.0F);
  const __half2 zero = __floats2half2_rn(0.0F, 0.0F);
#pragma unroll
  for (unsigned word = 0; word < 8; ++word) {
    std::uint32_t bits;
    __builtin_memcpy(&bits, src + 2 + word * 4, sizeof(bits));
    __half2 lo, hi;
    CodesToHalves(bits ^ 0x80808080U, magic, scale, zero, lo, hi);
    __builtin_memcpy(output + block * 32 + word * 4, &lo, sizeof(lo));
    __builtin_memcpy(output + block * 32 + word * 4 + 2, &hi, sizeof(hi));
  }
}

bool ConvertQ8Mirror(const void* weights, void* half, std::size_t elements,
                      hipStream_t stream) {
  if (weights == nullptr || half == nullptr || elements == 0 || elements % 32)
    return false;
  const std::size_t blocks = elements / 32;
  if ((blocks + 255) / 256 > 0xffffffffULL)
    return false;
  hipLaunchKernelGGL(Q8MirrorWeightsKernel, dim3((blocks + 255) / 256),
                     dim3(256), 0, stream,
                     static_cast<const std::uint8_t*>(weights),
                     static_cast<__half*>(half), blocks);
  return hipGetLastError() == hipSuccess;
}

bool DenseQ8MirrorGemm(const void* w, const __half* x, float* out,
                        std::size_t batch, std::size_t m, std::size_t k,
                        hipStream_t stream) {
  if (batch < 1024 || w == nullptr || x == nullptr || out == nullptr ||
      !(((m == 16384 || m == 13312) && k == 2560) || (m == 2560 && k == 6144)))
    return false;
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, false, false,
                          true, false, true>),
      dim3((batch + 127) / 128, (m + 255) / 256), dim3(256), 0, stream,
      w, x, out, batch, m, k);
  return hipGetLastError() == hipSuccess;
}

bool DenseQ8MirrorSsmGemm(const void* w, const __half* x, const float* conv_w,
                           const float* history, float* qkvz, float* convolved,
                           std::uint32_t n_tokens, std::uint32_t m,
                           std::uint32_t k, std::uint32_t channels,
                           std::uint32_t kernel, hipStream_t stream) {
  if (n_tokens < 1024 || m != 16384 || k != 2560 || channels != 10240 ||
      kernel != 4 || w == nullptr || x == nullptr || conv_w == nullptr ||
      history == nullptr || qkvz == nullptr || convolved == nullptr)
    return false;
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true, false,
                          true, false, true>),
      dim3((n_tokens + 127) / 128, m / 256), dim3(256), 0, stream,
      w, x, qkvz, n_tokens, m, k, nullptr, nullptr, nullptr, conv_w, convolved);
  if (hipGetLastError() != hipSuccess)
    return false;
  hipLaunchKernelGGL(SsmConvBoundaryKernel,
                     dim3(Blocks(channels), (n_tokens + 31) / 32, 3),
                     dim3(256), 0, stream, qkvz, conv_w, history, convolved,
                     n_tokens, channels, m);
  return hipGetLastError() == hipSuccess;
}

bool AttentionQ8MirrorGemm(const void* w, const __half* input,
                            const float* q_gamma, const float* k_gamma,
                            float* query, float* gate, __half* keys,
                            __half* values, std::uint32_t n_tokens,
                            const std::uint32_t* position, float theta,
                            float eps, hipStream_t stream,
                            const qwen::vision::DeviceRope* rope) {
  if (n_tokens < 1024 || w == nullptr || input == nullptr || q_gamma == nullptr ||
      k_gamma == nullptr || query == nullptr || gate == nullptr || keys == nullptr ||
      values == nullptr || position == nullptr)
    return false;
  const AttentionProjectionOutput output{q_gamma, k_gamma, query, gate, keys,
                                         values, position, theta, eps, rope};
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, false, true,
                          true, false, true>),
      dim3((n_tokens + 127) / 128, 52), dim3(256), 0, stream,
      w, input, nullptr, n_tokens, 13312, 2560, nullptr, nullptr, nullptr,
      nullptr, nullptr, output);
  return hipGetLastError() == hipSuccess;
}
