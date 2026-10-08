#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an exact-order scalar HC reduction, preserving the original GPU control."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-library-norm-bound'
OUT = ROOT / '.deps/gufo-q2-bench-hc-decode-reduce'
CPP = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
HPP = CPP.with_name('kernels.hpp')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = json.loads((ROOT / 'config/q2-decode-baseline-static.json').read_text())['source_file_hashes']
    actual = {str(p.relative_to(BASE)):sha(p) for p in BASE.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Measured baseline source differs')
    shutil.copytree(BASE, OUT)
    p = OUT / CPP
    s = p.read_text()
    begin = s.index('__global__ void HcDownF16VecKernel(')
    end = s.index('\n__global__ void PleGateKernel', begin)
    original = s[begin:end]
    if original.count('WaveSum(') != 2:
        raise ValueError('Scalar reduction boundary changed')
    helper = '''// First-party experiment derived from pinned Gufo's GDN DPP reduction and
// ReduceKQuantWave immediate XOR. Keep the HC descending tree 16,8,4,2,1.
// Only xor16 crosses a DPP row; all lanes participate before the lane0 store.
template<int Offset = 16>
__device__ __forceinline__ float HcScalarWaveSum(float value) {
  int partner;
  if constexpr (Offset == 16) {
    partner = __builtin_amdgcn_ds_swizzle(__builtin_bit_cast(int, value),
                                           (Offset << 10) | 31);
  } else {
    partner = __builtin_amdgcn_update_dpp(0, __builtin_bit_cast(int, value),
                                           0x160 | Offset, 0xF, 0xF, false);
  }
  const float sum = __fadd_rn(value, __builtin_bit_cast(float, partner));
  if constexpr (Offset > 1)
    return HcScalarWaveSum<Offset / 2>(sum);
  return sum;
}

'''
    candidate = original.replace('HcDownF16VecKernel', 'HcDownF16ReduceKernel').replace('WaveSum(', 'HcScalarWaveSum(')
    s = s[:end] + '\n' + helper + candidate + s[end:]
    call = 'hipLaunchKernelGGL(HcDownF16VecKernel, dim3(320), dim3(512), 0, stream,'
    if s.count(call) != 1:
        raise ValueError('Scalar dispatch differs')
    s = s.replace(call, call.replace('HcDownF16VecKernel', 'HcDownF16ReduceKernel'))
    wrapper = '''// Preserved-control entry point for the isolated component experiment only.
void HcDownF16Reference(const __half* w, const float* x, float* out,
                         hipStream_t stream) {
  hipLaunchKernelGGL(HcDownF16VecKernel, dim3(320), dim3(512), 0, stream,
                     w, x, out);
}

'''
    index = s.index('void SmallGemm(const void* w, WeightType type,')
    s = s[:index] + wrapper + s[index:]
    p.write_text(s)
    p = OUT / HPP
    s = p.read_text()
    index = s.index('void SmallGemm(')
    s = s[:index] + '''// First-party isolated scalar HC reduction control; original F16 bytes.
void HcDownF16Reference(const __half* w, const float* x, float* out,
                         hipStream_t stream);

''' + s[index:]
    p.write_text(s)
    subprocess.run(['clang-format', '-i', str(OUT / CPP), str(OUT / HPP)], check=True)
    text = (OUT / CPP).read_text()
    start = text.index('__global__ void HcDownF16VecKernel(')
    finish = text.index('// First-party experiment derived', start)
    if text[start:finish].strip() != original.strip():
        raise ValueError('Preserved original kernel changed')
    current = {str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()}
    changed = sorted(k for k in current if current[k] != expected[k])
    if changed != sorted([str(CPP), str(HPP)]):
        raise ValueError('Unexpected source change')
    patch = ''.join(''.join(difflib.unified_diff((BASE / rel).read_text().splitlines(True),
        (OUT / rel).read_text().splitlines(True), fromfile='a/'+str(rel), tofile='b/'+str(rel)))
        for rel in (CPP, HPP))
    dest = ROOT / 'experiments/q2-hc-decode-reduce.patch'
    with dest.open('x') as stream: stream.write(patch)
    report = dict(scope='Static preparation, no GPU or model execution',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', changed_files=changed,
        source_file_hashes=current, parent_file_hashes={k:expected[k] for k in changed},
        unchanged_files=len(current)-len(changed), preserved_original_kernel_sha256=hashlib.sha256(original.strip().encode()).hexdigest(),
        patch_sha256=sha(dest), contract='Only HC F16 down n1/m320/k10240 reduction; unchanged 16 waves, weights, FMAs, loop, LDS barrier and descending XOR/add tree. No prefill, up, allocation or scheduling change.',
        provenance=['Pinned kernels.hip.cpp GdnXorAddDpp', 'Pinned src/models/qwen/hip/kernels/small_batch_gemm.hpp ReduceKQuantWave'],
        numerical_pass=None, performance_pass=None, promoted=False, goal_met=False)
    (ROOT / 'config/q2-hc-decode-reduce-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(changed_files=changed, unchanged_files=report['unchanged_files'])))


if __name__ == '__main__':
    main()
