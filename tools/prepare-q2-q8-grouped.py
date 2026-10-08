#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bound Q8 decoded register lifetimes on the best measured provider."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def function(text, signature):
    if text.count(signature) != 1:
        raise ValueError('Ambiguous retained function')
    start = text.index(signature)
    body = re.search(r'\)\s*\{', text[start:])
    if body is None:
        raise ValueError('Retained function body missing')
    opening = start + body.end() - 1
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def main():
    parent_path = ROOT/'config/q2-hc-moe-deferred-source.json'
    parent = json.loads(parent_path.read_text())['variants']['hc-moe-deferred']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured MoE provider changed')
    source = base/REL
    original = source.read_text()
    kernel = function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    before = '''        __half2 h[16];
#pragma unroll
        for (int i = 0; i < 8; ++i) {
          CodesToHalves(words[i] ^ 0x80808080U, magic, scale2, zero2, h[2 * i],
                        h[2 * i + 1]);
        }
#pragma unroll
        for (int c = 0; c < 4; ++c) {
          uint4 v;
          __builtin_memcpy(&v, &h[4 * c], 16);
          s_a[kk][row][swizzle(row, c)] = v;
        }'''
    after = '''        // Decode and commit one16-byte group before expanding the next.
        // Same byte permutation, half add/FMA and LDS addresses as the parent.
        // The scheduler barrier bounds live decoded registers; it is not a
        // device synchronization and does not change the K16 WMMA sequence.
#pragma unroll
        for (int c = 0; c < 4; ++c) {
          __half2 h[4];
          CodesToHalves(words[2 * c] ^ 0x80808080U, magic, scale2, zero2,
                        h[0], h[1]);
          CodesToHalves(words[2 * c + 1] ^ 0x80808080U, magic, scale2, zero2,
                        h[2], h[3]);
          uint4 v;
          __builtin_memcpy(&v, h, 16);
          s_a[kk][row][swizzle(row, c)] = v;
          __builtin_amdgcn_sched_barrier(0);
        }'''
    if kernel.count(before) != 1:
        raise ValueError('Original Q8 stage anchor changed')
    changed = original.replace(kernel, kernel.replace(before, after), 1)
    candidate = ROOT/'.deps/gufo-q2-q8-grouped-run'
    control = ROOT/'experiments/q2-q8-grouped-control.inc'
    patch = ROOT/'experiments/q2-q8-grouped.patch'
    manifest = ROOT/'config/q2-q8-grouped-source.json'
    if any(p.exists() for p in (candidate, control, patch, manifest)):
        raise ValueError('Refusing to overwrite a retained experiment')
    shutil.copytree(base, candidate)
    (candidate/REL).write_text(changed)
    reference = kernel.replace('DenseF16GEMMKernel', 'DenseQ8GroupedControlKernel')
    reference += function(original, 'bool DenseF16SsmGemm(').replace(
        'DenseF16SsmGemm', 'DenseQ8GroupedControlSsm').replace(
        'DenseF16GEMMKernel', 'DenseQ8GroupedControlKernel')
    reference += '''bool DenseQ8GroupedControlPlain(const void* w, const __half* x, float* y,
                                      unsigned n, unsigned m, unsigned k, hipStream_t stream) {
  hipLaunchKernelGGL((DenseQ8GroupedControlKernel<256,128,2,8,1>),
      dim3((n+127)/128,(m+255)/256),dim3(256),0,stream,w,x,y,n,m,k);
  return hipGetLastError() == hipSuccess;
}
'''
    with control.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n'
                     '// Exact retained MoE provider dense numerical control, test-only.\n'
                     '// Generated from the independently pinned Gufo-derived LIE provider.\n' + reference)
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    files = inventory(candidate)
    delta = [n for n in files if files[n] != parent['files'].get(n)]
    if delta != [REL] or len(files) != 1025:
        raise ValueError('Unexpected provider delta')
    variant = dict(source=str(candidate.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-hc-moe-deferred-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-hc-moe-deferred-model-results.json'),
        original_kernel_sha256=hashlib.sha256(kernel.encode()).hexdigest(),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mechanism='Decode/commit four half2 values at a time with scheduler boundary; original Q8 arithmetic, addresses, tile geometry and ordered K16 WMMA retained',
        byte_exactness_expected_not_qualified=True, additional_allocations=0, additional_streams=0,
        full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-q8-grouped-source.v1',
                       variants={'q8-grouped-store': variant}, gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(files=len(files), changed=delta, original_kernel_sha256=variant['original_kernel_sha256'])))


if __name__ == '__main__':
    main()
