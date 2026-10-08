// SPDX-License-Identifier: MIT
// Literal retained1574 down; only renamed for the new component fixture.
template<WeightType kType, int BM, int BN, int BK, bool kPair = false,
         bool kPacked = false, bool kScaled = false>
__launch_bounds__(256) __global__ void RoutedQ2RegisterScatterControlKernel(
    const void* __restrict__ w,
    const std::conditional_t<kType == WeightType::kQ2_K && !kScaled, float,
                             __half>* __restrict__ x,
    const std::int32_t* __restrict__ tiles,
    const std::int32_t* __restrict__ pad_bounds,
    const std::int32_t* __restrict__ rows_in,
    const std::int32_t* __restrict__ rows_out,
    const float* __restrict__ swiglu_gate, float* __restrict__ out,
    __half* __restrict__ out_half, std::size_t m, std::size_t k,
    const void* __restrict__ w_up) {
  static_assert(BM == 128 || BM == 256, "eight waves, 16-row tiles");
  static_assert(!kPair || BM == 128);
  static_assert(BN % 16 == 0 && BN / 16 <= 8);
  static_assert(BK == 2, "one stage is one 32-byte Q4_K nibble group");
  constexpr int kTokTiles = BN / 16;
  constexpr int kWaveRowTiles = BM / 128;  // 16-row tiles per wave
  constexpr bool kQ5 = kType == WeightType::kQ5_1;
  constexpr bool kQ5K = kType == WeightType::kQ5_K;
  constexpr bool kQ8 = kType == WeightType::kQ8_0;
  constexpr bool kQ2 = kType == WeightType::kQ2_K;
  static_assert(kQ2 && kScaled && !kPair && !kPacked);
  constexpr bool kResidual = kQ2 && !kScaled;
  static_assert(!kScaled || (kQ2 && !kPacked && !kPair));
  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;
  constexpr bool kSigned = kQ8 || kIQ2;
  constexpr bool kKQuant = kType == WeightType::kQ4_K || kQ5K;
  // 16-byte code chunks per row and stage: Q4_K's nibble pair and Q5_1's
  // two nibble blocks are two, Q8_0's two byte blocks are four.
  constexpr int kChunks = (kSigned || kQ2) ? 2 * BK : BK;

  // LDS plan (bytes): the code plane holds BM rows x kChunks 16-byte chunks
  // with the chunks of nearby rows permuted so a fragment read (one row per
  // lane) covers all bank groups; the activation plane is
  // [kb][16-element quarter][token][16 B] so a fragment read is 256
  // contiguous bytes; the epilogue reuses it all.
  constexpr int kCodeBytes = BM * kChunks * 16;
  constexpr int kHighBytes = (kQ5 || kQ5K) ? BK * BM * 4 : 0;
  constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;
  // One slot of padding per activation quarter plane: the eight chunks of
  // a token then land on eight bank groups when they are written.
  constexpr int kActStride = BN + 1;
  constexpr int kActPlaneBytes = BK * 4 * kActStride * 16;
  constexpr int kActBytes = (kResidual ? 2 : 1) * kActPlaneBytes;
  // The epilogue transposes one 16x16 tile per wave through the same
  // bytes (8 KB), which the narrow tile's stages do not reach.
  constexpr int kStageBytes = kCodeBytes + kHighBytes + kScaleBytes + kActBytes;
  constexpr int kLdsBytes = kStageBytes > 8 * 1024 ? kStageBytes : 8 * 1024;
  __shared__ __attribute__((aligned(16))) std::uint8_t lds[kLdsBytes];
  auto* s_codes = reinterpret_cast<uint4*>(lds);
  auto* s_high = reinterpret_cast<std::uint32_t*>(lds + kCodeBytes);
  auto* s_scale =
      reinterpret_cast<std::uint32_t*>(lds + kCodeBytes + kHighBytes);
  auto* s_act =
      reinterpret_cast<uint4*>(lds + kCodeBytes + kHighBytes + kScaleBytes);

  const std::int32_t tile = tiles[blockIdx.y];
  const int expert = tile & 0xFFFF;
  const int t_local = (tile >> 16) * BN;
  const int bucket_begin = pad_bounds[expert];
  const int bucket_rows = pad_bounds[expert + 1] - bucket_begin;
  const int live_tok_tiles =
      std::min(kTokTiles, (bucket_rows - t_local + 15) / 16);
  const int num_kb = static_cast<int>(k / 32);
  const int m_i = static_cast<int>(m);
  const std::size_t row_bytes = RoutedF16RowBytes<kType>(k);
  const auto* w_expert = static_cast<const std::uint8_t*>(w) +
                         static_cast<std::size_t>(expert) * m * row_bytes;

  const int tid = static_cast<int>(threadIdx.x);
  const int wave_id = tid >> 5;
  const int lane_id = tid & 31;
  const int sub_lane = lane_id & 15;
  const int half_id = lane_id >> 4;
  constexpr int kRows = kPair ? BM / 2 : BM;
  const int r_block = static_cast<int>(blockIdx.x) * kRows;

  // Weight fetch: unit u of a thread is (row = tid / 2 + 128 u, chunk c =
  // tid % 2). Q4_K: the two 16-byte halves of one 32-byte nibble group (two
  // K blocks, low and high nibbles); Q5_1: one 24-byte K block each.
  const int f_c = tid & 1;
  const std::uint8_t* f_ptr[kWaveRowTiles];
  bool f_live[kWaveRowTiles];
  uint4 f_header[kWaveRowTiles];
#pragma unroll
  for (int u = 0; u < kWaveRowTiles; ++u) {
    const int r =
        r_block + (kPair ? (tid >> 1) % kRows : (tid >> 1) + (u * 128));
    f_live[u] = r < m_i;
    const std::uint8_t* weights = w_expert;
    if constexpr (kPair) {
      if ((tid >> 1) >= kRows) {
        weights = static_cast<const std::uint8_t*>(w_up) +
                  static_cast<std::size_t>(expert) * m * row_bytes;
      }
    }
    f_ptr[u] = weights +
               static_cast<std::size_t>(f_live[u] ? r : (m_i - 1)) * row_bytes;
    f_header[u] = make_uint4(0u, 0u, 0u, 0u);
  }
  // The next stage's weights and activations, fetched one stage ahead. The
  // (scale, bias) pair is derived from the raw header word only when the
  // stage is committed, so nothing waits on the loads before the compute.
  uint4 f_codes[kWaveRowTiles];
  uint2 f_iq2_group[kWaveRowTiles];
  __half f_iq2_d[kWaveRowTiles];
  // Paired gate/up tiles reuse the full quantized block over four stages.
  // Keep its remaining codes in registers alongside the cached header.
  uint4 code_cache[kWaveRowTiles][4];
  uint4 f_codes_hi[kWaveRowTiles];  ///< Q8_0: the block's second 16 codes
  uint4 f_qh[kWaveRowTiles][2];     ///< Q5_K: the superblock's high bits
  std::uint32_t f_high[kWaveRowTiles];
  std::uint32_t f_dm[kWaveRowTiles];  ///< Q5_1: d | m; Q8_0: d
  int f_sb32[kWaveRowTiles];          ///< Q4_K: the K block in its superblock
  constexpr int kActFetch = BN <= 64 ? 2 : 4;
  uint4 a_data[kActFetch];
  uint4 a_residual[kActFetch];

  // Activation fetch: BN tokens x (BK * 64) bytes per stage in 16-byte
  // chunks, eight per token; each thread fetches consecutive 256-chunk
  // strides, up to four for a 128-token tile.
  constexpr int kActChunks = BN * BK * 4;
  static_assert(kActChunks <= kActFetch * 256);
  using Activation = std::conditional_t<kResidual, float, __half>;
  const Activation* a_src[kActFetch];
  int a_slot[kActFetch];
#pragma unroll
  for (int i = 0; i < kActFetch; ++i) {
    const int chunk = tid + (i * 256);
    const int t = chunk / (BK * 4);
    const int sub = chunk % (BK * 4);
    const int c_row = t_local + t;
    const std::int32_t src = (chunk < kActChunks && c_row < bucket_rows)
                                 ? rows_in[bucket_begin + c_row]
                                 : -1;
    a_src[i] = src >= 0 ? x + (static_cast<std::size_t>(src) * k) + (sub * 8)
                        : nullptr;
    // Every K stage consumes only the live 16-row fragments. Keep
    // zero padding inside the last live fragment; wholly dead fragments
    // have no LDS reader. Decide this once, outside the stage loop.
    const bool store_live =
        chunk < kActChunks &&
        (!(kIQ2 && kPair && kTokTiles > 1) || t < live_tok_tiles * 16);
    // s_act[(kb * 4 + quarter) * kActStride + t]
    a_slot[i] = store_live ? (sub * kActStride) + t : -1;
  }

  const auto swizzle = [](int row, int c) {
    return (row * kChunks) +
           (c ^ (kChunks == 4 ? ((row >> 1) & 3) : ((row >> 2) & 1)));
  };

  const auto fetch_stage = [&](int kb0) {
#pragma unroll
    for (int u = 0; u < kWaveRowTiles; ++u) {
      if constexpr (kQ5) {
        const int kb = kb0 + f_c;
        const auto* words = reinterpret_cast<const uint2*>(f_ptr[u]) + (kb * 3);
        const uint2 w0 = words[0];
        const uint2 w1 = words[1];
        const uint2 w2 = words[2];
        f_codes[u] = make_uint4(w1.x, w1.y, w2.x, w2.y);
        f_high[u] = w0.y;
        f_dm[u] = w0.x;
      } else if constexpr (kIQ2) {
        const int sb32 = kb0 + f_c;
        const auto* block = f_ptr[u] + (sb32 / 8) * 66;
        // SPDX-License-Identifier: MIT
        // Keep only the original group/header live across current-stage WMMA.
        // No codebook/sign lookup or conversion waits on these loads here.
        __builtin_memcpy(&f_iq2_group[u], block + 2 + (sb32 % 8) * 8, 8);
        __builtin_memcpy(&f_iq2_d[u], block, 2);
      } else if constexpr (kQ2) {
        // Each Q2_K superblock stores 256 codes with independent affine
        // scales every 16 elements. The input's logical K may end halfway
        // through the last block; row storage remains padded to 256.
        const int sb32 = kb0 + f_c;
        const auto* blk = f_ptr[u] + ((sb32 / 8) * 84);
        const auto* codes = blk + 16 + ((sb32 % 8) / 4) * 32;
        __builtin_memcpy(&f_codes[u], codes, 16);
        __builtin_memcpy(&f_codes_hi[u], codes + 16, 16);
        __builtin_memcpy(&f_dm[u], blk + 80, 4);
        f_high[u] = blk[2 * (sb32 % 8)] |
                    (std::uint32_t(blk[2 * (sb32 % 8) + 1]) << 8U);
        const unsigned shift = 2U * unsigned(sb32 % 4);
        const auto unpack = [shift](uint4 v) {
          return make_uint4(
              (v.x >> shift) & 0x03030303U, (v.y >> shift) & 0x03030303U,
              (v.z >> shift) & 0x03030303U, (v.w >> shift) & 0x03030303U);
        };
        f_codes[u] = unpack(f_codes[u]);
        f_codes_hi[u] = unpack(f_codes_hi[u]);
      } else if constexpr (kQ8) {
        // block_q8_0 is 34 bytes, so the code loads are 2-byte aligned.
        const auto* blk = f_ptr[u] + ((kb0 + f_c) * 34);
        f_dm[u] = *reinterpret_cast<const std::uint16_t*>(blk);
        __builtin_memcpy(&f_codes[u], blk + 2, 16);
        __builtin_memcpy(&f_codes_hi[u], blk + 18, 16);
      } else {
        constexpr int kBlockChunks = kQ5K ? 11 : 9;
        constexpr int kCodeChunk = kQ5K ? 3 : 1;
        const int block = kb0 / 8;
        const auto* blk =
            reinterpret_cast<const uint4*>(f_ptr[u]) + (block * kBlockChunks);
        // The K sweep enters a new superblock every eight Q8-sized blocks.
        if (kb0 % 8 == 0) {
          f_header[u] = blk[0];
          if constexpr (kPair) {
#pragma unroll
            for (int group = 0; group < 4; ++group)
              code_cache[u][group] = blk[kCodeChunk + group * 2 + f_c];
          }
          if constexpr (kQ5K) {
            f_qh[u][0] = blk[1];
            f_qh[u][1] = blk[2];
          }
        }
        const int sb32 = (kb0 % 8) + f_c;
        if constexpr (kPair) {
          const int group = sb32 / 2;
          f_codes[u] = group == 0   ? code_cache[u][0]
                       : group == 1 ? code_cache[u][1]
                       : group == 2 ? code_cache[u][2]
                                    : code_cache[u][3];
        } else {
          f_codes[u] = blk[kCodeChunk + (sb32 / 2) * 2 + f_c];
        }
        f_sb32[u] = sb32;
        if constexpr (kQ5K) {
          // Bit sb32 of the 32 high-bit bytes, packed as the Q5_1 word.
          const std::uint32_t qh[8] = {f_qh[u][0].x, f_qh[u][0].y, f_qh[u][0].z,
                                       f_qh[u][0].w, f_qh[u][1].x, f_qh[u][1].y,
                                       f_qh[u][1].z, f_qh[u][1].w};
          std::uint32_t high = 0;
#pragma unroll
          for (int i = 0; i < 8; ++i) {
            high |= GatherBit(qh[i], sb32) << (4 * i);
          }
          f_high[u] = high;
        }
      }
    }
#pragma unroll
    for (int i = 0; i < kActFetch; ++i) {
      if constexpr (kResidual && kPacked) {
        // Eight existing 32-bit slots hold (half high, scaled half residual).
        // Read each slot once; extracting halves replaces repeated conversion
        // of the same F32 activation in every output-row block.
        const auto* packed = reinterpret_cast<const uint4*>(
            a_src[i] != nullptr ? a_src[i] + kb0 * 32 : nullptr);
        const uint4 a = packed ? packed[0] : make_uint4(0u, 0u, 0u, 0u);
        const uint4 b = packed ? packed[1] : make_uint4(0u, 0u, 0u, 0u);
        const auto high = [](uint4 v) {
          return make_uint2((v.x & 0xFFFFU) | (v.y << 16U),
                            (v.z & 0xFFFFU) | (v.w << 16U));
        };
        const auto low = [](uint4 v) {
          return make_uint2((v.x >> 16U) | (v.y & 0xFFFF0000U),
                            (v.z >> 16U) | (v.w & 0xFFFF0000U));
        };
        const uint2 ah = high(a), bh = high(b), al = low(a), bl = low(b);
        a_data[i] = make_uint4(ah.x, ah.y, bh.x, bh.y);
        a_residual[i] = make_uint4(al.x, al.y, bl.x, bl.y);
      } else if constexpr (kResidual) {
        __half hi[8], lo[8];
#pragma unroll
        for (int v = 0; v < 8; ++v) {
          const float value =
              a_src[i] != nullptr ? a_src[i][kb0 * 32 + v] : 0.0F;
          hi[v] = __float2half_rn(value);
          // Scale the residual to retain small/subnormal activations.
          lo[v] = __float2half_rn((value - __half2float(hi[v])) * 4096.0F);
        }
        __builtin_memcpy(&a_data[i], hi, 16);
        __builtin_memcpy(&a_residual[i], lo, 16);
      } else {
        a_data[i] = a_src[i] != nullptr
                        ? *reinterpret_cast<const uint4*>(a_src[i] + (kb0 * 32))
                        : make_uint4(0u, 0u, 0u, 0u);
      }
    }
  };

  const auto commit_stage = [&]() {
#pragma unroll
    for (int u = 0; u < kWaveRowTiles; ++u) {
      const int row = (tid >> 1) + (u * 128);
      std::uint32_t scale_bias = 0;
      if constexpr (kIQ2) {
        const uint2 group = f_iq2_group[u];
        const __half d = f_iq2_d[u];
        // SPDX-License-Identifier: MIT
        // Each lane retains its original ten-byte prefetch and scale owner.
        // Four lanes transpose decode ownership: each writes one eight-value
        // slice for each peer's group, preserving every compact LDS byte.
        const int part = lane_id & 3;
#pragma unroll
        for (int owner = 0; owner < 4; ++owner) {
          const int peer_lane = (lane_id & ~3) + owner;
          const int peer_tid = (tid & ~3) + owner;
          const std::uint32_t indices = __shfl(group.x, peer_lane, 32);
          const std::uint32_t signs = __shfl(group.y, peer_lane, 32);
          const unsigned code = (indices >> (8 * part)) & 255U;
          const unsigned sign = (signs >> (7 * part)) & 127U;
          const uint2 magnitude =
              reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          const uint2 decoded = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                           magnitude.y ^ (mask.y & 0x80808080U));
          const int peer_row = (peer_tid >> 1) + (u * 128);
          const int chunk = 2 * (peer_tid & 1) + (part >> 1);
          reinterpret_cast<uint2*>(s_codes + swizzle(peer_row, chunk))[part & 1] = decoded;
        }
        const float scale =
            __half2float(d) * float(2 * (group.y >> 28) + 1) * 0.125F;
        const std::uint32_t dm =
            __builtin_bit_cast(std::uint16_t, __float2half_rn(scale));
        scale_bias = f_live[u] ? dm : 0U;
      } else if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];
        s_codes[swizzle(row, (2 * f_c) + 1)] = f_codes_hi[u];
        scale_bias = f_live[u] ? f_dm[u] : 0U;  // half2 (d, 0)
      } else {
        s_codes[swizzle(row, f_c)] = f_codes[u];
      }
      if constexpr (kQ5K) {
        s_high[(f_c * BM) + row] = f_high[u];
      }
      if constexpr (kQ2) {
        const __half2 dm = __builtin_bit_cast(__half2, f_dm[u]);
#pragma unroll
        for (int part = 0; part < 2; ++part) {
          const unsigned sm = (f_high[u] >> (8 * part)) & 0xFFU;
          const float d = f_live[u] ? __low2float(dm) * float(sm & 15U) : 0.0F;
          const float b =
              f_live[u] ? -__high2float(dm) * float(sm >> 4U) : 0.0F;
          // Keep the affine in F32. Rounding its coefficients separately
          // to F16 amplifies cancellation in small routed outputs.
          auto* affine = reinterpret_cast<float*>(s_scale) +
                         2 * (((2 * f_c + part) * BM) + row);
          affine[0] = d;
          affine[1] = b;
        }
      } else if constexpr (kSigned) {
      } else if constexpr (kQ5) {
        s_high[(f_c * BM) + row] = f_high[u];
        const __half2 dm = __builtin_bit_cast(__half2, f_dm[u]);
        const float d = f_live[u] ? __low2float(dm) : 0.0F;
        const float mn = f_live[u] ? __high2float(dm) : 0.0F;
        scale_bias =
            __builtin_bit_cast(std::uint32_t, __floats2half2_rn(d, mn));
      } else {
        const int sb32 = f_sb32[u];
        std::uint32_t sc = 0;
        std::uint32_t mn = 0;
        if (sb32 < 4) {
          sc = HeaderByte(f_header[u], 4 + sb32) & 0x3FU;
          mn = HeaderByte(f_header[u], 8 + sb32) & 0x3FU;
        } else {
          sc = (HeaderByte(f_header[u], 8 + sb32) & 0x0FU) |
               ((HeaderByte(f_header[u], sb32) >> 6U) << 4U);
          mn = (HeaderByte(f_header[u], 8 + sb32) >> 4U) |
               ((HeaderByte(f_header[u], 4 + sb32) >> 6U) << 4U);
        }
        const __half2 dm = __builtin_bit_cast(__half2, f_header[u].x);
        const float scale =
            f_live[u] ? __low2float(dm) * static_cast<float>(sc) : 0.0F;
        const float offset =
            f_live[u] ? __high2float(dm) * static_cast<float>(mn) : 0.0F;
        scale_bias = __builtin_bit_cast(std::uint32_t,
                                        __floats2half2_rn(scale, -offset));
      }
      if constexpr (!kQ2)
        s_scale[(f_c * BM) + row] = scale_bias;
    }
#pragma unroll
    for (int i = 0; i < kActFetch; ++i) {
      if (a_slot[i] >= 0) {
        s_act[a_slot[i]] = a_data[i];
        if constexpr (kResidual)
          s_act[kActPlaneBytes / 16 + a_slot[i]] = a_residual[i];
      }
    }
  };

  v8f acc[kWaveRowTiles][kTokTiles];
  v8f acc_residual[kResidual ? kWaveRowTiles : 1][kResidual ? kTokTiles : 1];
#pragma unroll
  for (int u = 0; u < kWaveRowTiles; ++u) {
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
      acc[u][j] = v8f{0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F};
      if constexpr (kResidual)
        acc_residual[u][j] = acc[u][j];
    }
  }

  const __half2 magic = __floats2half2_rn(kSigned ? -1152.0F : -1024.0F,
                                          kSigned ? -1152.0F : -1024.0F);
  const auto compute_stage = [&]() {
    uint4 raw[kWaveRowTiles][BK];
    if constexpr (!kSigned && !kQ2) {
#pragma unroll
      for (int u = 0; u < kWaveRowTiles; ++u) {
        const int row = (wave_id * 16) + (u * 128) + sub_lane;
#pragma unroll
        for (int c = 0; c < BK; ++c) {
          raw[u][c] = s_codes[swizzle(row, c)];
        }
      }
    }
#pragma unroll
    for (int kb = 0; kb < BK; ++kb) {
      v16h a_lo[kWaveRowTiles];
      v16h a_hi[kWaveRowTiles];
#pragma unroll
      for (int u = 0; u < kWaveRowTiles; ++u) {
        const int row = (wave_id * 16) + (u * 128) + sub_lane;
        const __half2 sb =
            kQ2 ? __float2half2_rn(0.0F)
                : __builtin_bit_cast(__half2, s_scale[(kb * BM) + row]);
        const __half2 scale2 = __low2half2(sb);
        const __half2 bias2 = __high2half2(sb);
        std::uint32_t nib[8];
        if constexpr (kSigned || kQ2) {
          // Q8_0: the block's 32 signed bytes are chunks 2 kb and 2 kb + 1;
          // flipping the sign bit carries q + 128, which the 1152 magic
          // takes back out.
          const uint4 c0 = s_codes[swizzle(row, 2 * kb)];
          const uint4 c1 = s_codes[swizzle(row, (2 * kb) + 1)];
          const std::uint32_t words[8] = {c0.x, c0.y, c0.z, c0.w,
                                          c1.x, c1.y, c1.z, c1.w};
#pragma unroll
          for (int i = 0; i < 8; ++i) {
            nib[i] = (kSigned && !kIQ2) ? words[i] ^ 0x80808080U : words[i];
          }
        } else if constexpr (kQ5) {
          // Q5_1: K block kb's 16 bytes are chunk kb; elements 0-15 take
          // the low nibbles, 16-31 the high, plus bit j of the high-bit
          // word.
          const uint4 r = raw[u][kb];
          const std::uint32_t high = s_high[(kb * BM) + row];
          const std::uint32_t words[4] = {r.x, r.y, r.z, r.w};
#pragma unroll
          for (int i = 0; i < 4; ++i) {
            nib[i] = (words[i] & 0x0F0F0F0FU) |
                     SpreadHighBits((high >> (4 * i)) & 0xFU);
            nib[4 + i] = ((words[i] >> 4U) & 0x0F0F0F0FU) |
                         SpreadHighBits((high >> (16 + 4 * i)) & 0xFU);
          }
        } else {
          // Q4_K / Q5_K: elements 0-15 of K block kb0 + kb are the low
          // (kb = 0) or high (kb = 1) nibbles of chunk 0, elements 16-31
          // of chunk 1; Q5_K adds bit j of the staged high-bit word.
          const unsigned shift = 4U * static_cast<unsigned>(kb);
          const std::uint32_t words[8] = {raw[u][0].x, raw[u][0].y, raw[u][0].z,
                                          raw[u][0].w, raw[u][1].x, raw[u][1].y,
                                          raw[u][1].z, raw[u][1].w};
          const std::uint32_t high = kQ5K ? s_high[(kb * BM) + row] : 0U;
#pragma unroll
          for (int i = 0; i < 8; ++i) {
            nib[i] = (words[i] >> shift) & 0x0F0F0F0FU;
            if constexpr (kQ5K) {
              nib[i] |= SpreadHighBits((high >> (4 * i)) & 0xFU);
            }
          }
        }
        __half2 h[16];
        uint2 palette[kQ2 && (kPacked || kScaled) ? 2 : 1];
        if constexpr (kQ2 && (kPacked || kScaled)) {
          // A sixteen-element affine group has only four possible weights.
          // Preserve each F32 FMA and F16 rounding, then select its exact
          // half bits instead of repeating the affine for every element.
#pragma unroll
          for (int part = 0; part < 2; ++part) {
            const auto* affine = reinterpret_cast<const float*>(s_scale) +
                                 2 * (((2 * kb + part) * BM) + row);
            const float d = affine[0], bias = affine[1];
            palette[part] = make_uint2(
                __builtin_bit_cast(std::uint32_t,
                                   __floats2half2_rn(fmaf(0.0F, d, bias),
                                                     fmaf(1.0F, d, bias))),
                __builtin_bit_cast(std::uint32_t,
                                   __floats2half2_rn(fmaf(2.0F, d, bias),
                                                     fmaf(3.0F, d, bias))));
          }
        }
#pragma unroll
        for (int i = 0; i < 8; ++i) {
          if constexpr (kQ2 && (kPacked || kScaled)) {
            const uint2 values = palette[i / 4];
            // Duplicate each two-bit code into the two byte selectors for
            // its half; perm indices 0..3 read the second source word.
            const auto lo =
                (__builtin_amdgcn_perm(nib[i], nib[i], 0x01010000U) << 1U) |
                0x01000100U;
            const auto hi =
                (__builtin_amdgcn_perm(nib[i], nib[i], 0x03030202U) << 1U) |
                0x01000100U;
            h[2 * i] = __builtin_bit_cast(
                __half2, __builtin_amdgcn_perm(values.y, values.x, lo));
            h[2 * i + 1] = __builtin_bit_cast(
                __half2, __builtin_amdgcn_perm(values.y, values.x, hi));
          } else if constexpr (kQ2) {
            const auto* affine = reinterpret_cast<const float*>(s_scale) +
                                 2 * (((2 * kb + (i / 4)) * BM) + row);
            const float d = affine[0], bias = affine[1];
            h[2 * i] =
                __floats2half2_rn(fmaf(float(nib[i] & 3U), d, bias),
                                  fmaf(float((nib[i] >> 8U) & 3U), d, bias));
            h[2 * i + 1] =
                __floats2half2_rn(fmaf(float((nib[i] >> 16U) & 3U), d, bias),
                                  fmaf(float((nib[i] >> 24U) & 3U), d, bias));
          } else if constexpr (kIQ2) {
            Iq2HalfBytesToHalves(nib[i], scale2, bias2, h[2 * i], h[2 * i + 1]);
          } else {
            CodesToHalves(nib[i], magic, scale2, bias2, h[2 * i], h[2 * i + 1]);
          }
        }
        __builtin_memcpy(&a_lo[u], &h[0], 32);
        __builtin_memcpy(&a_hi[u], &h[8], 32);
      }
#pragma unroll
      for (int j = 0; j < kTokTiles; ++j) {
        if constexpr (kPair || ((kQ5 || kQ8 || kQ2) && BN >= 48)) {
          // Keep one token tile's LDS fragments live at a time. Hoisting
          // all eight tiles spills registers and defeats the wider tile's
          // reuse of each weight decode. This is a compiler barrier only.
          asm volatile("" ::: "memory");
        }
        // A short expert bucket has no output in the remaining token
        // tiles, so omit their WMMA work.
        if constexpr ((kPair || ((kQ5 || kQ8 || kQ2) && BN >= 48)) &&
                      kTokTiles > 1) {
          if (j >= live_tok_tiles)
            continue;
        }
        const uint4* frag =
            s_act + ((kb * 4) * kActStride) + (j * 16) + sub_lane;
        uint4 b[4];
#pragma unroll
        for (int q = 0; q < 4; ++q) {
          b[q] = frag[q * kActStride];
        }
        v16h b_lo;
        v16h b_hi;
        __builtin_memcpy(&b_lo, &b[0], 32);
        __builtin_memcpy(&b_hi, &b[2], 32);
#pragma unroll
        for (int u = 0; u < kWaveRowTiles; ++u) {
          acc[u][j] = Wmma(a_lo[u], b_lo, acc[u][j]);
          acc[u][j] = Wmma(a_hi[u], b_hi, acc[u][j]);
        }
        if constexpr (kResidual) {
#pragma unroll
          for (int q = 0; q < 4; ++q)
            b[q] = frag[kActPlaneBytes / 16 + q * kActStride];
          __builtin_memcpy(&b_lo, &b[0], 32);
          __builtin_memcpy(&b_hi, &b[2], 32);
#pragma unroll
          for (int u = 0; u < kWaveRowTiles; ++u) {
            acc_residual[u][j] = Wmma(a_lo[u], b_lo, acc_residual[u][j]);
            acc_residual[u][j] = Wmma(a_hi[u], b_hi, acc_residual[u][j]);
          }
        }
      }
    }
  };

  fetch_stage(0);
  for (int kb0 = 0; kb0 < num_kb; kb0 += BK) {
    commit_stage();
    __syncthreads();
    if (kb0 + BK < num_kb) {
      fetch_stage(kb0 + BK);
    }
    compute_stage();
    __syncthreads();
  }

  if constexpr (kResidual) {
#pragma unroll
    for (int u = 0; u < kWaveRowTiles; ++u)
#pragma unroll
      for (int j = 0; j < kTokTiles; ++j)
        acc[u][j] += acc_residual[u][j] * (1.0F / 4096.0F);
  }

  if constexpr (kPair) {
    // Four waves compute gate rows and four compute the matching up rows.
    // Pair them in the existing LDS allocation, keeping the K accumulation
    // order and avoiding the gate's F32 write/read between projections.
    // Two padding floats keep the accumulator scatter off repeated banks.
    constexpr unsigned stride = 18;
    constexpr unsigned plane = 16 * stride;
    static_assert(8 * plane * sizeof(float) <= kLdsBytes);
    float* base = reinterpret_cast<float*>(lds);
    float* scratch = base + wave_id * plane;
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll
      for (int l = 0; l < 8; ++l) {
        scratch[sub_lane * stride + 2 * l + half_id] = acc[0][j][l];
      }
      __syncthreads();
#pragma unroll
      for (int unit = 0; unit < 2; ++unit) {
        const int flat = (unit * 256 + tid) * 2;
        const int t = t_local + j * 16 + flat / kRows;
        const int r = flat % kRows;
        if (t < bucket_rows && r_block + r < m_i) {
          const std::int32_t dst = rows_out[bucket_begin + t];
          if (dst >= 0) {
            const int idx = (r / 16) * plane + (flat / kRows) * stride + r % 16;
            // Preserve the separate projection epilogue's F32 evaluation
            // order before narrowing. Fast-math can otherwise regroup the
            // products and change an F16 rounding tie.
            __half values[2];
            float wide_values[2];
            std::uint32_t packed_values[2];
#pragma unroll
            for (int v = 0; v < 2; ++v) {
              float product = base[idx + v + 4 * plane] * base[idx + v];
              asm volatile("" : "+v"(product));
              float value = product * SigmoidF(base[idx + v]);
              asm volatile("" : "+v"(value));
              values[v] = __float2half(value);
              if constexpr (kIQ2 && kPacked) {
                const __half residual = __float2half_rn(
                    (value - __half2float(values[v])) * 4096.0F);
                packed_values[v] = __builtin_bit_cast(
                    std::uint32_t, __halves2half2(values[v], residual));
              } else if constexpr (kIQ2) {
                wide_values[v] = value;
              }
            }
            const auto offset = static_cast<std::size_t>(dst) * m + r_block + r;
            if constexpr (kIQ2 && kPacked) {
              auto* packed_out = reinterpret_cast<std::uint32_t*>(out);
              if (m % 2 == 0 && r_block + r + 1 < m_i)
                *reinterpret_cast<uint2*>(packed_out + offset) =
                    make_uint2(packed_values[0], packed_values[1]);
              else {
                packed_out[offset] = packed_values[0];
                if (r_block + r + 1 < m_i)
                  packed_out[offset + 1] = packed_values[1];
              }
            } else if constexpr (kIQ2) {
              if (m % 2 == 0 && r_block + r + 1 < m_i)
                *reinterpret_cast<float2*>(out + offset) =
                    make_float2(wide_values[0], wide_values[1]);
              else {
                out[offset] = wide_values[0];
                if (r_block + r + 1 < m_i)
                  out[offset + 1] = wide_values[1];
              }
            } else if (m % 2 == 0 && r_block + r + 1 < m_i) {
              *reinterpret_cast<__half2*>(out_half + offset) =
                  __halves2half2(values[0], values[1]);
            } else {
              out_half[offset] = values[0];
              if (r_block + r + 1 < m_i)
                out_half[offset + 1] = values[1];
            }
          }
        }
      }
      __syncthreads();
    }
    return;
  }

  // One wave writes a complete 128-byte line of F16 output. Padding the
  // shared row by two floats also makes the accumulator scatter conflict-free.
  // Narrow buckets keep the lighter wave-local epilogue below.
  if constexpr (BN >= 48) {
    static_assert(kLdsBytes >= 16 * (BM + 2) * sizeof(float));
    if (out_half != nullptr) {
      constexpr unsigned stride = BM + 2;
      float* scratch = reinterpret_cast<float*>(lds);
#pragma unroll
      for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll
        for (int u = 0; u < kWaveRowTiles; ++u) {
#pragma unroll
          for (int l = 0; l < 8; ++l)
            scratch[sub_lane * stride + wave_id * 16 + u * 128 + 2 * l +
                    half_id] = acc[u][j][l];
        }
        __syncthreads();
#pragma unroll
        for (int round = 0; round < 16 * BM / (256 * 2); ++round) {
          const unsigned flat = (round * 256 + tid) * 2;
          const unsigned tr = flat / BM, row = flat % BM;
          const unsigned t = t_local + j * 16 + tr, r = r_block + row;
          if (t < unsigned(bucket_rows) && r < m) {
            const int dst = rows_out[bucket_begin + t];
            if (dst >= 0) {
              float2 v =
                  *reinterpret_cast<const float2*>(scratch + tr * stride + row);
              const size_t o = size_t(dst) * m + r;
              if (swiglu_gate != nullptr) {
                v.x *= SiluF(swiglu_gate[o]);
                if (r + 1 < m)
                  v.y *= SiluF(swiglu_gate[o + 1]);
              }
              if (m % 2 == 0 && r + 1 < m)
                *reinterpret_cast<__half2*>(out_half + o) =
                    __floats2half2_rn(v.x, v.y);
              else {
                out_half[o] = __float2half(v.x);
                if (r + 1 < m)
                  out_half[o + 1] = __float2half(v.y);
              }
            }
          }
        }
        __syncthreads();
      }
      return;
    }
  }
  if (out_half == nullptr) {
    // Each original accumulator owner restores and rounds its eight values
    // using one slot scale. Transpose the already-rounded half bytes through
    // wave-private scratch, then issue one aligned word per adjacent pair.
    // No block-wide synchronization or additional rounding is introduced.
    __half* half_tile = reinterpret_cast<__half*>(lds) + wave_id * 256;
    __half* dst_half = reinterpret_cast<__half*>(out);
#pragma unroll
    for (int u = 0; u < kWaveRowTiles; ++u) {
      const int r0 = r_block + wave_id * 16 + u * 128;
#pragma unroll
      for (int j = 0; j < kTokTiles; ++j) {
        const int t0 = t_local + j * 16;
        const int token = t0 + sub_lane;
        const int slot = token < bucket_rows ? rows_out[bucket_begin + token] : -1;
        if (slot >= 0) {
          const float inverse = static_cast<const float*>(w_up)[slot];
#pragma unroll
          for (int l = 0; l < 8; ++l) {
            float restored = acc[u][j][l] * inverse;
            asm("" : "+v"(restored));
            half_tile[sub_lane * 16 + 2 * l + half_id] = __float2half_rn(restored);
          }
        }
        __builtin_amdgcn_wave_barrier();
        if (m % 8 == 0 && reinterpret_cast<std::uintptr_t>(dst_half) % 16 == 0) {
          // Two lanes cover one complete token row of the 16x16 half tile.
          // Both addresses are 16-byte aligned; m and r are multiples of 8,
          // so r<m implies all eight output halves are valid.
          const int flat = lane_id * 8;
          const int t = t0 + (flat >> 4);
          const int r = r0 + (flat & 15);
          if (t < bucket_rows && r < m_i) {
            const int dst = rows_out[bucket_begin + t];
            if (dst >= 0) {
              const std::size_t o = std::size_t(dst) * m + std::size_t(r);
              *reinterpret_cast<uint4*>(dst_half + o) =
                  *reinterpret_cast<const uint4*>(half_tile + flat);
            }
          }
        } else {
  #pragma unroll
          for (int s = 0; s < 4; ++s) {
            const int flat = (s * 32 + lane_id) * 2;
            const int t = t0 + (flat >> 4);
            const int r = r0 + (flat & 15);
            if (t < bucket_rows && r < m_i) {
              const int dst = rows_out[bucket_begin + t];
              if (dst >= 0) {
                const std::size_t o = std::size_t(dst) * m + std::size_t(r);
                const __half2 packed = *reinterpret_cast<const __half2*>(half_tile + flat);
                if (m % 2 == 0 && r + 1 < m_i) {
                  *reinterpret_cast<__half2*>(dst_half + o) = packed;
                } else {
                  dst_half[o] = __low2half(packed);
                  if (r + 1 < m_i)
                    dst_half[o + 1] = __high2half(packed);
                }
              }
            }
          }
        }
        __builtin_amdgcn_wave_barrier();
      }
    }
    return;
  }

  // Transpose each 16x16 tile through LDS, then scatter the 16 rows of each
  // token to its output row.
  float* tile_scratch = reinterpret_cast<float*>(lds) + (wave_id * 256);
#pragma unroll
  for (int u = 0; u < kWaveRowTiles; ++u) {
    const int r0 = r_block + (wave_id * 16) + (u * 128);
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll
      for (int l = 0; l < 8; ++l) {
        tile_scratch[(sub_lane * 16) + (2 * l) + half_id] = acc[u][j][l];
      }
      __builtin_amdgcn_wave_barrier();
      const int t0 = t_local + (j * 16);
#pragma unroll
      for (int s = 0; s < 8; ++s) {
        const int flat = (s * 32) + lane_id;
        const int t = t0 + (flat >> 4);
        const int r = r0 + (flat & 15);
        if (t < bucket_rows && r < m_i) {
          const std::int32_t dst = rows_out[bucket_begin + t];
          if (dst >= 0) {
            const std::size_t o = (static_cast<std::size_t>(dst) * m) +
                                  static_cast<std::size_t>(r);
            float v = tile_scratch[flat];
            if (out_half != nullptr) {
              out_half[o] = __float2half(
                  swiglu_gate != nullptr ? v * SiluF(swiglu_gate[o]) : v);
            } else {
              // Preserve the original F32 inverse-scale product,
              // then introduce one explicit storage rounding.
              float restored = v * static_cast<const float*>(w_up)[dst];
              asm("" : "+v"(restored));
              reinterpret_cast<__half*>(out)[o] = __float2half_rn(restored);
            }
          }
        }
      }
      __builtin_amdgcn_wave_barrier();
    }
  }
}

