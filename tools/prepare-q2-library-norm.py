#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the exact paired norm producer against the new HC-library consumer."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-scaled-library'
OUT = ROOT / '.deps/gufo-q2-bench-library-norm'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycle', action='store_true',
                        help='Preserve original controls for the paired library-consumer fixture')
    args = parser.parse_args()
    name = 'q2-library-norm-cycle' if args.cycle else 'q2-library-norm'
    output = ROOT / ('.deps/gufo-q2-bench-library-norm-cycle' if args.cycle else str(OUT.relative_to(ROOT)))
    patch = ROOT / ('experiments/q2-hc-sequence.patch' if args.cycle else 'experiments/q2-hc-norm-half.patch')
    expected = ('f45133061c4f31aa721a8959ca470263d980ea6de9cbfbeb009e34ad7951c773' if args.cycle
                else 'e53e3e8c9fd06f88c12cd2d468c2299f0ea57233e070b1e94f049a04bf4bcc01')
    if digest(patch) != expected:
        raise ValueError('Previously measured paired-output patch changed')
    base = json.loads((ROOT / 'config/q2-scaled-library-static.json').read_text())['source_file_hashes']
    current = {str(p.relative_to(BASE)): digest(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    if current != base:
        raise ValueError('Measured scaled/library source changed')
    shutil.copytree(BASE, output)
    evidence = ROOT / 'evidence' / (name + '-static')
    evidence.mkdir()
    checks = []

    def run(name, argv):
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (evidence / (name + '.log')).open('x') as log:
            result = subprocess.run(argv, cwd=output, stdout=log, stderr=subprocess.STDOUT)
        checks.append(dict(name=name, argv=argv, exit_code=result.returncode, started_at=start,
                           finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        (evidence / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('Static check failed: ' + name)

    run('patch', ['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch', '-p1', '-i', str(patch)])
    changed = [str(p.relative_to(output)) for p in sorted(output.rglob('*'))
               if p.is_file() and digest(p) != base.get(str(p.relative_to(output)))]
    expected = [str(REL / n) for n in ('executor.cpp', 'kernels.hip.cpp', 'kernels.hpp')]
    if changed != sorted(expected):
        raise ValueError('Unexpected changed file inventory')
    run('format', ['clang-format', '--dry-run', '--Werror', *[str(output / n) for n in changed]])
    compiler = ['/opt/rocm/llvm/bin/clang++', '-x', 'hip', '--offload-arch=gfx1151']
    flags = ['-std=c++20', '-O3', '-ffast-math', '-fno-finite-math-only',
             '-DQFN_ROCM_BUILD=1', '-DENGINE_ENABLE_HIP=1', '-I' + str(output),
             '-isystem', '/opt/rocm/include']
    run('device', compiler + ['--offload-device-only', '-S'] + flags +
        [str(output / REL / 'kernels.hip.cpp'), '-o', str(evidence / 'kernels.s')])
    run('executor', compiler + ['--offload-host-only', '-fsyntax-only'] + flags +
        ['-I' + str(output / REL / 'mmq'), str(output / REL / 'executor.cpp')])
    run('fixture', compiler + ['--offload-host-only', '-fsyntax-only'] + flags +
        [str(ROOT / ('tests/q2_hc_library_norm.cpp' if args.cycle else 'tests/q2_hc_norm_half.cpp'))])
    report = dict(scope='Prepared locally; static compilation only, no GPU or speed claim',
                  base=str(BASE.relative_to(ROOT)), candidate=str(output.relative_to(ROOT)),
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  patch=str(patch.relative_to(ROOT)), patch_sha256=digest(patch),
                  changed_files={n: dict(base_sha256=base[n], candidate_sha256=digest(output / n)) for n in changed},
                  source_file_hashes={str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*')) if p.is_file()},
                  unchanged_files=len(base)-len(changed), checks=checks,
                  extra_tensor_bytes=0, arithmetic_intent='Preserve both F32 norm and existing consumer F16 rounding; previous GPU proof does not qualify this composition',
                  hypothesis='The new HC library consumer may avoid the native consumer regression after interleaved norm writes; measure complete producer/consumer cycles',
                  original_controls_preserved=args.cycle,
                  runtime_admitted=False, promoted=False, goal_met=False)
    (ROOT / 'config' / (name + '-static.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(changed_files=changed, checks=[c['exit_code'] for c in checks], runtime_admitted=False)))


if __name__ == '__main__':
    main()
