#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fuse the existing HC input narrowing into its WMMA consumer loads."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
OUT = ROOT / '.deps/gufo-q2-bench-hc-input'
PREFIX = Path('src/models/qwen38_flash_next/kernels/rocm')
EXPECTED = '4de114a41d58e2b6f74038abfbf27bef8dc285dadf4b95ef69ae3b51b6b8a9fe'


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source boundary: ' + before[:90])
    return text.replace(before, after)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / PREFIX / 'kernels.hip.cpp') != EXPECTED:
        raise ValueError('Measured affine-palette source changed')
    names = [PREFIX / name for name in ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp')]
    original = {name: (BASE / name).read_text() for name in names}
    kernel = original[names[0]]
    kernel = replace_once(kernel,
        '''         bool kHalfWeights = false>
__launch_bounds__(256) __global__ void DenseF16GEMMKernel(
    const void* __restrict__ w, const __half* __restrict__ x,''',
        '''         bool kHalfWeights = false, bool kFloatInput = false>
__launch_bounds__(256) __global__ void DenseF16GEMMKernel(
    const void* __restrict__ w,
    const std::conditional_t<kFloatInput, float, __half>* __restrict__ x,''')
    kernel = replace_once(kernel, '  const __half* b_ptr[kBPer];',
        '  const std::conditional_t<kFloatInput, float, __half>* b_ptr[kBPer];')
    kernel = replace_once(kernel,
        '''        const auto* src = reinterpret_cast<const uint4*>(b_ptr[p] + (kb * 32));
#pragma unroll
        for (int c = 0; c < 4; ++c) {
          b_data[p][c] = src[c];
        }''',
        '''        if constexpr (kFloatInput) {
          // Preserve the separate NarrowKernel's IEEE F16 rounding at the
          // consumer boundary. Every WMMA operand and both K16 sum chains
          // remain unchanged; no persistent narrowed tensor is written.
          const auto* src = reinterpret_cast<const float4*>(b_ptr[p] + kb * 32);
#pragma unroll
          for (int c = 0; c < 4; ++c) {
            const float4 a = src[2 * c], b = src[2 * c + 1];
            const __half2 halves[4] = {
                __floats2half2_rn(a.x, a.y), __floats2half2_rn(a.z, a.w),
                __floats2half2_rn(b.x, b.y), __floats2half2_rn(b.z, b.w)};
            __builtin_memcpy(&b_data[p][c], halves, 16);
          }
        } else {
          const auto* src = reinterpret_cast<const uint4*>(b_ptr[p] + kb * 32);
#pragma unroll
          for (int c = 0; c < 4; ++c) {
            b_data[p][c] = src[c];
          }
        }''')
    entry = '''bool HcDownF32InputGemm(const void* w, const float* x, float* out,
                         std::size_t batch, hipStream_t stream) {
  if (batch < 96 || w == nullptr || x == nullptr || out == nullptr)
    return false;
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true, true>),
      dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,
      batch, std::size_t(320), std::size_t(10240));
  return true;
}

'''
    anchor = 'bool UnquantizedF16Gemm(const void* w, const __half* x, float* out,'
    kernel = replace_once(kernel, anchor, entry + anchor)
    header = replace_once(original[names[1]], anchor,
        '''/// Original F16 HC down with the existing narrowing in its load stage.
/// Fixed M320/K10240, batch >=96; F32 input remains owned by the caller.
bool HcDownF32InputGemm(const void* w, const float* x, float* out,
                         std::size_t batch, hipStream_t stream);

''' + anchor)
    executor = replace_once(original[names[2]],
        '''  } else {
    if (xn_half_) {
      if (!W8A8Gemm(m.down.data, s_.xn_q8t, s_.lo, n_tokens, m.down.rows,''',
        '''  } else {
    if (fused_raw_projection) {
      // Consume the already-live F32 norm without a separate half-buffer
      // pass. The kernel preserves the original F16 operand rounding.
      if (!HcDownF32InputGemm(m.down.data, s_.xn, s_.lo, n_tokens, stream_)) {
        AssignError(error_msg, "HC F32-input down projection failed");
        return false;
      }
    } else if (xn_half_) {
      if (!W8A8Gemm(m.down.data, s_.xn_q8t, s_.lo, n_tokens, m.down.rows,''')
    shutil.copytree(BASE, OUT)
    for name, contents in zip(names, (kernel, header, executor)):
        (OUT / name).write_text(contents)
    subprocess.run(['clang-format', '-i', *(str(OUT / name) for name in names)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed != sorted(map(str, names)):
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / 'experiments/q2-hc-input.patch'
    patch.write_text(''.join(''.join(difflib.unified_diff(original[name].splitlines(True),
        (OUT / name).read_text().splitlines(True), fromfile='a/' + str(name), tofile='b/' + str(name)))
        for name in names))
    report = dict(scope='Prepared isolated source; measured speed and numerical replay unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
        candidate=str(OUT.relative_to(ROOT)), patch_sha256=sha(patch),
        changed_files={str(name):dict(base_sha256=sha(BASE / name), candidate_sha256=sha(OUT / name)) for name in names},
        dispatch='Only original F16 HC down on the existing fused-raw mixer route; M320/K10240 and n>=96',
        numerical_contract='F32 input rounded to identical F16 operands at load; original weights, two ordered K16 chains, final F32 sum',
        new_allocation_bytes=0, limit='Repeated F32 reads and conversions may offset the removed narrowing pass; no speedup assumed')
    (ROOT / 'config/q2-hc-input-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
