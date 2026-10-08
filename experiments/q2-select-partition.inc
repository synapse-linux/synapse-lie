// SPDX-License-Identifier: MIT
// Local selection body derived from independently fetched official Gufo
// f783fedb9bea2ec7de941f6da4e02f4a4596b29e, with the retained LIE histogram changes.
// The new two-stage ownership, compaction and merge below are first-party.
// No external engine source or binary was imported.
namespace gufo::models::qwen38_flash_next::rocm { namespace {
constexpr unsigned q2PartBlocks=4096, q2SelectBudget=512, q2SelectParts=9;
constexpr unsigned q2SelectSlots=q2SelectParts*q2SelectBudget;
__device__ __forceinline__ void Q2SelectLocal(unsigned* words,const unsigned* sc,
    unsigned complete,unsigned mask_words,unsigned max_blocks,unsigned budget) {
  __shared__ std::uint32_t candidates[4096];
  __shared__ std::uint32_t hist[256];
  __shared__ std::uint32_t candidate_count;
  __shared__ std::uint32_t wave_ties[kThreads / 32];
  __shared__ std::uint32_t state[3];  // threshold, remaining, bin count
  for (std::uint32_t w = threadIdx.x; w < mask_words; w += blockDim.x) {
    words[w] = complete <= budget ? 0xFFFFFFFFu : 0u;
  }
  if (complete <= budget) {
    return;
  }
  const std::uint32_t lane = threadIdx.x & 31u;
  const std::uint32_t wave = threadIdx.x >> 5;
  // Short rows already fit the original histogram cheaply.
  const bool windowed = complete >= 4096;
  std::uint32_t maximum = 0;
  if (windowed) {
    maximum = threadIdx.x < min(complete, kThreads) ? sc[threadIdx.x] : 0u;
#pragma unroll
    for (unsigned offset = 16; offset > 0; offset /= 2)
      maximum = max(maximum, __shfl_xor(maximum, offset));
    if (lane == 0)
      wave_ties[wave] = maximum;
    __syncthreads();
    for (unsigned w = 0; w < kThreads / 32; ++w)
      maximum = max(maximum, wave_ties[w]);
  }
  // Finer bins reduce contention among scores with similar exponents.
  // The sample only places the window: clipped tails are still counted.
  unsigned prefix_bits = windowed ? 14 : 20;
  unsigned base =
      (maximum >> prefix_bits) > 2047 ? (maximum >> prefix_bits) - 2047 : 0;
  if (threadIdx.x == 0)
    candidate_count = 0;
  for (unsigned attempt = 0; attempt < 2; ++attempt) {
    for (unsigned i = threadIdx.x; i < 4096; i += blockDim.x)
      candidates[i] = 0;
    __syncthreads();
    const auto bin = [&](std::uint32_t value) {
      const auto key = value >> prefix_bits;
      return key > base ? min(key - base, 4095u) : 0u;
    };
    // Aligned production rows use four adjacent scores per lane.
    for (unsigned b = threadIdx.x * 4; b < complete; b += blockDim.x * 4) {
      if (b + 3 < complete && max_blocks % 4 == 0) {
        const uint4 v = *reinterpret_cast<const uint4*>(sc + b);
        atomicAdd(&candidates[bin(v.x)], 1u);
        atomicAdd(&candidates[bin(v.y)], 1u);
        atomicAdd(&candidates[bin(v.z)], 1u);
        atomicAdd(&candidates[bin(v.w)], 1u);
      } else {
        for (unsigned j = 0; j < 4 && b + j < complete; ++j)
          atomicAdd(&candidates[bin(sc[b + j])], 1u);
      }
    }
    __syncthreads();
    FindHistogramThreshold<16>(candidates, budget, wave_ties, state);
    if (!windowed || attempt != 0 ||
        (state[0] != 4095 && (state[0] != 0 || base == 0)))
      break;
    // A clipped threshold needs a histogram over the full 32-bit keys.
    prefix_bits = 20;
    base = 0;
  }
  std::uint32_t prefix = (base + state[0]) << prefix_bits;
  std::uint32_t remaining = state[1];
  // Reuse the first histogram as a bounded candidate list. If its bin is
  // larger, later radix passes read the original scores instead.
  const bool compact = state[2] <= 4096 && remaining != state[2];
  const std::uint32_t input_count = compact ? state[2] : complete;
  if (compact) {
    for (std::uint32_t b = threadIdx.x; b < complete; b += blockDim.x) {
      std::uint32_t v = sc[b];
      if ((v & (~0u << prefix_bits)) == prefix)
        candidates[atomicAdd(&candidate_count, 1u)] = v;
    }
    __syncthreads();
  }
  // A whole bin can be accepted as soon as its count fills the remaining
  // budget. Otherwise refine the remaining bits, at most eight per pass.
  for (unsigned bits = prefix_bits; bits > 0 && remaining != state[2];) {
    const unsigned digit_bits = min(bits, 8u);
    const std::uint32_t prefix_mask = ~0u << bits;
    bits -= digit_bits;
    const std::uint32_t radix_mask = (1u << digit_bits) - 1;
    hist[threadIdx.x] = 0;
    __syncthreads();
    for (std::uint32_t b = threadIdx.x; b < input_count; b += blockDim.x) {
      const std::uint32_t v = compact ? candidates[b] : sc[b];
      if ((v & prefix_mask) == prefix)
        atomicAdd(&hist[(v >> bits) & radix_mask], 1u);
    }
    __syncthreads();
    FindHistogramThreshold<1>(hist, remaining, wave_ties, state);
    prefix |= state[0] << bits;
    remaining = state[1];
    __syncthreads();
  }
  const std::uint32_t threshold = prefix;
  // Blocks strictly above the threshold are in; the first `remaining` ties
  // in index order fill the budget. Ties are ranked with a wave ballot and
  // a per-chunk scan over the eight waves.
  if (remaining == state[2]) {
    // Every threshold tie fits (in particular, a unique threshold). No
    // prefix scan is needed: each wave writes one complete mask word.
    for (std::uint32_t chunk = 0; chunk < complete; chunk += blockDim.x) {
      const std::uint32_t b = chunk + threadIdx.x;
      const bool selected = b < complete && sc[b] >= threshold;
      const auto bits = static_cast<std::uint32_t>(__ballot(selected));
      if (lane == 0 && b < complete) {
        words[b / 32] = bits;
      }
    }
    return;
  }
  std::uint32_t ties_before = 0;
  for (std::uint32_t chunk = 0; chunk < complete; chunk += blockDim.x) {
    const std::uint32_t b = chunk + threadIdx.x;
    const std::uint32_t v = b < complete ? sc[b] : 0u;
    const bool tie = b < complete && v == threshold;
    if (b < complete && v > threshold) {
      atomicOr(&words[b / 32], 1u << (b % 32));
    }
    const std::uint64_t ballot = __ballot(tie);
    if (lane == 0) {
      wave_ties[wave] = static_cast<std::uint32_t>(__popcll(ballot));
    }
    __syncthreads();
    std::uint32_t before = ties_before;
    for (std::uint32_t w = 0; w < wave; ++w) {
      before += wave_ties[w];
    }
    before += static_cast<std::uint32_t>(
        __popcll(ballot & ((std::uint64_t{1} << lane) - 1)));
    if (tie && before < remaining) {
      atomicOr(&words[b / 32], 1u << (b % 32));
    }
    std::uint32_t chunk_ties = 0;
    for (std::uint32_t w = 0; w < kThreads / 32; ++w) {
      chunk_ties += wave_ties[w];
    }
    ties_before += chunk_ties;
    __syncthreads();
  }
}

// A global top512 item must belong to its partition's top512, with the same
// lower-index tie rule. Retaining that union cannot remove a global winner.
__global__ void Q2SelectPartitions(const float* scores,const unsigned* start_pos,
    unsigned* candidate_keys,unsigned* candidate_ids) {
  __shared__ unsigned local_mask[q2PartBlocks/32];
  __shared__ unsigned wave_counts[8];
  const unsigned part=blockIdx.x,base=part*q2PartBlocks;
  const unsigned total=(*start_pos+1)/4;
  const unsigned complete=base<total?min(q2PartBlocks,total-base):0;
  const unsigned lane=threadIdx.x&31u,wave=threadIdx.x>>5;
  const auto* sc=reinterpret_cast<const unsigned*>(scores)+min(base,total);
  for(unsigned j=threadIdx.x;j<q2SelectBudget;j+=blockDim.x){
    candidate_keys[part*q2SelectBudget+j]=0;
    candidate_ids[part*q2SelectBudget+j]=~0u;
  }
  Q2SelectLocal(local_mask,sc,complete,q2PartBlocks/32,q2PartBlocks,q2SelectBudget);
  __syncthreads();
  unsigned previous=0;
  for(unsigned chunk=0;chunk<complete;chunk+=blockDim.x){
    const unsigned b=chunk+threadIdx.x;
    const bool take=b<complete && ((local_mask[b/32]>>(b%32))&1u);
    const auto ballot=static_cast<unsigned>(__ballot(take));
    if(lane==0)wave_counts[wave]=__popc(ballot);
    __syncthreads();
    unsigned before=previous;
    for(unsigned w=0;w<wave;++w)before+=wave_counts[w];
    before+=__popc(ballot&((1u<<lane)-1));
    if(take){
      // Positive finite float bits retain their rank after +1. Zero becomes1;
      // padding stays0 and loses every tie with a valid score. No FP arithmetic.
      candidate_keys[part*q2SelectBudget+before]=sc[b]+1;
      candidate_ids[part*q2SelectBudget+before]=base+b;
    }
    for(unsigned w=0;w<8;++w)previous+=wave_counts[w];
    __syncthreads();
  }
}
__global__ void Q2SelectMerge(unsigned* mask,const unsigned* start_pos,
    const unsigned* candidate_keys,const unsigned* candidate_ids,unsigned mask_words) {
  __shared__ unsigned selected[q2SelectSlots/32];
  const unsigned complete=(*start_pos+1)/4;
  for(unsigned w=threadIdx.x;w<mask_words;w+=blockDim.x)
    mask[w]=complete<=q2SelectBudget?~0u:0u;
  if(complete<=q2SelectBudget)return;
  Q2SelectLocal(selected,candidate_keys,q2SelectSlots,q2SelectSlots/32,q2SelectSlots,q2SelectBudget);
  __syncthreads();
  for(unsigned j=threadIdx.x;j<q2SelectSlots;j+=blockDim.x){
    if((selected[j/32]>>(j%32))&1u){
      const unsigned id=candidate_ids[j];
      if(id<complete)atomicOr(mask+id/32,1u<<(id%32));
    }
  }
}
} }
