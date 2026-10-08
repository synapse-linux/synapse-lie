#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebase exact paired norms while preserving the retained control kernels."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-hc-sequence'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Unexpected checkpoint: ' + before[:100])
    return source.replace(before, after)


def section(source, start, end):
    first = source.index(start)
    return source[first:source.index(end, first)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'
    if sha(BASE / REL / 'kernels.hip.cpp') != expected:
        raise ValueError('Retained HC-up source differs')
    shutil.copytree(BASE, OUT)
    subprocess.run(['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch',
                    '-p1', '-i', str(ROOT / 'experiments/q2-hc-norm-half.patch')],
                   cwd=OUT, check=True)
    path = OUT / REL / 'kernels.hip.cpp'
    source, original = path.read_text(), (BASE / REL / path.name).read_text()
    # Keep the original control dispatch and body, not a null-output variant
    # of the candidate. Both paths can then be timed in alternating order.
    for start, end in [
        ('__global__ void HcCombineMoeF32Kernel(', '\n/// HcCombineVec4Kernel<__half>'),
        ('bool HcCombineMoeF32(', '\nbool HcCombineMoeF16('),
    ]:
        candidate = section(source, start, end)
        paired = candidate.replace('HcCombineMoeF32', 'HcCombineMoeF32Half')
        if start.startswith('bool'):
            paired = once(paired, '  if (',
                          '  if (gamma == nullptr || norm_half == nullptr) return false;\n  if (')
        source = once(source, candidate, section(original, start, end) + '\n' + paired)
    path.write_text(source)
    path = OUT / REL / 'kernels.hpp'
    source, original = path.read_text(), (BASE / REL / path.name).read_text()
    candidate = section(source, 'bool HcCombineMoeF32(', '\n/// HcCombineF16 with the MoE')
    paired = candidate.replace('HcCombineMoeF32', 'HcCombineMoeF32Half').replace(
        '__half* norm_half = nullptr', '__half* norm_half')
    source = once(source, candidate, section(original, 'bool HcCombineMoeF32(',
        '\n/// HcCombineF16 with the MoE') + '\n/// Paired F32/F16 norm; gamma and norm_half required.\n' + paired)
    source = once(source,
        '/// Uses one shared row and no global scratch. Optional norm_half\n'
        '/// receives the rounded F16 copy when gamma is non-null; otherwise\n'
        '/// neither normalized output is written. Outputs must be distinct.',
        '/// Uses one shared row, no global scratch and no F16 narrowing.')
    path.write_text(source)
    path = OUT / REL / 'executor.cpp'
    source = path.read_text()
    start = source.index('    if (!xn_half_ &&\n        HcCombineMoeF32(')
    end = source.index('    MoeEpilogueVec4(', start)
    candidate = source[start:end]
    call = section(candidate, 'HcCombineMoeF32(', ')) {') + ')'
    paired = call.replace('HcCombineMoeF32(', 'HcCombineMoeF32Half(')
    retained = call.replace('stream_, norm_half)', 'stream_)')
    source = source[:start] + '''    if (!xn_half_) {
      const bool combined = produce_half ? ''' + paired + ' : ' + retained + ''';
      if (combined) {
        if (produce_half) publish_half();
        return;
      }
    }
''' + source[end:]
    path.write_text(source)
    changed = [str(REL / n) for n in ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp')]
    subprocess.run(['clang-format', '-i', *changed], cwd=OUT, check=True)
    patch = ''.join(''.join(difflib.unified_diff(
        (BASE / n).read_text().splitlines(True), (OUT / n).read_text().splitlines(True),
        fromfile='a/' + n, tofile='b/' + n)) for n in changed)
    target = ROOT / 'experiments/q2-hc-sequence.patch'
    target.write_text(patch)
    report = {
        'scope': 'Isolated sequence source; no runtime evidence',
        'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        'base': str(BASE.relative_to(ROOT)), 'output': str(OUT.relative_to(ROOT)),
        'prior_patch_sha256': sha(ROOT / 'experiments/q2-hc-norm-half.patch'),
        'patch_sha256': sha(target), 'generator': str(Path(__file__).relative_to(ROOT)),
        'file_count': sum(p.is_file() for p in BASE.rglob('*')),
        'changed_files': {n: {'base_sha256': sha(BASE / n), 'candidate_sha256': sha(OUT / n)} for n in changed},
    }
    (ROOT / 'config/q2-hc-sequence-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
