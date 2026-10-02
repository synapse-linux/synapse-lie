#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain packed Q2 code bytes across the two stages consuming their bit planes."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
OUT = ROOT / '.deps/gufo-q2-bench-code-reuse'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '92faa287e2b5681d16f0f54c2f99a3eba0a14c5faaf398e631f8a12b7548cbad'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected measured source: ' + old[:90])
    return text.replace(old, new)


def main():
    original = (BASE / REL).read_text()
    if hashlib.sha256((BASE / REL).read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Measured base changed')
    start = original.index('template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    end = original.index('\n__global__', start)
    body = original[start:end]
    body = once(body, '  uint4 code_cache[kWaveRowTiles][4];', '''  uint4 code_cache[kWaveRowTiles][4];
  // Q2's 32 stored bytes contain four K32 groups in separate 2-bit planes.
  // A thread consumes two of those groups in successive K64 stages. Retain
  // the original bytes instead of fetching the same range for both stages.
  uint4 q2_code_cache[kQ2 && kPacked ? kWaveRowTiles : 1][2];''')
    body = once(body, '''        __builtin_memcpy(&f_codes[u], codes, 16);
        __builtin_memcpy(&f_codes_hi[u], codes + 16, 16);''', '''        if constexpr (kPacked) {
          if (kb0 % 4 == 0) {
            __builtin_memcpy(&q2_code_cache[u][0], codes, 16);
            __builtin_memcpy(&q2_code_cache[u][1], codes + 16, 16);
          }
          f_codes[u] = q2_code_cache[u][0];
          f_codes_hi[u] = q2_code_cache[u][1];
        } else {
          __builtin_memcpy(&f_codes[u], codes, 16);
          __builtin_memcpy(&f_codes_hi[u], codes + 16, 16);
        }''')
    shutil.copytree(BASE, OUT)
    path = OUT / REL
    path.write_text(original[:start] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / 'experiments/q2-code-reuse.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), path.read_text().splitlines(True),
                                                 fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation only; GPU replay and benefit unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(path),
                  patch_sha256=sha(patch), changed_files=changed,
                  mechanism='Keep the original 32 Q2 code bytes per producer thread across adjacent K64 stages; halve their source fetches',
                  unchanged='Original model bytes, affine scale fetch/rounding, LDS plan, two activation planes, WMMA order and residual correction; raw-input control unchanged')
    (ROOT / 'config/q2-code-reuse-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared packed Q2 code reuse:', changed)


if __name__ == '__main__':
    main()
