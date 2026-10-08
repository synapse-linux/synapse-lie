// SPDX-License-Identifier: MIT
// Derived from independently pinned Gufo, including its GDN DPP exchange.
// Only the one-token Q8 consumer is selected. No different dot products,
// scale contraction, persistent format, allocation or stream is introduced.
template<int mask>
__device__ __forceinline__ float Q8CompactXorAdd(float x) {
  const int peer = __builtin_amdgcn_update_dpp(
      0, __builtin_bit_cast(int, x), 0x160 | mask, 0xf, 0xf, false);
  return x + __builtin_bit_cast(float, peer);
}
__device__ __forceinline__ float Q8CompactSum(float x) {
  // All32 lanes are active here, after the optional tail reconverges.
  // Exchange opposite16-lane rows, then the original descending XOR tree.
  const unsigned bits = __builtin_bit_cast(unsigned, x);
  const unsigned peer = __builtin_amdgcn_permlanex16(
      bits, bits, 0x76543210u, 0xfedcba98u, false, false);
  x += __builtin_bit_cast(float, peer);
  x = Q8CompactXorAdd<8>(x);
  x = Q8CompactXorAdd<4>(x);
  x = Q8CompactXorAdd<2>(x);
  return Q8CompactXorAdd<1>(x);
}

template<bool has_gate>
__launch_bounds__(32, 1) static __global__
    void mul_mat_vec_q8_compact(const void* __restrict__ weights,
                        const void* __restrict__ gate,
                        const block_q8_1* __restrict__ input,
                        float* __restrict__ output, const uint32_t ncols_x,
                        const uint32_t nrows_x, const uint32_t stride_col_y,
                        const uint32_t valid_tokens = 1) {
  constexpr int ncols_dst = 1, token_waves = 1;
  constexpr bool ragged = false;
  constexpr int qi = QI8_0;
  constexpr int vdr = VDR_Q8_0_Q8_1_MMVQ;
  constexpr int blocks_per_iter = vdr * 32 / qi;
  const int lane = token_waves > 1 ? threadIdx.x % 32 : threadIdx.x;
  const int first_token = token_waves > 1 ? threadIdx.x / 32 * ncols_dst : 0;
  const int row = blockIdx.x;
  const int blocks_per_row = ncols_x / QK8_0;
  const int row_offset = row * blocks_per_row;
  const int kqs = vdr * (lane % (qi / vdr));
  float sum[ncols_dst] = {};
  float gate_sum[ncols_dst] = {};
  // Every lane has a valid block in the complete part. Only the final
  // partial group needs a per-lane bound; each lane retains its K order.
  const int full = blocks_per_row / blocks_per_iter * blocks_per_iter;
  const int lane_block = lane / (qi / vdr);
  for (int base = 0; base < full; base += blocks_per_iter) {
    const int kbx = base + lane_block;
#pragma unroll
    for (int j = 0; j < ncols_dst; ++j) {
      // The last wave may contain fewer than eight inputs. Its inactive
      // columns reuse a valid row; their results are never stored.
      const int token =
          ragged ? min(first_token + j, int(valid_tokens) - 1) : first_token + j;
      sum[j] += vec_dot_q8_0_q8_1(
          weights, input + token * stride_col_y + kbx,
          row_offset + kbx, kqs);
      if constexpr (has_gate) {
        gate_sum[j] += vec_dot_q8_0_q8_1(gate, input + j * stride_col_y + kbx,
                                         row_offset + kbx, kqs);
      }
    }
  }
  const int kbx = full + lane_block;
  if (kbx < blocks_per_row) {
#pragma unroll
    for (int j = 0; j < ncols_dst; ++j) {
      // The last wave may contain fewer than eight inputs. Its inactive
      // columns reuse a valid row; their results are never stored.
      const int token =
          ragged ? min(first_token + j, int(valid_tokens) - 1) : first_token + j;
      sum[j] += vec_dot_q8_0_q8_1(
          weights, input + token * stride_col_y + kbx,
          row_offset + kbx, kqs);
      if constexpr (has_gate) {
        gate_sum[j] += vec_dot_q8_0_q8_1(gate, input + j * stride_col_y + kbx,
                                         row_offset + kbx, kqs);
      }
    }
  }
#pragma unroll
  for (int j = 0; j < ncols_dst; ++j) {
    sum[j] = Q8CompactSum(sum[j]);
    if constexpr (has_gate)
      gate_sum[j] = Q8CompactSum(gate_sum[j]);
    if (lane == 0 && (token_waves == 1 || first_token + j < valid_tokens)) {
      float value = sum[j];
      if constexpr (has_gate)
        value *= ggml_hip_op_silu_single(gate_sum[j]);
      output[(first_token + j) * nrows_x + row] = value;
    }
  }
}

