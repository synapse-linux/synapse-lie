// SPDX-License-Identifier: MIT
// Private one-token Q5_0 decoder; no production dispatch or weight conversion.
template<bool has_gate>
__launch_bounds__(32, 1) static __global__ void mul_mat_vec_q5_dense(
    const void* __restrict__ weights, const void* __restrict__ gate,
    const block_q8_1* __restrict__ input, float* __restrict__ output,
    const uint32_t ncols_x, const uint32_t nrows_x) {
  constexpr int qi = QI5_0;
  constexpr int vdr = VDR_Q5_0_Q8_1_MMVQ;
  constexpr int blocks_per_iter = vdr * 32 / qi;
  const int lane = threadIdx.x;
  const int row = blockIdx.x;
  const int blocks_per_row = ncols_x / QK5_0;
  const int row_offset = row * blocks_per_row;
  const int kqs = vdr * (lane % (qi / vdr));
  float sum = 0.f;
  float gate_sum = 0.f;
  for (int kbx = lane / (qi / vdr); kbx < blocks_per_row;
       kbx += blocks_per_iter) {
    sum += vec_dot_q5_0_q8_1(weights, input + kbx, row_offset + kbx, kqs);
    if constexpr (has_gate) {
      gate_sum += vec_dot_q5_0_q8_1(gate, input + kbx,
                                    row_offset + kbx, kqs);
    }
  }
  sum = warp_reduce_sum<32>(sum);
  if constexpr (has_gate) gate_sum = warp_reduce_sum<32>(gate_sum);
  if (lane == 0) {
    float value = sum;
    if constexpr (has_gate) value *= ggml_hip_op_silu_single(gate_sum);
    output[row] = value;
  }
}
