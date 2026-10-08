#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare vector HC up with the generic scalar kernel's observed FMA order."""
import difflib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-fused'
VEC = ROOT / '.deps/gufo-q2-bench-hc-up-vec'
OUT = ROOT / '.deps/gufo-q2-bench-hc-up-vec-exact'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def main():
    shutil.copytree(VEC, OUT)
    path = OUT / REL
    source = path.read_text()
    before = '''    float dot = 0.0f;
    dot += __half2float(__low2half(lo)) * value.x;
    dot += __half2float(__high2half(lo)) * value.y;
    dot += __half2float(__low2half(hi)) * value.z;
    dot += __half2float(__high2half(hi)) * value.w;
    acc += dot;'''
    after = '''    // The measured generic F16 scalar ISA folds the four products directly
    // into one accumulator in component order 0, 1, 2, 3. Keep that RN tree
    // across all three groups despite fast-math vector-load scheduling.
    acc = __fmaf_rn(__half2float(__low2half(lo)), value.x, acc);
    acc = __fmaf_rn(__half2float(__high2half(lo)), value.y, acc);
    acc = __fmaf_rn(__half2float(__low2half(hi)), value.z, acc);
    acc = __fmaf_rn(__half2float(__high2half(hi)), value.w, acc);'''
    if source.count(before) != 1:
        raise ValueError('Vector HC up source differs from measured candidate')
    path.write_text(source.replace(before, after))
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    patch = ''.join(difflib.unified_diff((BASE / REL).read_text().splitlines(True),
                    path.read_text().splitlines(True), fromfile='a/' + str(REL),
                    tofile='b/' + str(REL)))
    (ROOT / 'experiments/q2-hc-up-vec-exact.patch').write_text(patch)
    print('Prepared vector HC up with ordered FMA:', REL)


if __name__ == '__main__':
    main()
