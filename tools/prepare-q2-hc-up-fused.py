#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an isolated raw-F16 HC up/mix fusion from the measured packed tree."""
import difflib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-packed'
OUT = ROOT / '.deps/gufo-q2-bench-hc-up-fused'


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source does not match the measured checkpoint: ' + before[:80])
    return source.replace(before, after)


def main():
    shutil.copytree(BASE, OUT)
    kernels = OUT / 'src/models/qwen38_flash_next/kernels/rocm'
    path = kernels / 'kernels.hip.cpp'
    source = path.read_text()
    source = once(source,
        'template<typename XnT>\n__global__ void HcMixEpilogueVec4Kernel',
        'template<typename XnT, bool kMix = true>\n__global__ void HcMixEpilogueVec4Kernel')
    start = source.index('__global__ void HcMixEpilogueVec4Kernel')
    end = source.index('\n/// The W8A8 GEMM', start)
    body = source[start:end]
    body = once(body, '    if (i < hidden) {\n      const float4 g',
                      '    if (kMix && i < hidden) {\n      const float4 g')
    body = once(body, '  if (i < hidden) {\n    constexpr float kInvStreams',
                      '  if (kMix && i < hidden) {\n    constexpr float kInvStreams')
    source = source[:start] + body + source[end:]
    source = once(source,
        '    const __half* xn = nullptr, __half* mixed_half = nullptr,',
        '    const std::conditional_t<kHalfWeights, float, __half>* xn = nullptr,\n'
        '    __half* mixed_half = nullptr,')
    # The allocated transpose pool, rather than just its staging subregion,
    # bounds the epilogue. A 128x64 tile avoids the raw-half 256x128 spills.
    source = once(source,
        '  static_assert(kLdsChunks * 16 >= 8 * 512 * 4, "epilogue transposes 16 KB");\n', '')
    source = once(source,
        '  __shared__ __attribute__((aligned(16))) uint4 s_lds[kLdsStorage];',
        '  static_assert(kLdsStorage * 16 >= 8 * 512 * 4, "epilogue transposes 16 KB");\n'
        '  __shared__ __attribute__((aligned(16))) uint4 s_lds[kLdsStorage];')
    start = source.index('  if constexpr (kHcMix) {')
    end = source.index('\n  // Transpose the result', start)
    body = source[start:end]
    body = once(body,
        '    static_assert(BM == 256 && BN == 128 && BK == 1 && WM == 4 && WN == 2);',
        '    static_assert((BM == 128 || BM == 256) && (BN == 64 || BN == 128) &&\n'
        '                  BK == 1 && WM == 4 && WN == 2);')
    body = once(body, '        if (token < batch) {',
        '        // Smaller hidden tiles use only the lanes of 16 token rows.\n'
        '        // All threads still reach both surrounding block barriers.\n'
        '        if (token_in_tile < 16 && token < batch) {')
    source = source[:start] + body + source[end:]
    signature = '''bool HcMixRawF16Gemm(const void* up, const __half* low_rank,
                       const float* xn, const float* inject_w, float* mixed,
                       __half* mixed_half, float* inject, std::uint32_t n_tokens,
                       std::uint32_t hidden, std::uint32_t rank,
                       hipStream_t stream)'''
    function = signature + ''' {
  if (n_tokens < 96 || hidden != 2560 || rank != 320 || up == nullptr ||
      low_rank == nullptr || xn == nullptr || mixed == nullptr ||
      (inject_w != nullptr && inject == nullptr)) {
    return false;
  }
  // Original half weights and the existing F32 normalized streams. Interleave
  // gate rows only in the fetch addresses; no persistent weight repacking.
  const dim3 grid((n_tokens + 63) / 64, 4 * hidden / 128);
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<128, 64, 1, 4, 2, 8, true, false, false, true>),
      grid, dim3(kThreads), 0, stream, up, low_rank, mixed, n_tokens,
      4 * hidden, rank, xn, mixed_half, nullptr);
  if (inject_w != nullptr) {
    // Keep the original F32 inject products, partials and reduction order.
    // This specialization omits only the gate read and mixed-row output.
    hipLaunchKernelGGL((HcMixEpilogueVec4Kernel<float, false>),
        dim3(n_tokens, HcInjectPartsVec4(hidden)), dim3(kThreads), 0, stream,
        xn, nullptr, inject_w, nullptr, inject, hidden);
  }
  return true;
}

'''
    source = once(source, 'bool UnquantizedF16Gemm(', function + 'bool UnquantizedF16Gemm(')
    path.write_text(source)
    path = kernels / 'kernels.hpp'
    source = path.read_text()
    source = once(source, '/// Exact Q8_0 HC up projection',
        '/// Fused original F16 up weights over F16 low rank and F32 normalized\n'
        '/// streams. Fixed hidden=2560, rank=320, n_tokens>=96; other shapes\n'
        '/// return false without a launch. Low rank must not overlap mixed_half.\n'
        '/// Mixed half rows are optional; inject keeps F32 partials.\n'
        + signature + ';\n\n/// Exact Q8_0 HC up projection')
    path.write_text(source)
    path = kernels / 'executor.cpp'
    source = path.read_text()
    anchor = '''  if (fused_projection) {
    // The up projection writes x_half; keep its input in the gate buffer.'''
    raw_condition = '''  const bool fused_raw_projection =
      !xn_half_ && n_tokens >= 96 && extras && c.hc_count == 4 &&
      c.hidden_size == 2560 && c.hc_low_rank == 320 &&
      m.down.type == GgmlType::kF16 && m.down.rows == c.hc_low_rank &&
      m.down.cols == c.HcDim() && m.up.type == GgmlType::kF16 &&
      m.up.rows == c.HcDim() && m.up.cols == c.hc_low_rank &&
      (inject == nullptr || m.inject.empty() || m.inject.type == GgmlType::kF32);
'''
    source = once(source, anchor, raw_condition + anchor)
    source = once(source,
        '    if (!Dense(m.up, s_.lo, s_.hc_gate, n_tokens, error_msg)) {',
        '''    if (fused_raw_projection) {
      // The full gate tensor is dead on this route. Its prefix holds the
      // same narrowed low-rank rows that the separate up GEMM would read.
      NarrowActivations(s_.lo, s_.hc_gate, false,
          static_cast<std::size_t>(n_tokens) * c.hc_low_rank, stream_);
    } else if (!Dense(m.up, s_.lo, s_.hc_gate, n_tokens, error_msg)) {''')
    source = once(source,
        '  } else if (vectorized) {\n    HcMixEpilogueVec4(',
        '''  } else if (fused_raw_projection) {
    if (!HcMixRawF16Gemm(m.up.data,
            reinterpret_cast<const __half*>(s_.hc_gate), xn,
            fused_inject ? m.inject.f32() : nullptr, mixed,
            static_cast<__half*>(s_.x_half), inject, n_tokens,
            c.hidden_size, c.hc_low_rank, stream_)) {
      AssignError(error_msg, "fused raw F16 HC projection failed");
      return false;
    }
    half_src_ = mixed;
    half_rows_ = n_tokens;
    half_cols_ = c.hidden_size;
    half_bf16_ = false;
  } else if (vectorized) {
    HcMixEpilogueVec4(''')
    path.write_text(source)
    subprocess.run(['clang-format', '-i', *[str(kernels / name) for name in
        ('executor.cpp', 'kernels.hip.cpp', 'kernels.hpp')]], check=True)
    changed = [str(p.relative_to(BASE)) for p in sorted(BASE.rglob('*'))
               if p.is_file() and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    patch = ''.join(''.join(difflib.unified_diff((BASE / name).read_text().splitlines(True),
                    (OUT / name).read_text().splitlines(True), fromfile='a/' + name,
                    tofile='b/' + name)) for name in changed)
    (ROOT / 'experiments/q2-hc-up-fused.patch').write_text(patch)
    print('Prepared raw F16 HC up fusion:', changed)


if __name__ == '__main__':
    main()
