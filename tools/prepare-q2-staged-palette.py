#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Share four rounded Q2 weight values in the existing eight-byte affine slot."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-staged-palette'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected retained source: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Retained paired-HC-up source changed')
    original = (BASE / REL).read_text()
    old = '''          // Keep the affine in F32. Rounding its coefficients separately
          // to F16 amplifies cancellation in small routed outputs.
          auto* affine = reinterpret_cast<float*>(s_scale) +
                         2 * (((2 * f_c + part) * BM) + row);
          affine[0] = d;
          affine[1] = b;'''
    new = '''          if constexpr (kPacked) {
            // Materialize the same rounded F32 coefficients before affine
            // evaluation, then share four exact half values in the old
            // eight-byte slot. Both half-waves consume the same palette.
            float rounded_d = d, rounded_b = b;
            asm volatile("" : "+v"(rounded_d), "+v"(rounded_b));
            reinterpret_cast<uint2*>(s_scale)[((2 * f_c + part) * BM) + row] =
                make_uint2(
                    __builtin_bit_cast(std::uint32_t, __floats2half2_rn(
                        fmaf(0.0F, rounded_d, rounded_b),
                        fmaf(1.0F, rounded_d, rounded_b))),
                    __builtin_bit_cast(std::uint32_t, __floats2half2_rn(
                        fmaf(2.0F, rounded_d, rounded_b),
                        fmaf(3.0F, rounded_d, rounded_b))));
          } else {
            // The raw-input control keeps the original F32 affine slot.
            auto* affine = reinterpret_cast<float*>(s_scale) +
                           2 * (((2 * f_c + part) * BM) + row);
            affine[0] = d;
            affine[1] = b;
          }'''
    changed = once(original, old, new)
    start = changed.index('        if constexpr (kQ2 && kPacked) {\n          // A sixteen-element')
    end = changed.index('\n#pragma unroll\n        for (int i = 0; i < 8; ++i)', start)
    changed = changed[:start] + '''        if constexpr (kQ2 && kPacked) {
          // Four half values occupy exactly the former two-F32 affine slot.
          // Producer evaluation removes duplicate conversion in each half-wave.
#pragma unroll
          for (int part = 0; part < 2; ++part) {
            palette[part] = reinterpret_cast<const uint2*>(s_scale)
                [((2 * kb + part) * BM) + row];
          }
        }''' + changed[end:]
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                       and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-staged-palette.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; GPU exactness and performance unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        changed_files=inventory, base_sha256=sha(BASE / REL), candidate_sha256=sha(target),
        patch_sha256=sha(patch),
        mechanism='Packed-Q2 producer stores four F16 palette values in the former F32 scale/bias slot; consumers load the same bits instead of computing the palette twice',
        arithmetic='Original F32 coefficient rounding, four F32 affine FMAs and F16 rounding; both activation planes, WMMA order and residual correction unchanged',
        unchanged='Original encoded models, LDS byte count/layout, token tiles, raw-F32-input control, IQ2, HC, scalar decode, PLE and public ABI',
        qualification='Exact complete operator and saved model output replay required, plus independent FP64 checks at unchanged limits',
        model_conversion=False, persistent_decoded_weight_cache=False)
    (ROOT / 'config/q2-staged-palette-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
