#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose measured cumulative Q2 kernels, exact narrowing and C17 PLE hooks."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DIR = Path('src/models/qwen38_flash_next/kernels/rocm')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor: ' + old[:90])
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', choices=('retained', 'scaled'), required=True)
    args = parser.parse_args()
    name = 'combined-' + args.base
    base = ROOT / '.deps' / ('gufo-q2-bench-' +
                           ('hc-up-chains' if args.base == 'retained' else 'scaled-input'))
    out = ROOT / '.deps' / ('gufo-q2-bench-' + name)
    expected = ('a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'
                if args.base == 'retained' else
                '0a72a7524c9cb04f967503a01b114b22f28cc3d63c44891a7b598e9553c949b4')
    if sha(base / DIR / 'kernels.hip.cpp') != expected:
        raise ValueError('Measured cumulative source changed')
    narrow = ROOT / '.deps/gufo-q2-bench-narrow-vector' / DIR / 'q2_narrow_vector.inc'
    if sha(narrow) != 'da3086de24b62d78d69d7dbe44ade5002d297e11e7490df337db2f1a5e7a5747':
        raise ValueError('Qualified conversion body changed')
    ple_patch = ROOT / 'experiments/q2-ple-lookahead.patch'
    if sha(ple_patch) != 'acf4f603776a173666042124091ca484054ce3cc25ff7873f58e6bad5019432f':
        raise ValueError('Measured PLE hook patch changed')
    shutil.copytree(base, out)
    logs = ROOT / 'evidence' / ('q2-' + name + '-static')
    logs.mkdir()
    argv = ['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch',
            '-p1', '-i', str(ple_patch)]
    with (logs / 'ple-patch.log').open('wb') as stream:
        run = subprocess.run(argv, cwd=out, stdout=stream, stderr=subprocess.STDOUT)
    (logs / 'ple-patch.json').write_text(json.dumps(dict(argv=argv, exit_code=run.returncode), indent=2) + '\n')
    if run.returncode:
        raise RuntimeError('PLE hook composition failed; original sources are untouched')
    kernel = out / DIR / 'kernels.hip.cpp'
    text = once(kernel.read_text(),
                'std::size_t Q8TiledBytes(std::size_t batch, std::size_t k) {',
                '#include "q2_narrow_vector.inc"\n\n'
                'std::size_t Q8TiledBytes(std::size_t batch, std::size_t k) {')
    kernel.write_text(text)
    header = out / DIR / 'kernels.hpp'
    header.write_text(once(header.read_text(),
        '/// W8A8 route for wide batches over Q8_0 weights:',
        '''// Cumulative experiment: existing scalar path remains available for replay.
bool NarrowF16Vector(const float*, __half*, std::size_t, hipStream_t);
void NarrowPrefillActivations(bool, const float*, void*, bool, std::size_t, hipStream_t);

/// W8A8 route for wide batches over Q8_0 weights:'''))
    include = out / DIR / 'q2_narrow_vector.inc'
    include.write_text(narrow.read_text() + '''
// Preserve the original asynchronous launch/error contract. Scalar decode,
// BF16 and unaligned inputs retain NarrowActivations; no error is consumed.
void NarrowPrefillActivations(bool prefill, const float* x, void* out,
                              bool bf16, std::size_t count, hipStream_t stream) {
  if (prefill && !bf16 && count >= 1024 && x && out &&
      count <= std::size_t{0xFFFFFFFFU} * kThreads &&
      (reinterpret_cast<std::uintptr_t>(x) & 15U) == 0 &&
      (reinterpret_cast<std::uintptr_t>(out) & 7U) == 0) {
    const std::size_t vectors = count / 4 + (count % 4 != 0);
    hipLaunchKernelGGL(NarrowF16VectorKernel, dim3(Blocks(vectors)),
                       dim3(kThreads), 0, stream, x,
                       static_cast<__half*>(out), count);
  } else {
    NarrowActivations(x, out, bf16, count, stream);
  }
}
''')
    executor = out / DIR / 'executor.cpp'
    text = executor.read_text()
    if text.count('NarrowActivations(') != 5:
        raise ValueError('Unexpected executor conversion call inventory')
    executor.write_text(text.replace('NarrowActivations(',
                                    'NarrowPrefillActivations(prefill_phase, '))
    names = ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp', 'executor.hpp',
             'q2_narrow_vector.inc')
    subprocess.run(['clang-format', '-i', *(str(out / DIR / n) for n in names)], check=True)
    files = {str(p.relative_to(base)): sha(p) for p in sorted(base.rglob('*')) if p.is_file()}
    changed = [p.relative_to(out) for p in sorted(out.rglob('*'))
               if p.is_file() and sha(p) != files.get(str(p.relative_to(out)))]
    if set(changed) != {DIR / n for n in names}:
        raise ValueError('Unexpected composition inventory')
    patch = ROOT / 'experiments' / ('q2-' + name + '.patch')
    patch.write_text(''.join(''.join(difflib.unified_diff(
        (base / p).read_text().splitlines(True) if (base / p).exists() else [],
        (out / p).read_text().splitlines(True),
        fromfile='a/' + str(p) if (base / p).exists() else '/dev/null',
        tofile='b/' + str(p))) for p in changed))
    report = dict(scope='Prepared cumulative experiment; joint GPU/model benefit unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(base.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
                  base_files=files, patch_sha256=sha(patch),
                  changed_files=[dict(path=str(p), sha256=sha(out / p)) for p in changed],
                  converted_executor_calls=5,
                  composition=['Cumulative retained HC/expert optimizations',
                               'Measured exact F16 vector conversion in prefill only',
                               'Measured ForwardPrepared PLE hook for C17 two-slot scheduling'],
                  scaled_input=args.base == 'scaled',
                  numerical_limits_changed=False, promoted=False,
                  limit='PLE overlap requires a multi-chunk caller; native bench2k uses the cumulative kernels and conversion only. Scaled-input rejection remains.')
    (ROOT / 'config' / ('q2-' + name + '-source.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'base_files'}))


if __name__ == '__main__':
    main()
