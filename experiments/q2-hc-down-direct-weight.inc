// SPDX-License-Identifier: MIT
/*
MIT License

Copyright (c) 2023-2026 The ggml authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
// Adapted from Aristo94/GSQHalo.cpp,
// pin5fc881b114c1ea130f5df6a30a98be2f8d397de6, ggml/src/ggml-cuda/mmb.cu
// mmb_hcd_kernel and fragment loaders. LIE adaptation: original F16 operands,
// two K16 chains, gfx1151 only. Arithmetic equivalence to hipBLASLt7526 is not
// asserted.
namespace {

// Original F16 HC weights and activations; native16-byte loads, BK256
// staging, one LDS buffer and direct F32 stores. No model conversion.
template<int BM, int BN, int WTM, int WTN, int BK, int NBUF = 2>
__global__ void __launch_bounds__(256, 1)
    HcDownDirectWeightKernel(const std::uint16_t* __restrict__ W,
                             const std::uint16_t* __restrict__ X,
                             float* __restrict__ D, const int M, const int K,
                             const int T, const int ldw, const int ldx) {
  constexpr int WAVES_M = BM / WTM, WAVES_N = (256 / 32) / WAVES_M,
                TM = WTM / 16, TN = WTN / 16;
  static_assert(WAVES_M * WTM == BM && WAVES_N * WTN == BN &&
                    WAVES_M * WAVES_N == 256 / 32,
                "8 waves cover the tile");
  static_assert(BM == 64 && BN == 32 && WTM == 16 && WTN == 16 && BK == 256 &&
                NBUF == 1);
  constexpr int LDS = BK + 8, CPR = BK / 8;  // 16-byte chunks per row slice
  constexpr int B_IT = (BN * CPR + 256 - 1) / 256;
  __shared__ __align__(16) std::uint16_t Bs[NBUF][BN * LDS];
  const int tid = threadIdx.x, lane = tid & 31, wave = tid >> 5;
  const int wm = wave % WAVES_M, wn = wave / WAVES_M;
  const int m0 = blockIdx.x * BM, t0 = blockIdx.y * BN;
  // global and LDS element offsets of this thread's chunks; rows past the
  // matrix are clamped to its last row (they only feed outputs that are never
  // stored), chunks past the tile (BM * CPR not a multiple of the block) are
  // not stored
  const std::uint16_t* bp[B_IT];
  int bl[B_IT];
#pragma unroll
  for (int i = 0; i < B_IT; ++i) {
    const int c = tid + i * 256;
    bp[i] = X + (size_t)min(t0 + c / CPR, T - 1) * ldx + (c % CPR) * 8;
    bl[i] = c < BN * CPR ? (c / CPR) * LDS + (c % CPR) * 8 : -1;
  }
  HcDownVector4 rb[B_IT];
#pragma unroll
  for (int i = 0; i < B_IT; ++i)
    rb[i] = *(const HcDownVector4*)bp[i];
#pragma unroll
  for (int i = 0; i < B_IT; ++i)
    if (bl[i] >= 0)
      *(HcDownVector4*)(Bs[0] + bl[i]) = rb[i];
  __syncthreads();
  v8f acc[TM][TN], high[TM][TN]{};
#pragma unroll
  for (int i = 0; i < TM; ++i)
#pragma unroll
    for (int j = 0; j < TN; ++j)
#pragma unroll
      for (int e = 0; e < 8; ++e)
        acc[i][j][e] = 0.f;
  const int nks = K / BK, r = lane & 15;
  for (int ks = 0; ks < nks; ++ks) {
    const int s = NBUF == 2 ? (ks & 1) : 0;
    const bool more = ks + 1 < nks;
    if (more) {  // next K step's global loads in flight during this step's
                 // WMMAs
      const int k0 = (ks + 1) * BK;
#pragma unroll
      for (int i = 0; i < B_IT; ++i)
        rb[i] = *(const HcDownVector4*)(bp[i] + k0);
    }
#pragma unroll 2
    for (int kk = 0; kk < BK; kk += 16) {
      v16h a[TM], b[TN];
#pragma unroll
      for (int i = 0; i < TM; ++i)
        a[i] = HcDownFragment16(W + (size_t)(m0 + wm * WTM + i * 16 + r) * ldw +
                                ks * BK + kk);
#pragma unroll
      for (int j = 0; j < TN; ++j)
        b[j] = HcDownFragment16(Bs[s] + (wn * WTN + j * 16 + r) * LDS + kk);
#pragma unroll
      for (int i = 0; i < TM; ++i)
#pragma unroll
        for (int j = 0; j < TN; ++j) {
          // Preserve two FP32 K16 chains, alternating within each K32 pair.
          if ((kk & 16) == 0)
            acc[i][j] = __builtin_amdgcn_wmma_f32_16x16x16_f16_w32(b[j], a[i],
                                                                   acc[i][j]);
          else
            high[i][j] = __builtin_amdgcn_wmma_f32_16x16x16_f16_w32(b[j], a[i],
                                                                    high[i][j]);
        }
    }
    if constexpr (NBUF == 1)
      __syncthreads();
    if (more) {  // NBUF 2: the other buffer was last read before the previous
                 // barrier
      const int sn = NBUF == 2 ? (s ^ 1) : 0;
#pragma unroll
      for (int i = 0; i < B_IT; ++i)
        if (bl[i] >= 0)
          *(HcDownVector4*)(Bs[sn] + bl[i]) = rb[i];
    }
    __syncthreads();
  }
  // lane holds output column m_base + (lane & 15) for token rows 2e + (lane >>
  // 4) of each 16-token fragment
  const int cm = lane & 15, cn = lane >> 4;
#pragma unroll
  for (int i = 0; i < TM; ++i) {
    const int m = m0 + wm * WTM + i * 16 + cm;
#pragma unroll
    for (int j = 0; j < TN; ++j) {
#pragma unroll
      for (int e = 0; e < 8; ++e) {
        const int t = t0 + wn * WTN + j * 16 + 2 * e + cn;
        if (t < T && m < M)
          D[(size_t)t * M + m] = acc[i][j][e] + high[i][j][e];
      }
    }
  }
}

}  // namespace

bool HcDownDirectWeightF16Gemm(const void* w, const __half* x, float* out,
                               std::size_t batch, std::size_t m, std::size_t k,
                               hipStream_t stream) {
  if (!w || !x || !out || batch < 96 || batch > 2048 || m != 320 || k != 10240)
    return false;
  hipLaunchKernelGGL((HcDownDirectWeightKernel<64, 32, 16, 16, 256, 1>),
                     dim3(5, (batch + 31) / 32), dim3(256), 0, stream,
                     static_cast<const std::uint16_t*>(w),
                     reinterpret_cast<const std::uint16_t*>(x), out, 320, 10240,
                     static_cast<int>(batch), 10240, 10240);
  return hipGetLastError() == hipSuccess;
}
