#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pair shared Q8 projections within each wave and emit rounded SwiGLU."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KERNEL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
HEADER = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hpp'
EXECUTOR = 'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'
INCLUDE = 'src/models/qwen38_flash_next/kernels/rocm/q2_shared_q8_pair.inc'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def transform(original):
    kernel = function(original,
        'template<int BM, int BN, int BK, int WM, int WN, bool kHcDown = false>')
    paired = once(kernel,
        'template<int BM, int BN, int BK, int WM, int WN, bool kHcDown = false>',
        'template<int BM, int BN, int BK, int WM, int WN>')
    paired = once(paired, 'W8A8BlockedWmmaGEMMKernel(', 'SharedQ8PairKernel(')
    paired = once(paired, 'const void* __restrict__ w, const void* __restrict__ x_blocks,',
        'const void* __restrict__ gate, const void* __restrict__ up,\n'
        '    const void* __restrict__ x_blocks,')
    paired = once(paired,
        'std::conditional_t<kHcDown, __half, float>* __restrict__ y,',
        '__half* __restrict__ y,')
    paired = once(paired, '  const auto* w_blocks = static_cast<const Q8_0Block*>(w);',
        '  const auto* gate_blocks = static_cast<const Q8_0Block*>(gate);\n'
        '  const auto* up_blocks = static_cast<const Q8_0Block*>(up);\n'
        '  static_assert(kWaveRowTiles == 2, "one gate/up row-tile pair per wave");')
    paired = once(paired,
        'const std::size_t r_block = static_cast<std::size_t>(blockIdx.y) * BM;',
        'const std::size_t r_block = static_cast<std::size_t>(blockIdx.y) * (BM / 2);')
    paired = once(paired, '''    const int r = static_cast<int>(r_block) + (((p * 256) + tid) / BK);
    const int r_clamped = (r < m_i) ? r : (m_i - 1);
    w_row[p] = w_blocks + (static_cast<std::size_t>(r_clamped) * num_blocks);''',
        '''    const int packed_row = ((p * 256) + tid) / BK;
    const int row_tile = packed_row / 16;
    const int r = static_cast<int>(r_block) + (row_tile / 2) * 16 + packed_row % 16;
    const int r_clamped = (r < m_i) ? r : (m_i - 1);
    const auto* weights = (row_tile & 1) ? up_blocks : gate_blocks;
    w_row[p] = weights + (static_cast<std::size_t>(r_clamped) * num_blocks);''')
    begin = paired.index('  // Transpose the result through LDS')
    paired = paired[:begin] + '''  // Keep the original F32 transpose before applying rounded SwiGLU.
  // Gate/up occupy the two halves of one token's 32-float scratch row.
  // Each wave retains its own scratch; no cross-wave reduction.
  __syncthreads();
  auto* tile_scratch = reinterpret_cast<float*>(lds) + wave_id * 16 * 32;
#pragma unroll
  for (int j = 0; j < kWaveTokTiles; ++j) {
#pragma unroll
    for (int l = 0; l < 8; ++l) {
      tile_scratch[sub_lane * 32 + 2 * l + half_id] = acc[0][j][l];
      tile_scratch[sub_lane * 32 + 16 + 2 * l + half_id] = acc[1][j][l];
    }
    __builtin_amdgcn_wave_barrier();
    const std::size_t r0 = r_block + wave_row * 16;
    const std::size_t t0 = t_block + (wave_tok * kWaveTokTiles + j) * 16;
    const std::size_t tok = t0 + (lane_id >> 1);
    const std::size_t r = r0 + (lane_id & 1) * 8;
    const int flat = (lane_id >> 1) * 32 + (lane_id & 1) * 8;
    if (tok < batch) {
#pragma unroll
      for (int q = 0; q < 2; ++q) {
        const float4 g = *reinterpret_cast<const float4*>(tile_scratch + flat + q * 4);
        const float4 u = *reinterpret_cast<const float4*>(tile_scratch + flat + 16 + q * 4);
        const __half2 lo = __floats2half2_rn(SiluF(g.x) * u.x, SiluF(g.y) * u.y);
        const __half2 hi = __floats2half2_rn(SiluF(g.z) * u.z, SiluF(g.w) * u.w);
        const std::size_t row = r + q * 4;
        if (row + 4 <= m && m % 4 == 0 &&
            reinterpret_cast<std::uintptr_t>(y) % 8 == 0) {
          *reinterpret_cast<__half2*>(y + tok * m + row) = lo;
          *reinterpret_cast<__half2*>(y + tok * m + row + 2) = hi;
        } else {
          __half values[4];
          __builtin_memcpy(values, &lo, 4);
          __builtin_memcpy(values + 2, &hi, 4);
#pragma unroll
          for (int v = 0; v < 4; ++v)
            if (row + v < m)
              y[tok * m + row + v] = values[v];
        }
      }
    }
    __builtin_amdgcn_wave_barrier();
  }
}
'''
    return kernel, '// SPDX-License-Identifier: MIT\n// Derived from the pinned Gufo W8A8 kernel; ordered K32 arithmetic retained.\n'+paired


def main():
    parent_path = ROOT/'config/q2-half-consumer-eight-source.json'
    parent = json.loads(parent_path.read_text())['variants']['half-consumer-eight']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Saved1571 provider inventory changed')
    source = ROOT/'.deps/gufo-q2-shared-q8-pair-run'
    manifest = ROOT/'config/q2-shared-q8-pair-source.json'
    patch = ROOT/'experiments/q2-shared-q8-pair.patch'
    if any(p.exists() for p in (source, manifest, patch)):
        raise ValueError('Refusing to overwrite experiment')
    original = {name: (base/name).read_text() for name in (KERNEL, HEADER, EXECUTOR)}
    kernel, include = transform(original[KERNEL])
    changed = dict(original)
    changed[KERNEL] = once(changed[KERNEL], kernel,
        kernel+'\n#include "q2_shared_q8_pair.inc"\n')
    wrapper = '''bool SharedQ8PairHalf(const void* gate, const void* up, const void* x_tiled,
                         __half* out, std::uint32_t batch, std::size_t m,
                         std::size_t k, hipStream_t stream) {
  if (batch < 96 || m != 640 || k != 2560 || gate == nullptr || up == nullptr ||
      x_tiled == nullptr || out == nullptr)
    return false;
  hipLaunchKernelGGL((SharedQ8PairKernel<128, 128, 2, 4, 2>),
                     dim3((batch + 127) / 128, (m + 63) / 64),
                     dim3(kThreads), 0, stream, gate, up, x_tiled, out, batch, m, k);
  return hipGetLastError() == hipSuccess;
}

'''
    changed[KERNEL] = once(changed[KERNEL], 'bool W8A8Gemm(const void* w,',
                          wrapper+'bool W8A8Gemm(const void* w,')
    declaration = '''/// Shared-expert pair; original W8A8 K32 updates and rounded SwiGLU F16.
/// Supported shape m640/k2560/batch>=96; false without launching otherwise.
bool SharedQ8PairHalf(const void* gate, const void* up, const void* x_tiled,
                     __half* out, std::uint32_t batch, std::size_t m,
                     std::size_t k, hipStream_t stream);
'''
    changed[HEADER] = once(changed[HEADER], 'bool W8A8Gemm(const void* w,',
                           declaration+'bool W8A8Gemm(const void* w,')
    dispatch = '''  // Pair the wide shared projections and write only their actual down input.
  // Keep the existing tiled-Q8 identity and private F16 pending lifetime.
  if (n_tokens >= 96 && n_tokens <= options_.max_batch && down != nullptr &&
      up.type == GgmlType::kQ8_0 && gate.type == GgmlType::kQ8_0 &&
      up.rows == 640 && gate.rows == up.rows && up.cols == 2560 &&
      gate.cols == up.cols && down->cols == up.rows &&
      DenseF16Route(*down, n_tokens)) {
    if (!(q8t_src_ == x && q8t_rows_ == n_tokens && q8t_cols_ == up.cols)) {
      QuantizeQ8Tiled(x, s_.x_q8t, n_tokens, up.cols, stream_);
      q8t_src_ = x;
      q8t_rows_ = n_tokens;
      q8t_cols_ = up.cols;
    }
    if (!SharedQ8PairHalf(gate.data, up.data, s_.x_q8t, s_.shexp_half,
                          n_tokens, up.rows, up.cols, stream_)) {
      AssignError(error_msg, "paired shared Q8 prefill failed");
      return false;
    }
    shexp_half_ready_ = true;
    return true;
  }
'''
    changed[EXECUTOR] = once(changed[EXECUTOR],
        '  // Swiglu is in place over its first operand.',
        dispatch+'  // Swiglu is in place over its first operand.')
    changed[INCLUDE] = include
    for name, text in changed.items():
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
            '--sort-includes=false', '--style=file:'+str(base/'.clang-format'),
            '--assume-filename='+str(base/name)], input=text, text=True, capture_output=True)
        if result.returncode:
            raise ValueError('Formatting failed: '+result.stderr)
        changed[name] = result.stdout
    shutil.copytree(base, source)
    for name, text in changed.items():
        (source/name).write_text(text)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1027 and sorted(delta) == sorted(changed)
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(
        ''.join(difflib.unified_diff(original.get(name, '').splitlines(True),
            text.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
        for name, text in changed.items()))
    measured = ROOT/'config/q2-half-consumer-eight-model-results.json'
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mechanism='Each wave pairs a16-row gate tile and corresponding up tile; original int8 K32 WMMA/scaled F32 accumulation feeds rounded SwiGLU F16 directly.',
        numerical_contract='Unchanged Q8 activation quantizer/cache, original encoded weights, K32 accumulation sequence, SiluF and F16 rounding. Per-wave epilogue consumes corresponding rows. Preserve original down consumer and fallback.',
        saved_logical_intermediate_bytes_per_layer=2*2048*640*4,
        extra_allocations=0, extra_streams=0, weight_conversion=False,
        activation_tile_load_reduction_claimed=False,
        risks='Pair mapping halves output rows per CTA relative to one projection; total CTA count matches the old two projections. Benefit is removal of F32 intermediates and one launch, not automatic halving of input reads. Register scheduling and epilogue contraction may change quality/performance.',
        gpu_run=False, model_inference=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-shared-q8-pair-source.v1',
        variants={'shared-q8-pair': variant}, gpu_run=False, goal_met=False), indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta, gpu_run=False)))


if __name__ == '__main__':
    main()
