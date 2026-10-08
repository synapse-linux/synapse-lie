// SPDX-License-Identifier: MIT
// Wave-local register transpose of the already-rounded sixteen-value rows.
// Each half-wave owns alternating output columns of the same sixteen tokens.
// Four word exchanges supply the opposite parity without an LDS round trip.
    if (m % 8 == 0 && reinterpret_cast<std::uintptr_t>(out) % 16 == 0) {
      auto* dst_half = reinterpret_cast<__half*>(out);
#pragma unroll
      for (int u = 0; u < kWaveRowTiles; ++u) {
        const int r0 = r_block + wave_id * 16 + u * 128;
#pragma unroll
        for (int j = 0; j < kTokTiles; ++j) {
          const int token = t_local + j * 16 + sub_lane;
          const int slot = token < bucket_rows ? rows_out[bucket_begin + token] : -1;
          std::uint32_t own[4] = {};
          if (slot >= 0) {
            const float inverse = static_cast<const float*>(w_up)[slot];
#pragma unroll
            for (int p = 0; p < 4; ++p) {
              float a = acc[u][j][2 * p] * inverse;
              float b = acc[u][j][2 * p + 1] * inverse;
              asm("" : "+v"(a), "+v"(b));
              const __half ha = __float2half_rn(a);
              const __half hb = __float2half_rn(b);
              own[p] = __builtin_bit_cast(std::uint32_t, __halves2half2(ha, hb));
            }
          }
          // All lanes execute the exchange, including poisoned/padded slots.
          // The original slot guard remains the only permission to store.
          std::uint32_t peer[4];
#pragma unroll
          for (int p = 0; p < 4; ++p) {
            peer[p] = __builtin_amdgcn_permlanex16(
                own[p], own[p], 0x76543210u, 0xfedcba98u, false, false);
          }
          const std::uint32_t even0 = half_id ? peer[2] : own[0];
          const std::uint32_t odd0 = half_id ? own[2] : peer[0];
          const std::uint32_t even1 = half_id ? peer[3] : own[1];
          const std::uint32_t odd1 = half_id ? own[3] : peer[1];
          const uint4 packed = make_uint4(
              (even0 & 0xffffu) | (odd0 << 16),
              (even0 >> 16) | (odd0 & 0xffff0000u),
              (even1 & 0xffffu) | (odd1 << 16),
              (even1 >> 16) | (odd1 & 0xffff0000u));
          const int row = r0 + half_id * 8;
          if (slot >= 0 && row < m_i) {
            const std::size_t o = std::size_t(slot) * m + std::size_t(row);
            *reinterpret_cast<uint4*>(dst_half + o) = packed;
          }
        }
      }
      return;
    }
