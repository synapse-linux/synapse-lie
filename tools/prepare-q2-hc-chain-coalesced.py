#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Distribute paired-wave HC stage fetches across all 512 threads."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-chain-waves'
OUT = ROOT / '.deps/gufo-q2-bench-hc-chain-coalesced'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def wrap_lambda(body, declaration, branch):
    start = body.index(declaration) + len(declaration)
    end = body.index('\n  };', start)
    return body[:start] + '\n    if constexpr (kChunkedHcDown) {\n' + branch + \
        '    } else {\n' + body[start:end] + '\n    }' + body[end:]


def main():
    original = (BASE / REL).read_text()
    if hashlib.sha256(original.encode()).hexdigest() != '7c4721b5e2b37e8a7a2a0b9b7cc180ab0223b602e1fdff8443b83cdd2180d9a3':
        raise ValueError('Prepared paired-wave base changed')
    begin = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', begin)
    body = original[begin:end]
    anchor = '  constexpr int kBPer = (kBUnits + kBlockThreads - 1) / kBlockThreads;'
    if body.count(anchor) != 1:
        raise ValueError('Unexpected stage geometry')
    body = body.replace(anchor, anchor + '''
  // Only the measured original-F16 HC down specialization changes fetch
  // ownership. Nearby lanes load nearby uint4 chunks, instead of assigning
  // all four chunks of a K32 row to one lane. LDS and math stay unchanged.
  constexpr bool kChunkedHcDown = kHalfWeights && !kHcMix && !kSsmConv &&
                                  !kAttention && BM == 64 && BN == 128 &&
                                  BK == 2 && WM == 2 && WN == 4 &&
                                  kRowGroup == 5;
  constexpr int kAChunkPer = (kAUnits * 4 + kBlockThreads - 1) / kBlockThreads;
  constexpr int kBChunkPer = (kBUnits * 4 + kBlockThreads - 1) / kBlockThreads;
''')
    array_anchor = '  uint4 b_data[kBPer][4];'
    if body.count(array_anchor) != 1:
        raise ValueError('Unexpected preload arrays')
    body = body.replace(array_anchor, array_anchor + '''
  uint4 a_chunk[kChunkedHcDown ? kAChunkPer : 1];
  uint4 b_chunk[kChunkedHcDown ? kBChunkPer : 1];
''')
    body = wrap_lambda(body, '  const auto fetch_stage = [&](int kb0) {', '''
#pragma unroll
      for (int p = 0; p < kAChunkPer; ++p) {
        const int chunk = p * kBlockThreads + tid;
        const int unit = chunk / 4;
        const int row = r_block + unit / BK;
        const int kb = kb0 + unit % BK;
        if (unit < kAUnits && row < m_i && kb < num_kb) {
          const auto* src = reinterpret_cast<const uint4*>(w_bytes +
              (static_cast<std::size_t>(row) * num_kb + kb) * 64);
          a_chunk[p] = src[chunk & 3];
        } else {
          a_chunk[p] = make_uint4(0u, 0u, 0u, 0u);
        }
      }
#pragma unroll
      for (int p = 0; p < kBChunkPer; ++p) {
        const int chunk = p * kBlockThreads + tid;
        const int unit = chunk / 4;
        const int token = t_block + unit / BK;
        const int kb = kb0 + unit % BK;
        if (unit < kBUnits && token < static_cast<int>(batch) && kb < num_kb) {
          const auto* src = reinterpret_cast<const uint4*>(
              x + static_cast<std::size_t>(token) * k + kb * 32);
          b_chunk[p] = src[chunk & 3];
        } else {
          b_chunk[p] = make_uint4(0u, 0u, 0u, 0u);
        }
      }
''')
    body = wrap_lambda(body, '  const auto commit_stage = [&]() {', '''
#pragma unroll
      for (int p = 0; p < kAChunkPer; ++p) {
        const int chunk = p * kBlockThreads + tid;
        const int unit = chunk / 4;
        if (unit < kAUnits) {
          const int row = unit / BK;
          s_a[unit % BK][row][swizzle(row, chunk & 3)] = a_chunk[p];
        }
      }
#pragma unroll
      for (int p = 0; p < kBChunkPer; ++p) {
        const int chunk = p * kBlockThreads + tid;
        const int unit = chunk / 4;
        if (unit < kBUnits) {
          const int token = unit / BK;
          s_b[unit % BK][token][swizzle(token, chunk & 3)] = b_chunk[p];
        }
      }
''')
    shutil.copytree(BASE, OUT)
    path = OUT / REL
    path.write_text(original[:begin] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
               and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments/q2-hc-chain-coalesced.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        path.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    result = dict(scope='Static preparation only; GPU replay and performance unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                  changed_files=changed, file_count=sum(p.is_file() for p in BASE.rglob('*')),
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(path), patch_sha256=sha(patch),
                  mechanism='HC down 16-byte coalesced global stage fetches; original LDS, tile, ordered K16 chains and epilogue retained',
                  stage_chunks_per_thread=dict(weights=1, activations=2),
                  model_conversion=False)
    (ROOT / 'config/q2-hc-chain-coalesced-source.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Prepared coalesced HC down source:', changed)


if __name__ == '__main__':
    main()
