#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a 160-row HC tile retaining 128 tokens and both K16 sums."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-hc-row160-wide'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor: ' + old[:80])
    return text.replace(old, new)


def main():
    expected = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'
    if sha(BASE / REL) != expected:
        raise ValueError('Retained HC-up base changed')
    original = (BASE / REL).read_text()
    start = original.index('__launch_bounds__(kHcUpChains ? 512 : 256)')
    end = original.index('bool AttentionF16Gemm(', start)
    text = once(original[start:end], '__launch_bounds__(kHcUpChains ? 512 : 256) __global__ void DenseF16GEMMKernel(',
                '__launch_bounds__(WM * WN * 32 * (kHcUpChains ? 2 : 1)) __global__ void DenseF16GEMMKernel(')
    text = once(text, '  static_assert(WM * WN == 8, "256 threads is 8 waves");',
                '  static_assert(WM * WN == 8 ||\n'
                '                (BM == 160 && BN == 128 && BK == 2 && WM == 5 &&\n'
                '                 WN == 4 && kRowGroup == 2 && kHalfWeights &&\n'
                '                 !kHcMix && !kSsmConv && !kAttention && !kHcUpChains));')
    text = once(text, '  constexpr int kBlockThreads = kHcUpChains ? 512 : 256;',
                '  constexpr int kBlockThreads = WM * WN * 32 * (kHcUpChains ? 2 : 1);')
    text = once(text, '  constexpr int kTransposeChunks = 8 * 16 * 36 * sizeof(float) / sizeof(uint4);',
                '  constexpr int kTransposeChunks = WM * WN * 16 * 36 * sizeof(float) / sizeof(uint4);')
    text = original[:start] + text + original[end:]
    text = once(text,
                '    // Group all five row tiles around one 128-token input stripe. The\n'
                '    // original F16 full-batch input alone exceeds the 32 MiB cache.\n'
                '    hipLaunchKernelGGL(\n'
                '        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),\n'
                '        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,\n'
                '        batch, m, k);',
                '    // Two row blocks share each 128-token stripe. Twenty waves retain\n'
                '    // the original per-wave 32x32 output and two ordered K16 sums.\n'
                '    hipLaunchKernelGGL(\n'
                '        (DenseF16GEMMKernel<160, 128, 2, 5, 4, 2, false, false, false, true>),\n'
                '        dim3((batch + 127) / 128, 2), dim3(640), 0, stream, w, x, out,\n'
                '        batch, m, k);')
    shutil.copytree(BASE, OUT)
    (OUT / REL).write_text(text)
    subprocess.run(['clang-format', '-i', str(OUT / REL)], check=True)
    files = {str(p.relative_to(BASE)):sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    changed = [name for name, digest in files.items() if sha(OUT / name) != digest]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source differences')
    patch = ROOT / 'experiments/q2-hc-row160-wide.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
                      (OUT / REL).read_text().splitlines(True),fromfile='a/'+str(REL),tofile='b/'+str(REL))))
    report = dict(scope='Prepared HC row160/token128 component; no GPU or model result',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',base=str(BASE.relative_to(ROOT)),
                  candidate=str(OUT.relative_to(ROOT)),base_sha256=expected,candidate_sha256=sha(OUT/REL),
                  patch_sha256=sha(patch),base_files=files,changed_files=changed,
                  geometry='BM160/BN128/BK2/WM5/WN4, 640 threads and two-row grouping',
                  arithmetic='Unchanged two ordered K16 sums, original F16 operands and final F32 addition',
                  reference_logical_staging_mib=dict(input=200,weights=100,blocks=80),
                  candidate_logical_staging_mib=dict(input=80,weights=100,blocks=32),
                  physical_traffic_measured=False,model_conversion=False,promoted=False)
    (ROOT/'config/q2-hc-row160-wide-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='base_files'}))


if __name__ == '__main__':
    main()
