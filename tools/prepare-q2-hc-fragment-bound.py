#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bound HC down LDS fragment lifetimes without changing arithmetic or tiles."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '4de114a41d58e2b6f74038abfbf27bef8dc285dadf4b95ef69ae3b51b6b8a9fe'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('token', 'k'), default='token')
    args = parser.parse_args()
    variant = 'hc-fragment-bound' if args.stage == 'token' else 'hc-stage-bound'
    out = ROOT / ('.deps/gufo-q2-bench-' + variant)
    original = (BASE / REL).read_text()
    if hashlib.sha256((BASE / REL).read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Measured affine-palette base changed')
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\n  if constexpr (kAttention)', start)
    body = original[start:end]
    anchor = '''      for (int j = 0; j < kWaveTokTiles; ++j) {
        const int t = (((wave_tok * kWaveTokTiles) + j) * 16) + sub_lane;'''
    replacement = '''      for (int j = 0; j < kWaveTokTiles; ++j) {
        if constexpr (kHalfWeights && !kHcMix && BM == 64 && BN == 128 &&
                      BK == 2 && WM == 2 && WN == 4 && kRowGroup == 5) {
          // Keep the next token tile's LDS fragments out of the current
          // tile's live register set. No device barrier or arithmetic change.
          asm volatile("" ::: "memory");
        }
        const int t = (((wave_tok * kWaveTokTiles) + j) * 16) + sub_lane;'''
    if args.stage == 'k':
        anchor = '''    for (int kb = 0; kb < BK; ++kb) {
      v16h a_lo[kWaveRowTiles];'''
        replacement = '''    for (int kb = 0; kb < BK; ++kb) {
      if constexpr (kHalfWeights && !kHcMix && BM == 64 && BN == 128 &&
                    BK == 2 && WM == 2 && WN == 4 && kRowGroup == 5) {
        // Keep later K32 fragments out of this stage's live register set.
        // This compiler boundary changes no device barrier or arithmetic.
        asm volatile("" ::: "memory");
      }
      v16h a_lo[kWaveRowTiles];'''
    if body.count(anchor) != 1:
        raise ValueError('Unexpected HC fragment load loop')
    body = body.replace(anchor, replacement)
    shutil.copytree(BASE, out)
    path = out / REL
    path.write_text(original[:start] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (out / p.relative_to(BASE)).read_bytes())
    if changed != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / ('experiments/q2-' + variant + '.patch')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), path.read_text().splitlines(True),
                                                fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation; runtime benefit and exact replay unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(path),
                  patch_sha256=sha(patch), changed_files=changed,
                  mechanism='Compiler memory barrier before each HC down ' + args.stage + ' fragment load',
                  dispatch='Existing F16 DenseF16GEMM 64x128 BK2 WM2 WN4 row-group5 only',
                  unchanged='Original weights, LDS allocation, tiles, split accumulation chains and scalar HC16 decode; other kernels unaffected',
                  numeric_contract='Exact component/model replay, with unchanged independent operator thresholds')
    (ROOT / ('config/q2-' + variant + '-source.json')).write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared bounded HC down fragment lifetimes:', args.stage, changed)


if __name__ == '__main__':
    main()
