#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare exact Q8 integer-half pair lookup on the measured compact provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
TABLE = 'src/models/qwen38_flash_next/kernels/rocm/lie_q8_halfpair.inc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(path.relative_to(folder)): sha(path)
            for path in sorted(folder.rglob('*')) if path.is_file()}


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Changed source anchor: ' + old[:80])
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT / 'config/q2-iq2-halfbyte-perm-formatted-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-halfbyte-perm']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured compact provider inventory changed')
    original = (base / REL).read_text()
    halves = [int.from_bytes(struct.pack('<e', code if code < 128 else code - 256),
                             'little') for code in range(256)]
    pairs = []
    for code in range(65536):
        bits = halves[code & 255] | (halves[code >> 8] << 16)
        # Independent magic construction is exact: each encoded integer is
        # in [-128,127], and 1152+q is representable with unit half spacing.
        for lane in range(2):
            raw = (code >> (8 * lane)) & 255
            value = raw if raw < 128 else raw - 256
            constructed = struct.unpack('<e', struct.pack('<H', 0x6400 | (raw ^ 128)))[0] - 1152
            if constructed != value or (bits >> (16 * lane)) & 65535 != halves[raw]:
                raise ValueError('Q8 half pair differs from original integer value')
        pairs.append(bits)
    table = ('// SPDX-License-Identifier: MIT\n'
             '// Generated exact signed int8 pairs; no model weights or upstream\n'
             '// codebook are copied. Index is two original little-endian bytes.\n'
             'static const __device__ std::uint32_t kQ8HalfPairs[65536] = {\n')
    table += ''.join('    ' + ', '.join(f'0x{value:08x}U' for value in pairs[index:index + 8]) + ',\n'
                     for index in range(0,65536,8))
    table += '};\n'
    helper = '''// SPDX-License-Identifier: MIT
#include "src/models/qwen38_flash_next/kernels/rocm/lie_q8_halfpair.inc"

// The exact signed integer halves replace the parent's magic half addition.
// Keep its rounded scale and packed FMA, including signed zero/NaN behavior.
__device__ __forceinline__ void Q8HalfPairLutToHalves(
    std::uint32_t bytes, __half2 scale2, __half2 bias2, __half2& lo,
    __half2& hi) {
  const std::uint32_t p0 = kQ8HalfPairs[bytes & 0xFFFFU];
  const std::uint32_t p1 = kQ8HalfPairs[bytes >> 16U];
  lo = __hfma2(__builtin_bit_cast(__half2, p0), scale2, bias2);
  hi = __hfma2(__builtin_bit_cast(__half2, p1), scale2, bias2);
}

'''
    signature = 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,'
    changed = once(original, signature, helper + signature)
    changed = once(changed,
                   '''          CodesToHalves(words[i] ^ 0x80808080U, magic, scale2, zero2, h[2 * i],
                        h[2 * i + 1]);''',
                   '''          Q8HalfPairLutToHalves(words[i], scale2, zero2, h[2 * i],
                                h[2 * i + 1]);''')
    source = ROOT / '.deps/gufo-q2-q8-halfpair-run'
    patch = ROOT / 'experiments/q2-q8-halfpair.patch'
    manifest = ROOT / 'config/q2-q8-halfpair-source.json'
    if any(path.exists() for path in (source, patch, manifest)):
        raise ValueError('Refusing to replace retained candidate')
    formatter = ['/opt/rocm/llvm/bin/clang-format', '--style=file:' + str(base / '.clang-format')]
    formatted = {}
    for name, text in ((REL, changed), (TABLE, table)):
        result = subprocess.run(formatter + ['--assume-filename=' + str(base / name)],
                                input=text, text=True, capture_output=True)
        if result.returncode:
            raise ValueError('Formatting failed: ' + result.stderr)
        formatted[name] = result.stdout
    shutil.copytree(base, source)
    for name, text in formatted.items():
        (source / name).write_text(text)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1026 or delta != sorted((REL, TABLE)):
        raise ValueError('Unexpected source delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in (REL, TABLE):
            stream.write(''.join(difflib.unified_diff(
                (original if name == REL else '').splitlines(True), formatted[name].splitlines(True),
                fromfile='a/' + name, tofile='b/' + name)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
                   parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
                   measured_parent='config/q2-iq2-halfbyte-model-results.json',
                   measured_parent_sha256=sha(ROOT / 'config/q2-iq2-halfbyte-model-results.json'),
                   control_include='experiments/q2-q8-grouped-control.inc',
                   control_include_sha256=sha(ROOT / 'experiments/q2-q8-grouped-control.inc'),
                   patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
                   table_file=TABLE, table_sha256=sha(source / TABLE), table_bytes=65536*4,
                   scalar_integer_format_checks=65536*2,
                   numerical_contract='Exact signed int8 half operands; original scale half bits, packed half FMA, '
                                      'ordered K16 WMMA, activation/LDS/epilogue and SSM convolution unchanged.',
                   affected='Q8-weight branch of DenseF16GEMMKernel only; F16-weight, routed IQ2/Q2 and W8A8 unchanged.',
                   risks='Additional 256KiB device table and dependent indexed loads may outweigh fewer '
                         'conversion instructions or compete with active weight/activation caches.',
                   additional_runtime_allocations=0, additional_streams=0,
                   full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-q8-halfpair-source.v1',
                       variants={'q8-halfpair': variant}, gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(source_files=len(files), changed_files=delta,
                         table_bytes=variant['table_bytes'], integer_checks=65536*2, gpu_run=False)))


if __name__ == '__main__':
    main()
