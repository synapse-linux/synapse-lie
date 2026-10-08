// SPDX-License-Identifier: MIT
// Derived from independently pinned Gufo MMVQ; original vendor notices apply.
// Only row grouping changes; each lane dot and wave reduction stay ordered.
typedef float (*vec_dot_q_hip_t)(const void* __restrict__ vbq,
                                 const block_q8_1* __restrict__ bq8_1,
                                 const int& kbx, const int& iqs);

static constexpr __device__ vec_dot_q_hip_t get_vec_dot_q_hip(ggml_type type) {
  switch (type) {
    case GGML_TYPE_Q5_1:
      return vec_dot_q5_1_q8_1;
    case GGML_TYPE_Q8_0:
      return vec_dot_q8_0_q8_1;
    case GGML_TYPE_Q4_K:
      return vec_dot_q4_K_q8_1;
    case GGML_TYPE_Q5_K:
      return vec_dot_q5_K_q8_1;
    case GGML_TYPE_IQ2_XXS:
      return vec_dot_iq2_xxs_q8_1;
    case GGML_TYPE_Q2_K:
      return vec_dot_q2_K_q8_1;
    default:
      return nullptr;
  }
}

static constexpr __host__ __device__ int get_vdr_mmvq(ggml_type type) {
  switch (type) {
    case GGML_TYPE_Q5_1:
      return VDR_Q5_1_Q8_1_MMVQ;
    case GGML_TYPE_Q8_0:
      return VDR_Q8_0_Q8_1_MMVQ;
    case GGML_TYPE_Q4_K:
      return VDR_Q4_K_Q8_1_MMVQ;
    case GGML_TYPE_Q5_K:
      return VDR_Q5_K_Q8_1_MMVQ;
    case GGML_TYPE_IQ2_XXS:
      return VDR_IQ2_XXS_Q8_1_MMVQ;
    case GGML_TYPE_Q2_K:
      return VDR_Q2_K_Q8_1_MMVQ;
    default:
      return 1;
  }
}

template<ggml_type type, int c_rows_per_block, bool gated = false>
__launch_bounds__(mmvq_moe_max_batch(type) * (gated ? 64 : 32),
                  1) static __global__
    void Q2DownRowsKernel(const void* __restrict__ weights,
                          const void* __restrict__ vy,
                          const int32_t* __restrict__ ids,
                          float* __restrict__ dst, const uint32_t ncols_x,
                          const uint32_t nrows_x, const uint32_t stride_row_x,
                          const uint32_t stride_col_y,
                          const uint32_t stride_col_dst,
                          const uint32_t stride_channel_x,
                          const uint32_t stride_channel_dst,
                          const uint32_t ncols_dst, const uint32_t ids_stride,
                          const void* __restrict__ up_weights = nullptr) {
  constexpr int qk = ggml_hip_type_traits<type>::qk;
  constexpr int qi = ggml_hip_type_traits<type>::qi;
  constexpr int vdr = get_vdr_mmvq(type);
  constexpr int warp_size = 32;

  constexpr vec_dot_q_hip_t vec_dot_q_hip = get_vec_dot_q_hip(type);

  const bool is_up = gated && threadIdx.y != 0;
  const uint32_t token_idx = gated ? 0 : blockIdx.z * blockDim.y + threadIdx.y;
  const void* vx = is_up ? up_weights : weights;
  const int row0 = c_rows_per_block * blockIdx.x;
  const int blocks_per_row_x = ncols_x / qk;
  constexpr int blocks_per_iter = vdr * warp_size / qi;

  const uint32_t channel_dst = blockIdx.y;

  if (token_idx >= ncols_dst) {
    return;
  }

  // Inactive experts still write zero to every output row. The expert ID
  // and its validity are uniform within a wave.
  const int32_t id_raw = ids[channel_dst + token_idx * ids_stride];
  const bool invalid_id = id_raw < 0;
  const uint32_t channel_x = invalid_id ? 0u : (uint32_t)id_raw;

  const block_q8_1* y = ((const block_q8_1*)vy) + token_idx * stride_col_y;
  uint32_t row_offsets[c_rows_per_block];
#pragma unroll
  for (int i = 0; i < c_rows_per_block; ++i) {
    // A ragged tile reads the last valid row again for its unused lane.
    // Keep the bounds check out of the quantized dot-product loop.
    const uint32_t row = min(uint32_t(row0 + i), nrows_x - 1);
    row_offsets[i] = channel_x * stride_channel_x + row * stride_row_x;
  }

  // partial sum for each thread
  float tmp[c_rows_per_block] = {0.0f};

  for (int kbx = threadIdx.x / (qi / vdr);
       !invalid_id && kbx < blocks_per_row_x; kbx += blocks_per_iter) {
    const int kby = kbx * (qk / QK8_1);
    const int kqs = vdr * (threadIdx.x % (qi / vdr));

#pragma unroll
    for (int i = 0; i < c_rows_per_block; ++i) {
      tmp[i] += vec_dot_q_hip(vx, &y[kby], row_offsets[i] + kbx, kqs);
    }
  }

  // Warp-level reduction only - no shared memory needed
#pragma unroll
  for (int i = 0; i < c_rows_per_block; ++i) {
    tmp[i] = warp_reduce_sum<warp_size>(tmp[i]);
  }

  if constexpr (gated) {
    // Separate waves preserve each projection's original dot-product
    // grouping. Combining two accumulators in one wave lets fast-math
    // reassociate their shared input scales.
    __shared__ float values[2][c_rows_per_block];
    if (threadIdx.x < c_rows_per_block) {
      const float value = tmp[threadIdx.x];
      values[is_up][threadIdx.x] = isfinite(value) ? value : 0.0f;
    }
    __syncthreads();
    if (!is_up && threadIdx.x < c_rows_per_block &&
        uint32_t(row0 + threadIdx.x) < nrows_x) {
      const float g = values[0][threadIdx.x];
      const float u = values[1][threadIdx.x];
      dst[channel_dst * stride_channel_dst + row0 + threadIdx.x] =
          (g * (1.0f / (1.0f + __expf(-g)))) * u;
    }
    return;
  }

  // Write results
  if (threadIdx.x < c_rows_per_block &&
      (c_rows_per_block == 1 || uint32_t(row0 + threadIdx.x) < nrows_x)) {
    const float value = tmp[threadIdx.x];
    dst[channel_dst * stride_channel_dst + token_idx * stride_col_dst + row0 +
        threadIdx.x] = isfinite(value) ? value : 0.0f;
  }
}
