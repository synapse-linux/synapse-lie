// SPDX-License-Identifier: MIT
// Derived from independently pinned official Gufo; compiler-only draft.
__launch_bounds__(256) __global__
    void GdnFullWindowDraftKernel(const float* conv_out, const float* scales,
                           const float* ab, float* state, float* raw,
                           std::uint32_t n_tokens, std::uint32_t k_heads,
                           std::uint32_t v_heads) {
  // A future selector must require n_tokens > 0 and n_tokens % 4 == 0.
  // Keep the original dimension, state ownership, window ring and arithmetic.
  constexpr int d = kGdnDim;
  constexpr int kKeysPerLane = 32;
  constexpr int kVec = kKeysPerLane / 4;
  constexpr int kLanesPerRow = d / kKeysPerLane;
  constexpr int kRowsPerWave = 32 / kLanesPerRow;
  constexpr int kRowsPerBlock = kRowsPerWave * 8;
  constexpr int kW = kGdnWindow;
  static_assert(kW * (d / 4) * 2 == 256, "one q or k float4 per thread");
  static_assert(kW * kRowsPerBlock == 256, "one v element per thread");
  static_assert(kW * 5 <= 256, "scales and decays per window");
  const int h = blockIdx.y;
  const int tid = threadIdx.x;
  const int lane = tid & 31;
  const int segment = lane % kLanesPerRow;
  const int row_group = lane / kLanesPerRow;
  const int row_local = (tid >> 5) * kRowsPerWave + row_group;
  const int row = blockIdx.x * kRowsPerBlock + row_local;
  const int kh = h % k_heads;
  const int vec0 = segment * kVec;
  const int channels = 2 * k_heads * d + v_heads * d;

  // Two window slots: q and k rows, the block's v rows, the three scales
  // and two decays per token.
  __shared__ float4 s_qk[2][2][kW][d / 4];
  __shared__ float s_v[2][kW][kRowsPerBlock];
  __shared__ float s_misc[2][kW][5];

  float* state_row = state + (static_cast<std::size_t>(h) * d + row) * d;
  auto* state4 = reinterpret_cast<float4*>(state_row);
  float4 s[kVec];
#pragma unroll
  for (int i = 0; i < kVec; ++i) {
    s[i] = state4[vec0 + i];
  }

  // Window loads: thread tid takes q (tid < 128) or k float4 (tid / 32 of
  // token (tid / 32) % kW ... laid out so a token's 128 floats are 32
  // consecutive threads), one v element and, for tid < 5 kW, one scale.
  const int qk_which = tid >> 7;      // 0: q, 1: k
  const int qk_tok = (tid >> 5) & 3;  // token in the window
  const int qk_vec = tid & 31;
  const int v_tok = tid >> 6;
  const int v_row = tid & 63;
  const int m_tok = tid / 5;
  const int m_idx = tid % 5;
  const float* qk_src =
      conv_out + (qk_which == 0 ? kh : k_heads + kh) * d + (qk_vec * 4);
  const float* v_src =
      conv_out + 2 * k_heads * d + h * d + blockIdx.x * kRowsPerBlock + v_row;
  const float* m_src =
      m_idx < 3 ? scales + kh * 3 + m_idx : ab + h * 2 + (m_idx - 3);
  const std::size_t m_stride = m_idx < 3 ? k_heads * 3 : v_heads * 2;

  // Three windows of loads in flight, as named registers (a ring array
  // lands in scratch).
  struct Window {
    float4 qk;
    float v;
    float m;
  };
  Window r0;
  Window r1;
  Window r2;
  const auto load_window = [&](int w, Window& r) {
    const int t_qk = (w * kW) + qk_tok;
    const int t_v = (w * kW) + v_tok;
    r.qk = *reinterpret_cast<const float4*>(
        qk_src + static_cast<std::size_t>(t_qk) * channels);
    r.v = v_src[static_cast<std::size_t>(t_v) * channels];
    if (tid < 5 * kW) {
      const int t_m = (w * kW) + m_tok;
      r.m = m_src[static_cast<std::size_t>(t_m) * m_stride];
    }
  };
  // A token's 32 float4 are stored [i][segment] so the four segments of
  // a row's lanes read adjacent 16-byte chunks (row-major, they were 128
  // bytes apart: a four-way bank conflict on every fragment).
  const int qk_slot = ((qk_vec % kVec) * kLanesPerRow) + (qk_vec / kVec);
  const auto commit_window = [&](const Window& r, int lds) {
    s_qk[lds][qk_which][qk_tok][qk_slot] = r.qk;
    s_v[lds][v_tok][v_row] = r.v;
    if (tid < 5 * kW) {
      s_misc[lds][m_tok][m_idx] = r.m;
    }
  };

  const int n_windows = static_cast<int>(n_tokens) / kW;
  load_window(0, r0);
  if (n_windows > 1) {
    load_window(1, r1);
  }
  if (n_windows > 2) {
    load_window(2, r2);
  }
  commit_window(r0, 0);
  __syncthreads();
  float* out_base = raw + h * d;
  // `cur` held window w (committed already) and takes window w + 3;
  // `next` holds window w + 1, committed after this window's tokens.
  const auto window = [&](int w, Window& cur, const Window& next) {
    if (w >= n_windows) {
      return;
    }
    const int lds = w & 1;
    if (w + kGdnWindowsAhead < n_windows) {
      load_window(w + kGdnWindowsAhead, cur);
    }
    constexpr int t_end = kW;
#pragma unroll
    for (int tl = 0; tl < t_end; ++tl) {
      const float4* q4 = s_qk[lds][0][tl];
      const float4* k4 = s_qk[lds][1][tl];
      const float decay = s_misc[lds][tl][3];
      float u = 0.0F;
      float p = 0.0F;
      float4 kc[kVec];
#pragma unroll
      for (int i = 0; i < kVec; ++i) {
        const float4 qv = q4[(i * kLanesPerRow) + segment];
        kc[i] = k4[(i * kLanesPerRow) + segment];
        s[i].x *= decay;
        s[i].y *= decay;
        s[i].z *= decay;
        s[i].w *= decay;
        u += s[i].x * kc[i].x + s[i].y * kc[i].y + s[i].z * kc[i].z +
             s[i].w * kc[i].w;
        p += s[i].x * qv.x + s[i].y * qv.y + s[i].z * qv.z + s[i].w * qv.w;
      }
      GdnRowReduce(u, p);
      const float inv_k = s_misc[lds][tl][0];
      const float q_scale = s_misc[lds][tl][1];
      const float delta =
          (s_v[lds][tl][row_local] - u * inv_k) * s_misc[lds][tl][4];
      if (segment == 0) {
        out_base[row] =
            p * q_scale + delta * inv_k * q_scale * s_misc[lds][tl][2];
      }
      const float update = delta * inv_k;
#pragma unroll
      for (int i = 0; i < kVec; ++i) {
        s[i].x += update * kc[i].x;
        s[i].y += update * kc[i].y;
        s[i].z += update * kc[i].z;
        s[i].w += update * kc[i].w;
      }
      out_base += v_heads * d;
    }
    // The other slot was last read one window ago (before the previous
    // barrier), so window w + 1 goes in without a second barrier.
    if (w + 1 < n_windows) {
      commit_window(next, lds ^ 1);
    }
    __syncthreads();
  };
  for (int w = 0; w < n_windows; w += kGdnWindowsAhead) {
    window(w, r0, r1);
    window(w + 1, r1, r2);
    window(w + 2, r2, r0);
  }
#pragma unroll
  for (int i = 0; i < kVec; ++i) {
    state4[vec0 + i] = s[i];
  }
}
