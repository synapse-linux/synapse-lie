// SPDX-License-Identifier: MIT
// Derived from the independently pinned MIT Gufo f783fedb provider and LIE's
// retained IQ2 fixed-bounds/whole-row scaled packing implementations.
// Compiler/component draft only: no production selector uses this kernel.
// One block owns up to 16 routed token rows and all 640 gate/up output columns.
__launch_bounds__(256) __global__ void RoutedIq2Whole640DraftKernel(
    const void* __restrict__ gate, const void* __restrict__ up,
    const __half* __restrict__ x, const std::int32_t* __restrict__ tiles,
    const std::int32_t* __restrict__ bounds,
    const std::int32_t* __restrict__ tokens,
    const std::int32_t* __restrict__ slots, __half* __restrict__ out,
    float* __restrict__ inverse) {
  constexpr unsigned kColumns = 640;
  constexpr unsigned kInput = 2560;
  constexpr unsigned kGroups = 10;
  constexpr unsigned kWeightRows = 128;
  constexpr unsigned kActStride = 17;
  constexpr unsigned kCodeBytes = kWeightRows * 4 * 16;
  constexpr unsigned kScaleBytes = 2 * kWeightRows * 4;
  constexpr unsigned kActBytes = 8 * kActStride * 16;
  constexpr unsigned kLdsBytes = kCodeBytes + kScaleBytes + kActBytes;
  constexpr unsigned kRowBytes = kInput / 256 * 66;
  __shared__ __attribute__((aligned(16))) unsigned char lds[kLdsBytes];
  auto* codes = reinterpret_cast<uint4*>(lds);
  auto* scales = reinterpret_cast<unsigned*>(lds + kCodeBytes);
  auto* activations = reinterpret_cast<uint4*>(lds + kCodeBytes + kScaleBytes);

  const unsigned tid = threadIdx.x;
  const unsigned lane = tid & 31;
  const unsigned wave = tid >> 5;
  const unsigned sub_lane = lane & 15;
  const unsigned half_id = lane >> 4;
  const unsigned descriptor = static_cast<unsigned>(tiles[blockIdx.x]);
  const unsigned expert = descriptor & 0xffffU;
  // Descriptors retain the parent's 64-token tail units. Only tails with
  // 1..16 live rows are eligible; no routing count or descriptor is rewritten.
  const unsigned first = (descriptor >> 16) * 64;
  const unsigned begin = static_cast<unsigned>(bounds[expert]);
  const unsigned count = static_cast<unsigned>(bounds[expert + 1]) - begin;
  if (first >= count || count - first > 16)
    return;
  const unsigned live = count - first;
  const unsigned owner_row = tid >> 1;
  const unsigned owner_k = tid & 1;
  const auto* weights =
      static_cast<const unsigned char*>(owner_row < 64 ? gate : up) +
      (static_cast<std::size_t>(expert) * kColumns + owner_row % 64) *
          kRowBytes;
  const unsigned act_token = tid / 8;
  const unsigned act_part = tid % 8;
  const int source_token =
      act_token < live ? tokens[begin + first + act_token] : -1;
  const __half* source =
      source_token >= 0
          ? x + static_cast<std::size_t>(source_token) * kInput + act_part * 8
          : nullptr;
  uint4 pending_activation;
  uint2 pending_codes;
  __half pending_scale;
  const auto fetch_activation = [&](unsigned kb) {
    if (tid < 128) {
      pending_activation =
          source ? *reinterpret_cast<const uint4*>(source + kb * 32)
                 : make_uint4(0U, 0U, 0U, 0U);
    }
  };
  const auto fetch_weight = [&](unsigned group, unsigned kb) {
    const unsigned k32 = kb + owner_k;
    const auto* block = weights + group * 64 * kRowBytes + (k32 / 8) * 66;
    __builtin_memcpy(&pending_codes, block + 2 + (k32 % 8) * 8, 8);
    __builtin_memcpy(&pending_scale, block, 2);
  };
  const auto swizzle = [](unsigned row, unsigned chunk) {
    return row * 4 + (chunk ^ ((row >> 1) & 3));
  };
  const auto commit_weight = [&]() {
    const unsigned part = lane & 3;
#pragma unroll
    for (unsigned owner = 0; owner < 4; ++owner) {
      const unsigned peer_lane = (lane & ~3U) + owner;
      const unsigned peer_tid = (tid & ~3U) + owner;
      const unsigned indices = __shfl(pending_codes.x, peer_lane, 32);
      const unsigned signs = __shfl(pending_codes.y, peer_lane, 32);
      const unsigned code = (indices >> (8 * part)) & 255U;
      const unsigned sign = (signs >> (7 * part)) & 127U;
      const uint2 magnitude =
          reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
      const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
      const uint2 decoded = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                       magnitude.y ^ (mask.y & 0x80808080U));
      const unsigned peer_row = peer_tid >> 1;
      const unsigned chunk = 2 * (peer_tid & 1) + (part >> 1);
      reinterpret_cast<uint2*>(codes + swizzle(peer_row, chunk))[part & 1] =
          decoded;
    }
    // Same rounded F32 scale product and F16 conversion as the parent.
    const float scale = __half2float(pending_scale) *
                        float(2 * (pending_codes.y >> 28) + 1) * .125F;
    scales[owner_k * kWeightRows + owner_row] =
        __builtin_bit_cast(unsigned short, __float2half_rn(scale));
  };

  // Name the ten accumulator vectors explicitly. An indexed array retained
  // private-memory accesses even after the compiler unrolled all ten groups.
  v8f acc0{}, acc1{}, acc2{}, acc3{}, acc4{};
  v8f acc5{}, acc6{}, acc7{}, acc8{}, acc9{};
  fetch_activation(0);
  fetch_weight(0, 0);
  for (unsigned kb0 = 0; kb0 < kInput / 32; kb0 += 2) {
    // Each input stage is published once and shared by all ten output groups.
    if (tid < 128)
      activations[act_part * kActStride + act_token] = pending_activation;
    const auto compute_group = [&](unsigned group, v8f& accumulator) {
      commit_weight();
      __syncthreads();
      if (group + 1 < kGroups) {
        fetch_weight(group + 1, kb0);
      } else if (kb0 + 2 < kInput / 32) {
        fetch_weight(0, kb0 + 2);
        fetch_activation(kb0 + 2);
      }
#pragma unroll
      for (unsigned kb = 0; kb < 2; ++kb) {
        const unsigned row = wave * 16 + sub_lane;
        const __half2 scale =
            __builtin_bit_cast(__half2, scales[kb * kWeightRows + row]);
        const uint4 c0 = codes[swizzle(row, 2 * kb)];
        const uint4 c1 = codes[swizzle(row, 2 * kb + 1)];
        const unsigned words[8] = {c0.x, c0.y, c0.z, c0.w,
                                   c1.x, c1.y, c1.z, c1.w};
        __half2 decoded[16];
#pragma unroll
        for (unsigned i = 0; i < 8; ++i)
          Iq2HalfBytesToHalves(words[i], __low2half2(scale),
                               __high2half2(scale), decoded[2 * i],
                               decoded[2 * i + 1]);
        v16h a_lo, a_hi, b_lo, b_hi;
        __builtin_memcpy(&a_lo, &decoded[0], 32);
        __builtin_memcpy(&a_hi, &decoded[8], 32);
        const auto* fragment = activations + kb * 4 * kActStride + sub_lane;
        uint4 b[4];
#pragma unroll
        for (unsigned i = 0; i < 4; ++i)
          b[i] = fragment[i * kActStride];
        __builtin_memcpy(&b_lo, &b[0], 32);
        __builtin_memcpy(&b_hi, &b[2], 32);
        // K16 fragments are accumulated in the parent's original order.
        accumulator = Wmma(a_lo, b_lo, accumulator);
        accumulator = Wmma(a_hi, b_hi, accumulator);
      }
      // Bound register live ranges across the unrolled output groups.
      // This is a compiler scheduling fence, not a device synchronization.
      __builtin_amdgcn_sched_barrier(0);
      __syncthreads();
    };
    compute_group(0, acc0);
    compute_group(1, acc1);
    compute_group(2, acc2);
    compute_group(3, acc3);
    compute_group(4, acc4);
    compute_group(5, acc5);
    compute_group(6, acc6);
    compute_group(7, acc7);
    compute_group(8, acc8);
    compute_group(9, acc9);
  }

  constexpr unsigned kStride = 18;
  constexpr unsigned kPlane = 16 * kStride;
  static_assert(8 * kPlane * sizeof(float) <= kLdsBytes);
  auto* scratch = reinterpret_cast<float*>(lds);
  float2 values[2][kGroups];
  const auto finish_group = [&](unsigned group, v8f accumulator) {
#pragma unroll
    for (unsigned i = 0; i < 8; ++i)
      scratch[wave * kPlane + sub_lane * kStride + 2 * i + half_id] =
          accumulator[i];
    __syncthreads();
#pragma unroll
    for (unsigned unit = 0; unit < 2; ++unit) {
      const unsigned token = wave + unit * 8;
      const unsigned column = lane * 2;
      const unsigned index =
          column / 16 * kPlane + token * kStride + column % 16;
      float output[2];
#pragma unroll
      for (unsigned i = 0; i < 2; ++i) {
        float product = scratch[index + i + 4 * kPlane] * scratch[index + i];
        asm volatile("" : "+v"(product));
        float value = product * SigmoidF(scratch[index + i]);
        asm volatile("" : "+v"(value));
        output[i] = value;
      }
      values[unit][group] = make_float2(output[0], output[1]);
    }
    __builtin_amdgcn_sched_barrier(0);
    __syncthreads();
  };
  finish_group(0, acc0);
  finish_group(1, acc1);
  finish_group(2, acc2);
  finish_group(3, acc3);
  finish_group(4, acc4);
  finish_group(5, acc5);
  finish_group(6, acc6);
  finish_group(7, acc7);
  finish_group(8, acc8);
  finish_group(9, acc9);

#pragma unroll
  for (unsigned unit = 0; unit < 2; ++unit) {
    const unsigned token = wave + unit * 8;
    // Whole waves own rows. All block barriers have completed before skipping.
    if (token >= live)
      continue;
    const int destination = slots[begin + first + token];
    if (destination < 0)
      continue;
    float maximum = 0.F;
#pragma unroll
    for (unsigned group = 0; group < kGroups; ++group) {
      maximum = fmaxf(maximum, fabsf(values[unit][group].x));
      maximum = fmaxf(maximum, fabsf(values[unit][group].y));
    }
    for (unsigned offset = 16; offset; offset >>= 1)
      maximum = fmaxf(maximum, __shfl_down(maximum, offset, 32));
    float multiplier = 1.F;
    if (lane == 0) {
      const unsigned bits = __builtin_bit_cast(unsigned, maximum);
      const int exponent = int((bits >> 23) & 255U) - 127;
      int shift = maximum == 0.F ? 0 : 13 - exponent;
      shift = shift < -120 ? -120 : shift > 120 ? 120 : shift;
      multiplier = __builtin_bit_cast(float, unsigned(127 + shift) << 23);
      inverse[destination] =
          __builtin_bit_cast(float, unsigned(127 - shift) << 23);
    }
    multiplier = __shfl(multiplier, 0, 32);
    auto* target = out + static_cast<std::size_t>(destination) * kColumns;
#pragma unroll
    for (unsigned group = 0; group < kGroups; ++group) {
      const unsigned column = group * 64 + lane * 2;
      const float2 value = values[unit][group];
      const __half2 packed =
          __floats2half2_rn(value.x * multiplier, value.y * multiplier);
      if (reinterpret_cast<std::uintptr_t>(target) % 4 == 0)
        *reinterpret_cast<__half2*>(target + column) = packed;
      else {
        target[column] = __low2half(packed);
        target[column + 1] = __high2half(packed);
      }
    }
  }
}
