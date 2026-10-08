#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fuse routed IQ2 SwiGLU/Q8 emission with a direct, bounded Q2 MMQ consumer."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function

EMIT = '''// Same 144-byte D2S6 block contract as the attributed MMQ quantizer.
struct Q2ProducerQ8Block {
  __half d2s6[8];
  std::int8_t qs[128];
};
static_assert(sizeof(Q2ProducerQ8Block) == 144);

// One complete wave owns a 64-value group; every live lane has two values.
// Adjacent even lanes reconstruct the quantizer's original four-value sum.
__device__ __forceinline__ void EmitQ2ProducerQ8(
    float a, float b, void* output, std::size_t capacity,
    std::size_t physical_row, int r_block, int lane) {
  float peak = fmaxf(fabsf(a), fabsf(b));
#pragma unroll
  for (int offset = 16; offset; offset >>= 1)
    peak = fmaxf(peak, __shfl_xor(peak, offset, 32));
  const float inv = peak == 0.0F ? 0.0F : 127.0F / peak;
  const std::int8_t qa = static_cast<std::int8_t>(roundf(a * inv));
  const std::int8_t qb = static_cast<std::int8_t>(roundf(b * inv));
  auto* blocks = static_cast<Q2ProducerQ8Block*>(output);
  auto& block = blocks[std::size_t(r_block / 128) * capacity + physical_row];
  const int q_index = r_block % 128 + lane * 2;
  const std::uint16_t codes = std::uint8_t(qa) | (std::uint16_t(std::uint8_t(qb)) << 8);
  *reinterpret_cast<std::uint16_t*>(block.qs + q_index) = codes;
  const float c = __shfl_down(a, 1, 32);
  const float d = __shfl_down(b, 1, 32);
  float sum = a + b + c + d;
  sum += __shfl_xor(sum, 4, 32);
  sum += __shfl_xor(sum, 2, 32);
  if (q_index % 16 == 0 && q_index < 96)
    block.d2s6[2 + q_index / 16] = __float2half_rn(sum);
  if (lane == 0)
    block.d2s6[r_block % 128 / 64] = __float2half_rn(peak == 0.0F ? 0.0F : 1.0F / inv);
  // The final live64 group also initializes the entire stored640..767 tail.
  if (r_block == 576) {
    auto& tail = blocks[5 * capacity + physical_row];
    reinterpret_cast<std::uint32_t*>(tail.qs)[lane] = 0;
    if (lane < 4) reinterpret_cast<std::uint32_t*>(tail.d2s6)[lane] = 0;
  }
}
'''

DOWN = '''// SPDX-License-Identifier: MIT
// Bounded routed Q2 consumer. Arithmetic helpers derive from official Gufo's
// llama.cpp MMQ port; see mmq/VENDOR.md and the pinned LIE source manifest.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "qfn_mmq.h"
#include "common.hpp"
#include "mmq.hpp"

template<int BN, bool CheckRows>
__global__ void Q2ProducerQ8DownKernel(
    const char* __restrict__ weights, const int* __restrict__ packed,
    const std::int32_t* __restrict__ tiles,
    const std::uint32_t* __restrict__ counts,
    const std::int32_t* __restrict__ bounds,
    const std::int32_t* __restrict__ slots,
    half* __restrict__ output, int m, int capacity) {
#if defined(__HIP_DEVICE_COMPILE__)
  static_assert(ggml_hip_get_physical_warp_size() == 32);
  static_assert(mmq_get_nwarps_device() == 4 && get_mmq_y_device() == 64);
  static_assert(mmq_get_ncw_device() == 1);
#endif
  constexpr int BM = 64, Threads = 128;
  const int tid = threadIdx.y * 32 + threadIdx.x;
  const int descriptor = tiles[blockIdx.y];
  const int expert = descriptor & 0xffff;
  const int token_begin = (descriptor >> 16) * BN;
  const int remaining = int(counts[expert]) - token_begin;
  if (remaining <= 0) return;
  const int live = remaining < BN ? remaining : BN;
  const int physical_begin = bounds[expert] + token_begin;
  const int output_begin = int(blockIdx.x) * BM;
  const int output_last = m - output_begin - 1;
  __shared__ int ids[BN];
  __shared__ int y_tile[GGML_PAD(BN * MMQ_TILE_Y_K, Threads)];
  __shared__ int x_tile[BM * MMQ_MMA_TILE_X_K_Q2_K];
  if (tid < BN) ids[tid] = tid < live ? slots[physical_begin + tid] : 0;
  float sum[BN * BM / Threads] = {0.0F};
  constexpr int Words = sizeof(block_q8_1_mmq) / sizeof(int);
  const int weight_begin = (expert * m + output_begin) * 3;
  for (int kb = 0; kb < 3; ++kb) {
    load_tiles_q2_K<BM, CheckRows>(weights, x_tile, weight_begin + kb, output_last, 3);
    // All padding is masked at load: no cross-expert read or global slack.
#pragma unroll
    for (int l0 = 0; l0 < BN * MMQ_TILE_Y_K; l0 += Threads) {
      const int l = l0 + tid;
      if (l < BN * MMQ_TILE_Y_K)
        y_tile[l] = l / Words < live
            ? packed[(kb * 2 * capacity + physical_begin) * Words + l] : 0;
    }
    __syncthreads();
    vec_dot_q2_K_q8_1_mma<BN, BM>(x_tile, y_tile, sum, 0);
    __syncthreads();
#pragma unroll
    for (int l0 = 0; l0 < BN * MMQ_TILE_Y_K; l0 += Threads) {
      const int l = l0 + tid;
      if (l < BN * MMQ_TILE_Y_K)
        y_tile[l] = l / Words < live
            ? packed[((kb * 2 + 1) * capacity + physical_begin) * Words + l] : 0;
    }
    __syncthreads();
    vec_dot_q2_K_q8_1_mma<BN, BM>(x_tile, y_tile, sum, MMQ_TILE_NE_K);
    __syncthreads();
  }
  // Original gfx1151 MMQ accumulator ownership, narrowed once at the consumer.
  using Tile = tile<16,16,int,DATA_LAYOUT_J_MAJOR>;
#pragma unroll
  for (int j0 = 0; j0 < BN; j0 += 16) {
#pragma unroll
    for (int l = 0; l < Tile::ne; ++l) {
      const int row = int(threadIdx.y) * 16 + Tile::get_i(l);
      const int token = j0 + Tile::get_j(l);
      if (token < live && (!CheckRows || row <= output_last))
        output[std::size_t(ids[token]) * m + output_begin + row] =
            __float2half_rn(sum[(j0 / 16) * Tile::ne + l]);
    }
  }
}

template<int BN>
static void LaunchQ2ProducerQ8Down(const void* weights, const void* packed,
    const std::int32_t* tiles, unsigned tile_count, const std::uint32_t* counts,
    const std::int32_t* bounds, const std::int32_t* slots, void* output,
    unsigned m, unsigned capacity, hipStream_t stream) {
  const dim3 grid((m + 63) / 64, tile_count), block(32,4);
  if (m % 64)
    Q2ProducerQ8DownKernel<BN,true><<<grid,block,0,stream>>>(
        static_cast<const char*>(weights), static_cast<const int*>(packed),
        tiles,counts,bounds,slots,static_cast<half*>(output),m,capacity);
  else
    Q2ProducerQ8DownKernel<BN,false><<<grid,block,0,stream>>>(
        static_cast<const char*>(weights), static_cast<const int*>(packed),
        tiles,counts,bounds,slots,static_cast<half*>(output),m,capacity);
}

extern "C" int qfn_q2_producer_q8_down(const void* weights, const void* packed,
    const std::int32_t* tiles, unsigned tile_count, unsigned tile_rows,
    const std::uint32_t* counts, const std::int32_t* bounds,
    const std::int32_t* slots, void* output, unsigned m, unsigned capacity,
    hipStream_t stream) {
  if (!weights || !packed || !tiles || !counts || !bounds || !slots ||
      !output || !m || !capacity || !tile_count) return -1;
  switch (tile_rows) {
    case 16: LaunchQ2ProducerQ8Down<16>(weights,packed,tiles,tile_count,counts,bounds,slots,output,m,capacity,stream); break;
    case 48: LaunchQ2ProducerQ8Down<48>(weights,packed,tiles,tile_count,counts,bounds,slots,output,m,capacity,stream); break;
    case 64: LaunchQ2ProducerQ8Down<64>(weights,packed,tiles,tile_count,counts,bounds,slots,output,m,capacity,stream); break;
    default: return -1;
  }
  return hipGetLastError() == hipSuccess ? 0 : -2;
}
} // namespace qfn_mmq
'''


def main():
    manifest = ROOT/'config/q2-producer-q8-source.json'
    patch = ROOT/'experiments/q2-producer-q8.patch'
    out = ROOT/'.deps/gufo-q2-producer-q8-run'
    if any(p.exists() for p in (manifest,patch,out)):
        raise ValueError('Refusing to overwrite an experiment')
    parent_path = ROOT/'config/q2-scaled-wave-pack-source.json'
    parent = json.loads(parent_path.read_text())['variants']['scaled-wave-pack']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']: raise ValueError('Retained1574 provider changed')
    kernel = (base/(REL+'kernels.hip.cpp')).read_text()
    gate = function(kernel,'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    gate = gate.replace('RoutedF16GEMMKernel','RoutedIQ2ProducerQ8Kernel')
    gate = once(gate,'const void* __restrict__ w_up) {','const void* __restrict__ w_up, std::size_t q8_capacity) {')
    gate = once(gate,'  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;',
        '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;\n  static_assert(kIQ2 && kPair && !kPacked && !kScaled);')
    first=gate.index('            const auto offset = static_cast<std::size_t>(dst) * m + r_block + r;')
    last=gate.index('\n          }\n        }\n      }\n      __syncthreads();',first)
    gate=gate[:first]+'''            EmitQ2ProducerQ8(wide_values[0], wide_values[1], out,
                q8_capacity, bucket_begin + t, r_block, lane_id);'''+gate[last:]
    launch=function(kernel,'template<int BN, bool kPacked = false>\nvoid LaunchRoutedIQ2(')
    launch=launch.replace('LaunchRoutedIQ2','LaunchRoutedIQ2ProducerQ8').replace('RoutedF16GEMMKernel','RoutedIQ2ProducerQ8Kernel')
    launch=once(launch,'hipStream_t stream) {','std::size_t q8_capacity, hipStream_t stream) {')
    launch=once(launch,'m, k, up);','m, k, up, q8_capacity);')
    dispatch=function(kernel,'template<bool kPacked>\nbool RoutedGatedIQ2GemmImpl(')
    dispatch=dispatch.replace('template<bool kPacked>\n','').replace('RoutedGatedIQ2GemmImpl','RoutedGatedIQ2ProducerQ8Gemm').replace('LaunchRoutedIQ2','LaunchRoutedIQ2ProducerQ8').replace(', kPacked>',', false>')
    dispatch=once(dispatch,'hipStream_t stream) {','std::size_t q8_capacity, hipStream_t stream) {')
    dispatch=once(dispatch,'!rows_slot || !m','!rows_slot || m != 640 || !q8_capacity || !m')
    dispatch=dispatch.replace('out, m, k, stream);','out, m, k, q8_capacity, stream);')
    dispatch=once(dispatch,'  return true;','  return hipGetLastError() == hipSuccess;')
    changed={REL+'q2_producer_q8.inc':'// SPDX-License-Identifier: MIT\n'+EMIT+'\n'+gate+'\n'+launch+'\n'+dispatch,
        REL+'mmq/q2_producer_q8.hip.cpp':DOWN}
    changed[REL+'kernels.hip.cpp']=once(kernel,'#include "q2_down_half_storage.inc"','#include "q2_down_half_storage.inc"\n#include "q2_producer_q8.inc"')
    header=(base/(REL+'kernels.hpp')).read_text()
    declaration=dispatch[:dispatch.index(' {')]+';\n'
    changed[REL+'kernels.hpp']=once(header,'}  // namespace gufo::models::qwen38_flash_next::rocm',declaration+'\n}  // namespace gufo::models::qwen38_flash_next::rocm')
    mmqh=(base/(REL+'mmq/qfn_mmq.h')).read_text()
    f=function(DOWN,'extern "C" int qfn_q2_producer_q8_down(')
    declaration=f[:f.index(' {')].replace('extern "C" ','').replace('std::int32_t','int32_t').replace('std::uint32_t','uint32_t')+';\n'
    changed[REL+'mmq/qfn_mmq.h']=once(mmqh,'int qfn_mmq_init(int device);','int qfn_mmq_init(int device);\n\n'+declaration)
    cmake=(base/'src/models/qwen38_flash_next/CMakeLists.txt').read_text()
    changed['src/models/qwen38_flash_next/CMakeLists.txt']=once(cmake,'    ${QFN_MMQ_DIR}/qfn_mmq.hip.cpp','    ${QFN_MMQ_DIR}/qfn_mmq.hip.cpp\n    ${QFN_MMQ_DIR}/q2_producer_q8.hip.cpp')
    executor=(base/(REL+'executor.cpp')).read_text()
    anchor='  if (iq2_wmma) {\n    RoutedCompact('
    executor=once(executor,anchor,'''  const std::size_t q8_capacity = RoutedCompactRows(slots, c.num_experts);
  const bool producer_q8 = compact_down && q8_capacity * 6 * 144 <=
      std::size_t(slots) * c.expert_ff * sizeof(float);
  if (iq2_wmma) {
    RoutedCompact(''')
    anchor='''      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,'''
    executor=once(executor,anchor,'''      if (producer_q8)
        return RoutedGatedIQ2ProducerQ8Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,
            static_cast<const __half*>(s_.x_half), s_.routed_tiles + offset, count,
            rows, s_.routed_bounds, s_.rows_token, s_.rows_slot, s_.gate_e,
            c.expert_ff, c.hidden_size, q8_capacity, stream_);
      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,''')
    anchor='''    if (!gate_ok ||
        !PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                          c.expert_ff, stream_) ||'''
    replacement='''    if (!gate_ok || (producer_q8
        ? qfn_q2_producer_q8_down(l.ffn_down_exps.data, s_.gate_e,
              s_.routed_tiles, routed_n_tiles_, routed_tile_rows_, s_.expert_counts,
              s_.routed_bounds, s_.rows_slot, s_.down_e, c.hidden_size,
              static_cast<unsigned>(q8_capacity), stream_) != 0
        : (!PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                          c.expert_ff, stream_) ||'''
    executor=once(executor,anchor,replacement)
    executor=once(executor,'c.expert_ff, stream_))) {\n      AssignError(error_msg, "routed IQ2 paired gate/up or Q2 down failed");',
        'c.expert_ff, stream_))))) {\n      AssignError(error_msg, "routed IQ2 paired gate/up or Q2 down failed");')
    changed[REL+'executor.cpp']=executor
    shutil.copytree(base,out)
    diffs=[]
    for rel,value in changed.items():
        if rel.endswith(('.cpp','.hpp','.h','.inc')):
            value=subprocess.run(['/opt/rocm/llvm/bin/clang-format','--sort-includes=false',
                '--assume-filename='+str(base/rel)],input=value,text=True,capture_output=True,check=True).stdout
        old=(base/rel).read_text() if (base/rel).exists() else ''
        (out/rel).write_text(value)
        diffs.extend(difflib.unified_diff(old.splitlines(True),value.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(diffs))
    files=inventory(out);delta=[n for n in files if files[n]!=parent['files'].get(n)]
    assert len(files)==1029 and len(delta)==7
    measured=ROOT/'config/q2-scaled-wave-pack-model-results.json'
    sources=[base/(REL+'kernels.hip.cpp'),base/(REL+'mmq/mmq.hpp'),base/(REL+'mmq/quantize.hip.cpp'),
        ROOT/'.deps/gufo-base/src/models/deepseek_v4_flash/kernels/rocm/mmq/ds4_mmq.hip.cpp']
    variant=dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        upstream_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        inspected_sources={str(p.relative_to(ROOT)):sha(p) for p in sources},
        mechanism='Emit64-value Q8 D2S6 groups from the unchanged IQ2 WMMA/SwiGLU producer; consume original Q2 weights by bounded direct integer MMQ and narrow output once. Existing padded routing reused.',
        arithmetic_change='Replaces row-scaled F16 activations and F16-WMMA down with64-value Q8 scales and integer-MMQ Q2 arithmetic; original gate/up F16 and F32 SwiGLU retained. Independent matrix/model quality remains unqualified.',
        workspace_bytes_2048_top10_512=28160*6*144,
        original_gate_capacity_bytes=20480*640*4,
        additional_allocations=0,additional_streams=0,gpu_dispatches_removed=1,
        materialized_f32_gate_removed=True,half_pack_pass_removed=True,
        risks='Q8 error, MMQ occupancy and instruction cost can outweigh removed passes. Routing padding must be masked before all loads; grouped producer sums and half scales need independent replay.',
        gpu_run=False,independent_quality=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-producer-q8-source.v1',variants={'producer-q8':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
