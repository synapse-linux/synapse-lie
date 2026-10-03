#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shorten HC down operand lifetimes while preserving both ordered WMMA sums."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')

PHASED = '''    if constexpr (kHalfWeights && !kHcMix && BM == 64 && BN == 128 &&
                  BK == 2 && WM == 2 && WN == 4 && kRowGroup == 5) {
      // Keep the two original ordered K16 sums. Consume each operand half
      // before loading the other, shortening LDS-fragment register lifetimes.
#pragma unroll
      for (int kb = 0; kb < BK; ++kb) {
#pragma unroll
        for (int phase = 0; phase < 2; ++phase) {
          v16h a[kWaveRowTiles];
#pragma unroll
          for (int i = 0; i < kWaveRowTiles; ++i) {
            const int row = (((wave_row * kWaveRowTiles) + i) * 16) + sub_lane;
            uint4 c[2];
#pragma unroll
            for (int q = 0; q < 2; ++q)
              c[q] = s_a[kb][row][swizzle(row, q + phase * 2)];
            __builtin_memcpy(&a[i], &c[0], 32);
          }
#pragma unroll
          for (int j = 0; j < kWaveTokTiles; ++j) {
            const int t = (((wave_tok * kWaveTokTiles) + j) * 16) + sub_lane;
            uint4 c[2];
#pragma unroll
            for (int q = 0; q < 2; ++q)
              c[q] = s_b[kb][t][swizzle(t, q + phase * 2)];
            v16h b;
            __builtin_memcpy(&b, &c[0], 32);
#pragma unroll
            for (int i = 0; i < kWaveRowTiles; ++i) {
              if (phase == 0)
                acc[i][j] = Wmma(a[i], b, acc[i][j]);
              else
                acc_high[i][j] = Wmma(a[i], b, acc_high[i][j]);
            }
          }
          // Compiler scheduling boundary only; no device synchronization.
          __builtin_amdgcn_sched_barrier(0);
        }
      }
    } else {
'''


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--free-schedule', action='store_true')
    group.add_argument('--k32-boundary', action='store_true')
    args = parser.parse_args()
    suffix = ('hc-k32-schedule' if args.k32_boundary else
              'hc-down-phased-free' if args.free_schedule else 'hc-down-phased')
    out = ROOT / '.deps' / ('gufo-q2-bench-' + suffix)
    expected = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'
    if sha(BASE / REL) != expected:
        raise ValueError('Retained HC-up kernel identity changed')
    original = (BASE / REL).read_text()
    begin = original.index('  fetch_stage(0);', original.index('__global__ void DenseF16GEMMKernel('))
    begin = original.index('#pragma unroll\n    for (int kb = 0; kb < BK; ++kb)', begin)
    end = original.index('    __syncthreads();\n  }', begin)
    old = original[begin:end]
    phased = PHASED
    if args.free_schedule:
        phased = phased.replace('          // Compiler scheduling boundary only; no device synchronization.\n'
                                '          __builtin_amdgcn_sched_barrier(0);\n', '')
    replacement = phased + old + '    }\n'
    if args.k32_boundary:
        if not old.endswith('    }\n'):
            raise ValueError('Unexpected K32 loop boundary')
        replacement = old[:-6] + (
            '      // Bound compiler motion between K32 blocks, retaining the original\n'
            '      // interleaved low/high WMMA updates and all memory operations.\n'
            '      if constexpr (kHalfWeights && !kHcMix && BM == 64 && BN == 128 &&\n'
            '                    BK == 2 && WM == 2 && WN == 4 && kRowGroup == 5)\n'
            '        __builtin_amdgcn_sched_barrier(0);\n'
            '    }\n')
    changed = original[:begin] + replacement + original[end:]
    shutil.copytree(BASE, out)
    (out / REL).write_text(changed)
    subprocess.run(['clang-format', '-i', str(out / REL)], check=True)
    files = {str(p.relative_to(BASE)):sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    changed_files = [name for name, digest in files.items() if sha(out / name) != digest]
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments' / ('q2-' + suffix + '.patch')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
                      (out / REL).read_text().splitlines(True), fromfile='a/'+str(REL), tofile='b/'+str(REL))))
    result = dict(scope='Isolated HC operand lifetime experiment; GPU speed/replay unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
                  candidate=str(out.relative_to(ROOT)), base_sha256=expected,
                  candidate_sha256=sha(out / REL), patch_sha256=sha(patch),
                  phase_compiler_barrier=not args.free_schedule and not args.k32_boundary,
                  k32_compiler_barrier=args.k32_boundary,
                  base_files=files, changed_files=changed_files,
                  arithmetic='Original F16 operands, two ordered K16 sums, unchanged final F32 addition',
                  changed_scope='Only HC down M320/K10240/n>=96, original 64x128/BK2/WM2/WN4 geometry',
                  allocation_bytes_added=0, numerical_limits_changed=False, promoted=False)
    (ROOT / 'config' / ('q2-' + suffix + '-source.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='base_files'}))


if __name__ == '__main__':
    main()
