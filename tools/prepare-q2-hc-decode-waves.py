#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare isolated HC scalar row-parallelism candidates from the measured base."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '92faa287e2b5681d16f0f54c2f99a3eba0a14c5faaf398e631f8a12b7548cbad'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--waves', type=int, choices=(8, 16, 32), required=True)
    args = parser.parse_args()
    source = (BASE / REL).read_text()
    if hashlib.sha256((BASE / REL).read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Measured base changed')
    start = source.index('// Original F16 HC down weights, four waves cooperating')
    end = source.index('\n__global__ void PleGateKernel', start)
    body = source[start:end]
    old = 'constexpr unsigned waves = 4;'
    if body.count(old) != 1:
        raise ValueError('Unexpected scalar HC implementation')
    body = body.replace(old, f'constexpr unsigned waves = {args.waves};')
    body = body.replace('four waves cooperating', f'{args.waves} waves cooperating')
    source = source[:start] + body + source[end:]
    launch = 'hipLaunchKernelGGL(HcDownF16VecKernel, dim3(320), dim3(128), 0, stream,'
    if source.count(launch) != 1:
        raise ValueError('Unexpected scalar HC dispatch')
    source = source.replace(launch, launch.replace('dim3(128)', f'dim3({args.waves * 32})'))
    out = ROOT / f'.deps/gufo-q2-bench-hc-decode{args.waves}'
    shutil.copytree(BASE, out)
    (out / REL).write_text(source)
    subprocess.run(['clang-format', '-i', str(out / REL)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (out / p.relative_to(BASE)).read_bytes())
    if changed != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / f'experiments/q2-hc-decode{args.waves}.patch'
    patch.write_text(''.join(difflib.unified_diff((BASE / REL).read_text().splitlines(True),
                     (out / REL).read_text().splitlines(True),
                     fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation; numerical drift and runtime benefit unmeasured',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(out / REL),
                  patch_sha256=sha(patch), changed_files=changed, waves=args.waves,
                  threads_per_row=args.waves * 32,
                  groups_per_thread_min=10240 // (args.waves * 128),
                  groups_per_thread_max=(10240 + args.waves * 128 - 1) // (args.waves * 128),
                  last_step_threads=(10240 // 4) % (args.waves * 32) or args.waves * 32,
                  mechanism='Increase scalar HC down row parallelism; preserve F16 weights and F32 products/accumulation',
                  rounding='Per-thread assignments and cross-wave reduction change; independent numerical checks required',
                  dispatch='Only F16 SmallGemm with one token, M320 and K10240')
    (ROOT / f'config/q2-hc-decode{args.waves}-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Prepared scalar HC down with {args.waves} waves:', changed)


if __name__ == '__main__':
    main()
