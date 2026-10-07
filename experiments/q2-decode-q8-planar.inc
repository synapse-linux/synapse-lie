// SPDX-License-Identifier: MIT
// Gufo f783fedb Q8 dot/reduction, with losslessly separated codes and scales.
// Same 34 bytes per block; aligned code words replace two-byte-aligned loads.
__launch_bounds__(256) static __global__ void PackQ8PlanarKernel(
    const block_q8_0* __restrict__ source, int* __restrict__ codes,
    unsigned short* __restrict__ scales, unsigned blocks) {
  const unsigned block = blockIdx.x * blockDim.x + threadIdx.x;
  if (block >= blocks)
    return;
  scales[block] = __half_as_ushort(source[block].d);
#pragma unroll
  for (int word = 0; word < 8; ++word)
    codes[block * 8 + word] = get_int_b2(source[block].qs, word);
}

static __device__ __forceinline__ float DotQ8Planar(
    const int* __restrict__ codes, const unsigned short* __restrict__ scales,
    const block_q8_1* __restrict__ input, int block, int iqs) {
  int v[VDR_Q8_0_Q8_1_MMVQ], u[VDR_Q8_0_Q8_1_MMVQ];
#pragma unroll
  for (int i = 0; i < VDR_Q8_0_Q8_1_MMVQ; ++i) {
    v[i] = codes[block * 8 + iqs + i];
    u[i] = get_int_b4(input->qs, iqs + i);
  }
  return vec_dot_q8_0_q8_1_impl<float, VDR_Q8_0_Q8_1_MMVQ>(
      v, u, __ushort_as_half(scales[block]), __low2half(input->ds));
}

template<bool has_gate>
__launch_bounds__(32, 1) static __global__ void Q8PlanarDecodeKernel(
    const int* __restrict__ codes, const unsigned short* __restrict__ scales,
    const int* __restrict__ gate_codes,
    const unsigned short* __restrict__ gate_scales,
    const block_q8_1* __restrict__ input, float* __restrict__ output,
    unsigned columns) {
  constexpr int qi = QI8_0, vdr = VDR_Q8_0_Q8_1_MMVQ;
  constexpr int blocks_per_iter = vdr * 32 / qi;
  const int lane = threadIdx.x;
  const int blocks_per_row = columns / QK8_0;
  const int row_offset = blockIdx.x * blocks_per_row;
  const int kqs = vdr * (lane % (qi / vdr));
  float sum = 0, gate_sum = 0;
  for (int kb = lane / (qi / vdr); kb < blocks_per_row; kb += blocks_per_iter) {
    sum += DotQ8Planar(codes, scales, input + kb, row_offset + kb, kqs);
    if constexpr (has_gate)
      gate_sum += DotQ8Planar(gate_codes, gate_scales, input + kb,
                             row_offset + kb, kqs);
  }
  sum = warp_reduce_sum<32>(sum);
  if constexpr (has_gate)
    gate_sum = warp_reduce_sum<32>(gate_sum);
  if (lane == 0) {
    float value = sum;
    if constexpr (has_gate)
      value *= ggml_hip_op_silu_single(gate_sum);
    output[blockIdx.x] = value;
  }
}
