#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Produce expert-compact F32/half rows without a packing gather or padded data."""
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

PREFIX = '''__global__ void RoutedCompactBoundsKernel(
    const std::uint32_t* counts, std::int32_t* padded_bounds,
    std::int32_t* logical_bounds, std::int32_t* cursors,
    std::uint32_t experts) {
  __shared__ std::int32_t padded[1024];
  for (unsigned e = threadIdx.x; e < experts; e += blockDim.x) {
    padded[e] = (counts[e] + 15u) / 16u * 16u;
    cursors[e] = 0;
  }
  __syncthreads();
  if (threadIdx.x == 0) {
    std::int32_t physical = 0, logical = 0;
    for (unsigned e = 0; e < experts; ++e) {
      padded_bounds[e] = physical;
      logical_bounds[e] = logical;
      physical += padded[e];
      logical += counts[e];
    }
    padded_bounds[experts] = physical;
    logical_bounds[experts] = logical;
  }
}

bool RoutedCompactLogical(const std::int32_t* ids, const std::uint32_t* counts,
                          std::int32_t* padded_bounds, std::int32_t* logical_bounds,
                          std::int32_t* cursors, std::int32_t* rows_token,
                          std::int32_t* rows_slot, std::uint32_t tokens,
                          std::uint32_t used, std::uint32_t experts,
                          hipStream_t stream) {
  if (!ids || !counts || !padded_bounds || !logical_bounds || !cursors ||
      !rows_token || !rows_slot || !tokens || !used || !experts || experts > 1024)
    return false;
  const std::size_t slots = std::size_t(tokens) * used;
  const std::size_t rows = RoutedCompactRows(slots, experts);
  if (hipMemsetAsync(rows_token, 0xFF, rows * sizeof(std::int32_t), stream) != hipSuccess ||
      hipMemsetAsync(rows_slot, 0xFF, rows * sizeof(std::int32_t), stream) != hipSuccess)
    return false;
  hipLaunchKernelGGL(RoutedCompactBoundsKernel, dim3(1), dim3(1024), 0, stream,
                    counts, padded_bounds, logical_bounds, cursors, experts);
  if (hipGetLastError() != hipSuccess) return false;
  hipLaunchKernelGGL(RoutedScatterKernel, dim3(Blocks(slots)), dim3(kThreads), 0,
                    stream, ids, padded_bounds, cursors, rows_token, rows_slot,
                    static_cast<std::uint32_t>(slots), used);
  return hipGetLastError() == hipSuccess;
}
'''


def main():
    parent_path = ROOT/'config/q2-scaled-wave-pack-source.json'
    parent = json.loads(parent_path.read_text())['variants']['scaled-wave-pack']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained1574 provider changed')
    out = ROOT/'.deps/gufo-q2-compact-expert-chain-run'
    manifest = ROOT/'config/q2-compact-expert-chain-source.json'
    patch = ROOT/'experiments/q2-compact-expert-chain.patch'
    if any(p.exists() for p in (out,manifest,patch)):
        raise ValueError('Refusing to overwrite an experiment')
    original = {n:(base/(REL+n)).read_text() for n in
                ('kernels.hip.cpp','kernels.hpp','executor.cpp','q2_down_half_storage.inc')}
    gate = function(original['kernels.hip.cpp'],
                    'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    gate = gate.replace('RoutedF16GEMMKernel','RoutedIQ2CompactRowsKernel')
    gate = once(gate, 'const void* __restrict__ w_up) {',
                'const void* __restrict__ w_up, const std::int32_t* logical_bounds) {')
    gate = once(gate, '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;',
                '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;\n'
                '  static_assert(kIQ2 && kPair && !kPacked && !kScaled);')
    gate = once(gate, '          const std::int32_t dst = rows_out[bucket_begin + t];\n'
                      '          if (dst >= 0) {\n'
                      '            const int idx =',
                      '          const std::int32_t slot = rows_out[bucket_begin + t];\n'
                      '          if (slot >= 0) {\n'
                      '            const std::int32_t dst = logical_bounds[expert] + t;\n'
                      '            const int idx =')
    gate_launch = function(original['kernels.hip.cpp'], 'template<int BN, bool kPacked = false>\nvoid LaunchRoutedIQ2(')
    gate_launch = gate_launch.replace('LaunchRoutedIQ2','LaunchRoutedIQ2Compact')
    gate_launch = gate_launch.replace('RoutedF16GEMMKernel','RoutedIQ2CompactRowsKernel')
    gate_launch = once(gate_launch, 'const std::int32_t* rows_slot, float* out,',
                       'const std::int32_t* rows_slot, const std::int32_t* logical_bounds, float* out,')
    gate_launch = once(gate_launch, 'm, k, up);', 'm, k, up, logical_bounds);')
    gate_dispatch = function(original['kernels.hip.cpp'], 'template<bool kPacked>\nbool RoutedGatedIQ2GemmImpl(')
    gate_dispatch = gate_dispatch.replace('template<bool kPacked>\n','').replace('RoutedGatedIQ2GemmImpl','RoutedGatedIQ2CompactGemm')
    gate_dispatch = gate_dispatch.replace('LaunchRoutedIQ2','LaunchRoutedIQ2Compact').replace(', kPacked>', ', false>')
    gate_dispatch = once(gate_dispatch, 'const std::int32_t* rows_slot, float* out,',
                         'const std::int32_t* rows_slot, const std::int32_t* logical_bounds, float* out,')
    gate_dispatch = once(gate_dispatch, '!rows_slot || !m', '!rows_slot || !logical_bounds || !m')
    gate_dispatch = gate_dispatch.replace('rows_token, rows_slot, out, m, k, stream);',
                                           'rows_token, rows_slot, logical_bounds, out, m, k, stream);')
    gate_dispatch = once(gate_dispatch, '  return true;','  return hipGetLastError() == hipSuccess;')
    down = function(original['q2_down_half_storage.inc'],
                    'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    down = down.replace('RoutedQ2HalfStorageKernel','RoutedQ2CompactHalfKernel')
    down = once(down, 'const void* __restrict__ w_up) {',
                'const void* __restrict__ w_up, const std::int32_t* logical_bounds) {')
    down = once(down, '  const int bucket_rows = pad_bounds[expert + 1] - bucket_begin;',
                '  const int bucket_rows = pad_bounds[expert + 1] - bucket_begin;\n'
                '  const int logical_begin = logical_bounds[expert];\n'
                '  const int logical_rows = logical_bounds[expert + 1] - logical_begin;')
    down = once(down, '(chunk < kActChunks && c_row < bucket_rows)\n'
                      '                                 ? rows_in[bucket_begin + c_row]',
                      '(chunk < kActChunks && c_row < logical_rows)\n'
                      '                                 ? logical_begin + c_row')
    down = once(down, 'static_cast<const float*>(w_up)[slot]',
                'static_cast<const float*>(w_up)[logical_begin + token]')
    down = once(down, 'static_cast<const float*>(w_up)[dst]',
                'static_cast<const float*>(w_up)[logical_begin + t]')
    down_launch = function(original['q2_down_half_storage.inc'], 'template<int BN>\nvoid LaunchRoutedQ2HalfStorage(')
    down_launch = down_launch.replace('LaunchRoutedQ2HalfStorage','LaunchRoutedQ2CompactHalf').replace('RoutedQ2HalfStorageKernel','RoutedQ2CompactHalfKernel')
    down_launch = once(down_launch, 'const std::int32_t* slots,',
                       'const std::int32_t* slots, const std::int32_t* logical_bounds,')
    down_launch = once(down_launch, '      inverse);','      inverse, logical_bounds);')
    down_dispatch = function(original['q2_down_half_storage.inc'], 'bool RoutedQ2ScaledHalfGemm(')
    down_dispatch = down_dispatch.replace('RoutedQ2ScaledHalfGemm','RoutedQ2CompactHalfGemm').replace('LaunchRoutedQ2HalfStorage','LaunchRoutedQ2CompactHalf')
    down_dispatch = once(down_dispatch, 'const std::int32_t* slots,',
                         'const std::int32_t* slots, const std::int32_t* logical_bounds,')
    down_dispatch = once(down_dispatch, '!slots || !out', '!slots || !logical_bounds || !out')
    down_dispatch = down_dispatch.replace('bounds, slots,\n', 'bounds, slots, logical_bounds,\n')
    changed = {'q2_compact_expert_chain.inc':'// SPDX-License-Identifier: MIT\n'
        '// Logical expert rows are compact; physical routing maps retain padded buckets.\n'+
        PREFIX+'\n'+gate+'\n'+gate_launch+'\n'+gate_dispatch+'\n'+down+'\n'+down_launch+'\n'+down_dispatch}
    changed['kernels.hip.cpp'] = once(original['kernels.hip.cpp'],
        '#include "q2_down_half_storage.inc"', '#include "q2_down_half_storage.inc"\n#include "q2_compact_expert_chain.inc"')
    declarations = '\n// Private compact expert activation layout.\n'
    for f in (function(PREFIX,'bool RoutedCompactLogical('),gate_dispatch,down_dispatch):
        declarations += f[:f.index(' {')]+';\n'
    changed['kernels.hpp'] = once(original['kernels.hpp'],
        '}  // namespace gufo::models::qwen38_flash_next::rocm',
        declarations+'}  // namespace gufo::models::qwen38_flash_next::rocm')
    executor = original['executor.cpp']
    start = '''  if (iq2_wmma) {
    RoutedCompact(s_.ids, s_.expert_counts, s_.routed_bounds, s_.routed_cursors,
                  s_.rows_token, s_.rows_slot, n_tokens, used, c.num_experts,
                  stream_);'''
    replacement = '''  if (iq2_wmma) {
    auto* scaled = reinterpret_cast<__half*>(s_.up_e);
    auto* inverse = reinterpret_cast<float*>(scaled + std::size_t(slots) * c.expert_ff);
    auto* logical_bounds = reinterpret_cast<std::int32_t*>(inverse + slots);
    const bool compact_chain = compact_down && c.num_experts <= 1024 &&
        std::size_t(slots) * c.expert_ff * sizeof(__half) +
            (std::size_t(slots) + c.num_experts + 1) * sizeof(float) <=
            std::size_t(slots) * c.expert_ff * sizeof(float);
    if (compact_chain) {
      if (!RoutedCompactLogical(s_.ids, s_.expert_counts, s_.routed_bounds,
                                logical_bounds, s_.routed_cursors, s_.rows_token,
                                s_.rows_slot, n_tokens, used, c.num_experts, stream_)) {
        AssignError(error_msg, "compact expert routing failed");
        return false;
      }
    } else {
      RoutedCompact(s_.ids, s_.expert_counts, s_.routed_bounds, s_.routed_cursors,
                    s_.rows_token, s_.rows_slot, n_tokens, used, c.num_experts, stream_);
    }'''
    executor = once(executor,start,replacement)
    executor = once(executor, '''    auto* scaled = reinterpret_cast<__half*>(s_.up_e);
    auto* inverse = reinterpret_cast<float*>(
        scaled + static_cast<std::size_t>(n_tokens) * used * c.expert_ff);
''','')
    executor = once(executor, '      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,',
        '''      if (compact_chain)
        return RoutedGatedIQ2CompactGemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,
            static_cast<const __half*>(s_.x_half), s_.routed_tiles + offset, count, rows,
            s_.routed_bounds, s_.rows_token, s_.rows_slot, logical_bounds,
            s_.gate_e, c.expert_ff, c.hidden_size, stream_);
      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,''')
    executor = once(executor, '        !(compact_down\n',
        '''        !(compact_chain
              ? RoutedQ2CompactHalfGemm(l.ffn_down_exps.data, scaled, inverse,
                    s_.routed_tiles, routed_n_tiles_, routed_tile_rows_,
                    s_.routed_bounds, s_.rows_slot, logical_bounds,
                    reinterpret_cast<__half*>(s_.down_e), c.hidden_size, c.expert_ff, stream_)
              : compact_down
''')
    changed['executor.cpp'] = executor
    shutil.copytree(base,out)
    patches=[]
    for name,value in changed.items():
        value = subprocess.run(['/opt/rocm/llvm/bin/clang-format','--sort-includes=false',
                                '--assume-filename='+str(base/(REL+name))],input=value,
                               text=True,capture_output=True,check=True).stdout
        old = (base/(REL+name)).read_text() if (base/(REL+name)).exists() else ''
        (out/(REL+name)).write_text(value)
        patches.extend(difflib.unified_diff(old.splitlines(True),value.splitlines(True),
                                          fromfile='a/'+REL+name,tofile='b/'+REL+name))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(patches))
    files=inventory(out);delta=[n for n in files if files[n] != parent['files'].get(n)]
    assert len(files)==1028 and len(delta)==4
    measured=ROOT/'config/q2-scaled-wave-pack-model-results.json'
    variant=dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Emit compact expert-major F32 rows directly from gate/up, use unchanged contiguous scaled packing, read compact half rows in down and scatter original slot outputs. Existing routing prefix emits logical offsets.',
        numerical_contract='Original token rows, IQ2/Q2 weights, WMMA K order, F32 SwiGLU, whole640-row scale/RN half, F32 restoration/RN down output. Slot output and downstream ordered sum unchanged.',
        workspace_bytes_2048_top10_512=20480*640*2+(20480+513)*4,
        existing_up_capacity_bytes=20480*640*4,
        additional_allocations=0,additional_streams=0,additional_gpu_dispatches=0,
        risks='Producer store permutation and consumer traversal can change surrounding cache behavior; offset generation adds integer work. Exact source arithmetic does not prove identical compiled output or faster full model.',
        independent_quality=False,gpu_run=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-compact-expert-chain-source.v1',
        variants={'compact-expert-chain':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
