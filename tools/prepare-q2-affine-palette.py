#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reuse the four Q2 affine values within each sixteen-element group."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-decode16'
OUT = ROOT / '.deps/gufo-q2-bench-affine-palette'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'be038fa353b26feaa45aa9fde8d23bcb03a454639edeb6a5634f7d72f7ef4a37'


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
    body = once(body, '''        __half2 h[16];
#pragma unroll
        for (int i = 0; i < 8; ++i) {
          if constexpr (kQ2) {''', '''        __half2 h[16];
        uint2 palette[kQ2 && kPacked ? 2 : 1];
        if constexpr (kQ2 && kPacked) {
          // A sixteen-element affine group has only four possible weights.
          // Preserve each F32 FMA and F16 rounding, then select its exact
          // half bits instead of repeating the affine for every element.
#pragma unroll
          for (int part = 0; part < 2; ++part) {
            const auto* affine = reinterpret_cast<const float*>(s_scale) +
                                 2 * (((2 * kb + part) * BM) + row);
            const float d = affine[0], bias = affine[1];
            palette[part] = make_uint2(
                __builtin_bit_cast(std::uint32_t, __floats2half2_rn(
                    fmaf(0.0F, d, bias), fmaf(1.0F, d, bias))),
                __builtin_bit_cast(std::uint32_t, __floats2half2_rn(
                    fmaf(2.0F, d, bias), fmaf(3.0F, d, bias))));
          }
        }
#pragma unroll
        for (int i = 0; i < 8; ++i) {
          if constexpr (kQ2 && kPacked) {
            const uint2 values = palette[i / 4];
            // Duplicate each two-bit code into the two byte selectors for
            // its half; perm indices 0..3 read the second source word.
            const auto lo = (__builtin_amdgcn_perm(nib[i], nib[i],
                                                  0x01010000U) << 1U) |
                            0x01000100U;
            const auto hi = (__builtin_amdgcn_perm(nib[i], nib[i],
                                                  0x03030202U) << 1U) |
                            0x01000100U;
            h[2 * i] = __builtin_bit_cast(
                __half2, __builtin_amdgcn_perm(values.y, values.x, lo));
            h[2 * i + 1] = __builtin_bit_cast(
                __half2, __builtin_amdgcn_perm(values.y, values.x, hi));
          } else if constexpr (kQ2) {''')
    shutil.copytree(BASE, OUT)
    path = OUT / REL
    path.write_text(original[:start] + body + original[end:])
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / 'experiments/q2-affine-palette.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), path.read_text().splitlines(True),
                                                fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(scope='Static preparation only; GPU replay and benefit unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                  base_sha256=sha(BASE / REL), candidate_sha256=sha(path),
                  patch_sha256=sha(patch), changed_files=changed,
                  mechanism='Compute four F16 affine values per Q2 group and select their bytes with register permutes',
                  unchanged='Original model bytes, LDS plan, activation planes, WMMA order and residual correction; raw-input control and HC16 decode unchanged',
                  numeric_contract='Exact GPU operator/model replay required; constant folding must preserve original rounded values')
    (ROOT / 'config/q2-affine-palette-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared Q2 affine palette:', changed)


if __name__ == '__main__':
    main()
