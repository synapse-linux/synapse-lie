#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retile raw-F16 HC down while retaining both ordered K16 chains."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
OUT = ROOT / '.deps/gufo-q2-bench-hc-down64'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def main():
    shutil.copytree(BASE, OUT)
    path = OUT / REL
    source = path.read_text()
    before = '''    // Group all five row tiles around one 128-token input stripe. The
    // original F16 full-batch input alone exceeds the 32 MiB cache.
    hipLaunchKernelGGL(
        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,
        batch, m, k);'''
    after = '''    // A 64-token stripe halves each wave's output accumulators. Group
    // all five row tiles around it, retaining both ordered K16 chains.
    hipLaunchKernelGGL(
        (DenseF16GEMMKernel<64, 64, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 63) / 64, 5), dim3(kThreads), 0, stream, w, x, out,
        batch, m, k);'''
    if source.count(before) != 1:
        raise ValueError('HC down differs from measured MoE/HC checkpoint')
    path.write_text(source.replace(before, after))
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    patch = ''.join(difflib.unified_diff((BASE / REL).read_text().splitlines(True),
                    path.read_text().splitlines(True), fromfile='a/' + str(REL),
                    tofile='b/' + str(REL)))
    patch_path = ROOT / 'experiments/q2-hc-down64.patch'
    patch_path.write_text(patch)
    changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
               and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source changes')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Source preparation only; no numerical or GPU evidence',
                  base='measured F32 MoE/HC fusion; excludes rejected norm copy',
                  official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  file_count=sum(p.is_file() for p in BASE.rglob('*')),
                  changed_files={str(REL): dict(base_sha256=sha(BASE / REL),
                                                candidate_sha256=sha(path))},
                  patch_sha256=sha(patch_path),
                  generator=str(Path(__file__).relative_to(ROOT)))
    (ROOT / 'config/q2-hc-down64-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared tile-only HC down candidate:', changed)


if __name__ == '__main__':
    main()
