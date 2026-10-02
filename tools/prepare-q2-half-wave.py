#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Split Q2 affine decoding between paired half-waves, without expanding LDS."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exchange', choices=['shuffle', 'permlane'], default='shuffle')
    args = parser.parse_args()
    name = 'q2-half-wave' + ('-permlane' if args.exchange == 'permlane' else '')
    out = ROOT / '.deps' / ('gufo-' + name.replace('q2-', 'q2-bench-', 1))
    original = (BASE / REL).read_text()
    begin = original.index('template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    end = original.index('\n__global__', begin)
    body = original[begin:end]
    compute = body.index('  const auto compute_stage = [&]() {')
    start = body.index('        const __half2 sb =', compute)
    stop = body.index('      }\n#pragma unroll\n      for (int j = 0; j < kTokTiles; ++j)', start)
    current = body[start:stop]
    if current.count('__builtin_memcpy(&a_lo[u], &h[0], 32);') != 1:
        raise ValueError('Unexpected measured decode body')
    replacement = '''        if constexpr (kQ2 && kPacked) {
          // Paired lanes need identical A operands, but only one half-wave
          // has to decode each K16 half. Exchange the already rounded bits.
          // Keep the original F32 affine plane, code plane and WMMA order.
          const uint4 packed = s_codes[swizzle(row, 2 * kb + half_id)];
          const std::uint32_t words[4] = {packed.x, packed.y, packed.z, packed.w};
          const auto* affine = reinterpret_cast<const float*>(s_scale) +
                               2 * (((2 * kb + half_id) * BM) + row);
          const float d = affine[0], bias = affine[1];
          __half2 h[8];
#pragma unroll
          for (int i = 0; i < 4; ++i) {
            h[2 * i] = __floats2half2_rn(
                fmaf(float(words[i] & 3U), d, bias),
                fmaf(float((words[i] >> 8U) & 3U), d, bias));
            h[2 * i + 1] = __floats2half2_rn(
                fmaf(float((words[i] >> 16U) & 3U), d, bias),
                fmaf(float((words[i] >> 24U) & 3U), d, bias));
          }
          std::uint32_t lo[8], hi[8];
#pragma unroll
          for (int i = 0; i < 8; ++i) {
            const auto own = __builtin_bit_cast(std::uint32_t, h[i]);
            const auto peer = __shfl_xor(own, 16, 32);
            lo[i] = half_id == 0 ? own : peer;
            hi[i] = half_id == 0 ? peer : own;
          }
          __builtin_memcpy(&a_lo[u], lo, 32);
          __builtin_memcpy(&a_hi[u], hi, 32);
        } else {
''' + current + '        }\n'
    if args.exchange == 'permlane':
        replacement = replacement.replace(
            'const auto peer = __shfl_xor(own, 16, 32);',
            '''const auto peer = __builtin_amdgcn_permlanex16(
                own, own, 0x76543210U, 0xFEDCBA98U, false, false);''')
    body = body[:start] + replacement + body[stop:]
    shutil.copytree(BASE, out)
    path = out / REL
    path.write_text(original[:begin] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
               and p.read_bytes() != (out / p.relative_to(BASE)).read_bytes()]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments' / (name + '.patch')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        path.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation only; GPU numerical equivalence and benefit unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
                  changed_files=changed, base_sha256=sha(BASE / REL), candidate_sha256=sha(path),
                  patch_sha256=sha(patch),
                  exchange=args.exchange,
                  mechanism='Paired half-waves decode opposite K16 halves, exchange rounded F16 bits; original LDS layout and WMMA accumulation order retained')
    (ROOT / 'config' / (name + '-source.json')).write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared Q2 paired half-wave decode:', changed)


if __name__ == '__main__':
    main()
