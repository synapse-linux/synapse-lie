#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare compact IQ2 half-bit bytes without expanding the LDS weight plane."""
import argparse
import difflib
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
TABLE_REL = 'src/models/qwen38_flash_next/kernels/rocm/mmq/ggml-common.h'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(path.relative_to(folder)): sha(path)
            for path in sorted(folder.rglob('*')) if path.is_file()}


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Retained source anchor changed: ' + before[:80])
    return text.replace(before, after, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decode', choices=('perm', 'shift'), required=True)
    parser.add_argument('--format-main-header', action='store_true',
                        help='Separate retained source with filename-aware include formatting')
    args = parser.parse_args()
    parent_path = ROOT / 'config/q2-hc-moe-deferred-source.json'
    parent = json.loads(parent_path.read_text())['variants']['hc-moe-deferred']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent provider changed')
    original = (base / REL).read_text()
    tables = (base / TABLE_REL).read_text()
    match = re.search(r'GGML_TABLE_BEGIN\(uint64_t, iq2xxs_grid, 256\)(.*?)GGML_TABLE_END\(\)',
                      tables, re.S)
    if match is None:
        raise ValueError('Pinned IQ2 table missing')
    grid = [int(value, 16) for value in re.findall(r'0x[0-9a-fA-F]+', match[1])]
    if len(grid) != 256:
        raise ValueError('IQ2 codebook changed')
    high = {8: 0x48, 25: 0x4e, 43: 0x51}
    encoded = []
    scalar_checks = packed_checks = 0
    for entry in grid:
        values = [(entry >> (8 * lane)) & 255 for lane in range(8)]
        if any(value not in high for value in values):
            raise ValueError('Unknown codebook magnitude')
        encoded.append(sum(high[value] << (8 * lane) for lane, value in enumerate(values)))
        for sign in range(128):
            signs = sign | ((sign.bit_count() & 1) << 7)
            for lane, value in enumerate(values):
                byte = high[value] ^ (0x80 if (signs >> lane) & 1 else 0)
                selector = byte & 3
                low = (0, 0x60, 0x40, 0)[selector]
                shifted = (selector | ((selector & 1) << 1)) << 5
                expected = int.from_bytes(struct.pack('<e', -value if (signs >> lane) & 1 else value), 'little')
                if low != shifted or (byte << 8) | low != expected:
                    raise ValueError('Half-bit representation differs')
                scalar_checks += 1
    for values in itertools.product((8, -8, 25, -25, 43, -43), repeat=4):
        word = sum((high[abs(value)] ^ (0x80 if value < 0 else 0)) << (8 * lane)
                   for lane, value in enumerate(values))
        selectors = word & 0x03030303
        shifted_low = (selectors | ((selectors & 0x01010101) << 1)) << 5
        for lane, value in enumerate(values):
            low = (shifted_low >> (8 * lane)) & 255
            byte = (word >> (8 * lane)) & 255
            expected = int.from_bytes(struct.pack('<e', value), 'little')
            if (byte << 8) | low != expected:
                raise ValueError('Packed shift crossed byte boundaries')
        packed_checks += 1
    table = ('// SPDX-License-Identifier: MIT\n'
             '// Lossless half high-byte encoding of the independently pinned\n'
             '// IQ2 codebook above; its original table and notices remain.\n'
             'static const __device__ std::uint64_t kIq2HalfHighGrid[256] = {\n')
    table += ''.join('    ' + ', '.join(f'0x{value:016x}ULL' for value in encoded[index:index + 4]) + ',\n'
                     for index in range(0, 256, 4))
    table += '};\n\n'
    low = ('__builtin_amdgcn_perm(0x00406000U, 0x00406000U, selectors)'
           if args.decode == 'perm' else '(selectors | ((selectors & 0x01010101U) << 1U)) << 5U')
    helper = '''/// Each IQ2 magnitude is exactly8,25 or43. Their F16 high bytes
/// are48,4e or51; the low bytes are00,40 or60. The sign stays in bit7.
/// Keep one byte per weight in LDS and reconstruct the original F16 bits.
__device__ __forceinline__ void Iq2HalfBytesToHalves(
    std::uint32_t high, __half2 scale2, __half2 bias2, __half2& lo,
    __half2& hi) {
  const std::uint32_t selectors = high & 0x03030303U;
  const std::uint32_t low = ''' + low + ''';
  const std::uint32_t p0 =
      __builtin_amdgcn_perm(low, high, 0x01050004U);
  const std::uint32_t p1 =
      __builtin_amdgcn_perm(low, high, 0x03070206U);
  // These are the exact signed magnitude operands of the original half add.
  // Retain the same rounded scale, packed half FMA and zero bias.
  lo = __hfma2(__builtin_bit_cast(__half2, p0), scale2, bias2);
  hi = __hfma2(__builtin_bit_cast(__half2, p1), scale2, bias2);
}

'''
    changed = once(original, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,',
                   table + helper + 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    changed = once(changed, 'reinterpret_cast<const uint2*>(iq2xxs_grid)[code];',
                   'reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];')
    changed = once(changed,
                   '''        // masks and a four-bit scale. All codebook magnitudes are 8/25/43;
        // packed xor-plus-one negation therefore cannot carry across bytes.''',
                   '''        // masks and a four-bit scale. Store the lossless F16 high bytes;
        // applying signs changes bit7 without integer negation or byte carry.''')
    changed = once(changed,
                   '''          signed_codes[part] =
              make_uint2((magnitude.x ^ mask.x) + (mask.x & 0x01010101U),
                         (magnitude.y ^ mask.y) + (mask.y & 0x01010101U));''',
                   '''          signed_codes[part] =
              make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                         magnitude.y ^ (mask.y & 0x80808080U));''')
    changed = once(changed,
                   '            nib[i] = kSigned ? words[i] ^ 0x80808080U : words[i];',
                   '            nib[i] = (kSigned && !kIQ2) ? words[i] ^ 0x80808080U : words[i];')
    changed = once(changed,
                   '''          } else {
            CodesToHalves(nib[i], magic, scale2, bias2, h[2 * i], h[2 * i + 1]);''',
                   '''          } else if constexpr (kIQ2) {
            Iq2HalfBytesToHalves(nib[i], scale2, bias2, h[2 * i], h[2 * i + 1]);
          } else {
            CodesToHalves(nib[i], magic, scale2, bias2, h[2 * i], h[2 * i + 1]);''')
    tag = 'q2-iq2-halfbyte-' + args.decode
    if args.format_main_header:
        tag += '-formatted'
    source = ROOT / '.deps' / ('gufo-' + tag + '-run')
    patch = ROOT / 'experiments' / (tag + '.patch')
    manifest = ROOT / 'config' / (tag + '-source.json')
    if any(path.exists() for path in (source, patch, manifest)):
        raise ValueError('Refusing to overwrite retained source')
    formatter = ['/opt/rocm/llvm/bin/clang-format', '--style=file:' + str(base / '.clang-format')]
    if args.format_main_header:
        formatter.append('--assume-filename=' + str(base / REL))
    formatted = subprocess.run(formatter, input=changed, text=True, capture_output=True)
    if formatted.returncode:
        raise ValueError('Provider formatting failed: ' + formatted.stderr)
    changed = formatted.stdout
    shutil.copytree(base, source)
    (source / REL).write_text(changed)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True), fromfile='a/' + REL, tofile='b/' + REL)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
                   parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
                   measured_parent='config/q2-hc-moe-deferred-model-results.json',
                   measured_parent_sha256=sha(ROOT / 'config/q2-hc-moe-deferred-model-results.json'),
                   official_table_file=TABLE_REL, official_table_sha256=sha(base / TABLE_REL),
                   derived_table_bytes=2048, decoder=args.decode, scalar_format_checks=scalar_checks,
                   filename_aware_formatting=args.format_main_header,
                   packed_format_checks=packed_checks, patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
                   stage_layout_unchanged=True, additional_allocations=0, additional_streams=0,
                   numerical_contract='Exact signed magnitude F16 bits, original rounded scale and half FMA; '
                                      'unchanged ordered K16 WMMA, routing, tails and SwiGLU.',
                   risks='Extra integer/perm work may cost more than packed half add; static counts are not timings.',
                   gpu_run=False, full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-halfbyte-source.v1',
                       variants={'iq2-halfbyte-' + args.decode: variant}, gpu_run=False, goal_met=False),
                  stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(source_files=len(files), changed_files=delta, decoder=args.decode,
                          scalar_format_checks=scalar_checks, packed_format_checks=packed_checks,
                          gpu_run=False, goal_met=False)))


if __name__ == '__main__':
    main()
