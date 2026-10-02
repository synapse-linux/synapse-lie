#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage decoded Q2 weights once, retaining the packed activation arithmetic."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
OUT = ROOT / '.deps/gufo-q2-bench-staged-weights'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Unexpected measured source: ' + before[:80])
    return source.replace(before, after)


def main():
    shutil.copytree(BASE, OUT)
    original = (BASE / REL).read_text()
    start = original.index('template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    end = original.index('\n__global__', start)
    body = original[start:end]
    body = once(body, '  constexpr bool kQ2 = kType == WeightType::kQ2_K;',
                '''  constexpr bool kQ2 = kType == WeightType::kQ2_K;
  // Only the measured packed-Q2 path changes. Decode each original weight
  // once in the producer, then share that same F16 value across WMMA lanes.
  constexpr bool kStageQ2 = kQ2 && kPacked;''')
    body = once(body, '  constexpr int kChunks = (kSigned || kQ2) ? 2 * BK : BK;',
                '  constexpr int kChunks = kStageQ2 ? 4 * BK : (kSigned || kQ2) ? 2 * BK : BK;')
    body = once(body, '  constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;',
                '  constexpr int kScaleBytes = kStageQ2 ? 0 : (kQ2 ? 4 : 1) * BK * BM * 4;')
    body = once(body,
                '           (c ^ (kChunks == 4 ? ((row >> 1) & 3) : ((row >> 2) & 1)));',
                '''           (c ^ (kChunks == 8 ? ((row >> 1) & 7)
                : kChunks == 4 ? ((row >> 1) & 3) : ((row >> 2) & 1)));''')
    body = once(body, '''      if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''',
                '''      if constexpr (kStageQ2) {
        // Two producer lanes own the two K32 halves of a row. Preserve the
        // F32 affine coefficients formerly materialized in LDS before FMA.
        const __half2 dm = __builtin_bit_cast(__half2, f_dm[u]);
        const std::uint32_t words[8] = {
            f_codes[u].x, f_codes[u].y, f_codes[u].z, f_codes[u].w,
            f_codes_hi[u].x, f_codes_hi[u].y, f_codes_hi[u].z, f_codes_hi[u].w};
#pragma unroll
        for (int part = 0; part < 2; ++part) {
          const unsigned sm = (f_high[u] >> (8 * part)) & 0xFFU;
          float d = f_live[u] ? __low2float(dm) * float(sm & 15U) : 0.0F;
          float b = f_live[u] ? -__high2float(dm) * float(sm >> 4U) : 0.0F;
          asm volatile("" : "+v"(d), "+v"(b));
          __half2 values[8];
#pragma unroll
          for (int i = 0; i < 4; ++i) {
            const std::uint32_t q = words[part * 4 + i];
            values[2 * i] = __floats2half2_rn(
                fmaf(float(q & 3U), d, b), fmaf(float((q >> 8U) & 3U), d, b));
            values[2 * i + 1] = __floats2half2_rn(
                fmaf(float((q >> 16U) & 3U), d, b),
                fmaf(float((q >> 24U) & 3U), d, b));
          }
          uint4 lo, hi;
          __builtin_memcpy(&lo, &values[0], 16);
          __builtin_memcpy(&hi, &values[4], 16);
          s_codes[swizzle(row, 4 * f_c + 2 * part)] = lo;
          s_codes[swizzle(row, 4 * f_c + 2 * part + 1)] = hi;
        }
      } else if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''')
    body = once(body, '''      if constexpr (kQ2) {
        const __half2 dm = __builtin_bit_cast(__half2, f_dm[u]);''',
                '''      if constexpr (kQ2 && !kStageQ2) {
        const __half2 dm = __builtin_bit_cast(__half2, f_dm[u]);''')
    # The old scale-generation else-chain must also skip staged Q2; that path
    # has no scale plane and has already decoded its original coefficients.
    body = once(body, '      } else if constexpr (kSigned) {',
                '      } else if constexpr (kSigned || kStageQ2) {')
    compute = body.index('  const auto compute_stage = [&]() {')
    a = body.index('        const __half2 sb =', compute)
    b = body.index('      }\n#pragma unroll\n      for (int j = 0; j < kTokTiles; ++j)', a)
    decode = body[a:b]
    body = body[:a] + '''        if constexpr (kStageQ2) {
          uint4 values[4];
#pragma unroll
          for (int c = 0; c < 4; ++c)
            values[c] = s_codes[swizzle(row, 4 * kb + c)];
          __builtin_memcpy(&a_lo[u], &values[0], 32);
          __builtin_memcpy(&a_hi[u], &values[2], 32);
        } else {
''' + decode + '        }\n' + body[b:]
    path = OUT / REL
    path.write_text(original[:start] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
               and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments/q2-staged-weights.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
                     path.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation only; numerical and GPU benefit unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                  files=sum(p.is_file() for p in BASE.rglob('*')), changed_files=changed,
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(path), patch_sha256=sha(patch),
                  mechanism='Packed Q2 only: one cooperative weight decode into LDS per stage; original activation planes and ordered WMMA accumulations unchanged',
                  persistent_weight_storage='Original Q2_K; no converted model or global dequantized cache')
    (ROOT / 'config/q2-staged-weights-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared packed-Q2 staged weights:', changed)


if __name__ == '__main__':
    main()
