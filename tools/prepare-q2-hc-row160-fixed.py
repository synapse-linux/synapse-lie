#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Specialize the existing HC160 tile for its dispatch-proven M/K shape."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-row160-wide'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hoist-zero', action='store_true',
                        help='Initialize inactive fetch lanes once before the K loop')
    args = parser.parse_args()
    suffix = 'hc-row160-loads' if args.hoist_zero else 'hc-row160-fixed'
    out = ROOT / '.deps' / ('gufo-q2-bench-' + suffix)
    expected = 'a3b8dc431298c74d26f2bf7e3b77ac3f1354008e9a8cef7c18010457c9b37d88'
    if sha(BASE / REL) != expected:
        raise ValueError('Measured HC160 source changed')
    original = (BASE / REL).read_text()
    start = original.index('    void DenseF16GEMMKernel(')
    anchor = '  constexpr int kRowTiles = BM / 16;'
    pos = original.index(anchor, start)
    specialization = '''  // This tile is launched only by the M320/K10240 HC-down dispatch.
  // Expose that contract to the compiler; token tails remain runtime-checked.
  if constexpr (BM == 160 && BN == 128 && BK == 2 && WM == 5 && WN == 4 &&
                kRowGroup == 2 && kHalfWeights && !kHcMix && !kSsmConv &&
                !kAttention && !kHcUpChains) {
    m = 320;
    k = 10240;
  }
'''
    changed = original[:pos] + specialization + original[pos:]
    if args.hoist_zero:
        begin = changed.index('  uint4 a_codes[kAPer][2];', start)
        end = changed.index('  const __half2 magic', begin)
        scope = changed[begin:end]
        anchor = '  const auto fetch_stage = [&](int kb0) {\n'
        if scope.count(anchor) != 1:
            raise ValueError('Unexpected fetch stage')
        scope = scope.replace(anchor, '''  constexpr bool kFixedHcDown = BM == 160 && BN == 128 && BK == 2 &&
      WM == 5 && WN == 4 && kRowGroup == 2 && kHalfWeights &&
      !kHcMix && !kSsmConv && !kAttention && !kHcUpChains;
  // Lane validity is invariant over all 160 K stages. Initialize the
  // inactive lanes once; active lanes replace every word on every fetch.
  if constexpr (kFixedHcDown) {
#pragma unroll
    for (int p = 0; p < kAPer; ++p)
#pragma unroll
      for (int c = 0; c < 4; ++c)
        a_half[p][c] = make_uint4(0u, 0u, 0u, 0u);
#pragma unroll
    for (int p = 0; p < kBPer; ++p)
#pragma unroll
      for (int c = 0; c < 4; ++c)
        b_data[p][c] = make_uint4(0u, 0u, 0u, 0u);
  }
  const auto fetch_stage = [&](int kb0) {
    if constexpr (kFixedHcDown) {
      // M320/K10240 has no row or K tail. Preserve masked token lanes,
      // but do not refill their zero fragments inside the reduction loop.
#pragma unroll
      for (int p = 0; p < kAPer; ++p) {
        const int kb = kb0 + (((p * kBlockThreads) + tid) % BK);
        if (a_live[p]) {
          const auto* src = reinterpret_cast<const uint4*>(a_ptr[p] + kb * 64);
#pragma unroll
          for (int c = 0; c < 4; ++c)
            a_half[p][c] = src[c];
        }
      }
#pragma unroll
      for (int p = 0; p < kBPer; ++p) {
        const int kb = kb0 + (((p * kBlockThreads) + tid) % BK);
        if (b_ptr[p] != nullptr) {
          const auto* src = reinterpret_cast<const uint4*>(b_ptr[p] + kb * 32);
#pragma unroll
          for (int c = 0; c < 4; ++c)
            b_data[p][c] = src[c];
        }
      }
    } else {
''')
        if not scope.endswith('  };\n\n'):
            raise ValueError('Unexpected fetch end')
        scope = scope[:-6] + '    }\n  };\n\n'
        changed = changed[:begin] + scope + changed[end:]
    shutil.copytree(BASE, out)
    (out / REL).write_text(changed)
    subprocess.run(['clang-format', '-i', str(out / REL)], check=True)
    files = {str(p.relative_to(BASE)): sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    differences = [name for name, digest in files.items() if sha(out / name) != digest]
    if differences != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments' / ('q2-' + suffix + '.patch')
    patch.write_text(''.join(difflib.unified_diff(
        original.splitlines(True), (out / REL).read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    result = dict(
        scope='HC160 dispatch-proven fixed dimensions; no runtime evidence yet',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
        base_sha256=expected, candidate_sha256=sha(out / REL),
        patch_sha256=sha(patch), base_files=files, changed_files=differences,
        geometry='Unchanged BM160/BN128/BK2/WM5/WN4, 640 threads',
        mechanism='Constant-propagate dispatch-proven M320/K10240 inside this specialization',
        hoist_inactive_lane_initialization=args.hoist_zero,
        arithmetic='Original F16 operands, two ordered K16 sums and final F32 addition',
        allocation_bytes_added=0, numerical_limits_changed=False, promoted=False)
    (ROOT / 'config' / ('q2-' + suffix + '-source.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'base_files'}))


if __name__ == '__main__':
    main()
