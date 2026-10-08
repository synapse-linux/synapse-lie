#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fuse IQ2 sign/code lookups on the measured raw-prefetch parent."""
import difflib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
TABLE = 'src/models/qwen38_flash_next/kernels/rocm/lie_iq2_signed_grid.inc'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prepare = module('prepare-q2-q8-halfpair.py')
literal = module('prepare-q2-q8-grouped.py')
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once


def table_values(text, expression, count):
    match = re.search(expression, text, re.S)
    if not match:
        raise ValueError('Pinned table definition missing')
    values = [int(x, 16) for x in re.findall(r'0x[0-9a-fA-F]+', match[1])]
    if len(values) != count:
        raise ValueError('Pinned table count differs')
    return values


def main():
    parent_path = ROOT/'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    original = (base/REL).read_text()
    common = (base/'src/models/qwen38_flash_next/kernels/rocm/mmq/ggml-common.h').read_text()
    high = table_values(original, r'kIq2HalfHighGrid\[256\]\s*=\s*\{(.*?)\};', 256)
    grid = table_values(common, r'GGML_TABLE_BEGIN\(uint64_t, iq2xxs_grid, 256\)(.*?)GGML_TABLE_END', 256)
    signs = table_values(common, r'GGML_TABLE_BEGIN\(uint64_t, ksigns64, 128\)(.*?)GGML_TABLE_END', 128)
    fused = []
    for sign in range(128):
        parity_sign = sign | ((sign.bit_count() & 1) << 7)
        for code in range(256):
            value = high[code] ^ (signs[sign] & 0x8080808080808080)
            for lane in range(8):
                magnitude = (grid[code] >> (8*lane)) & 255
                expected = -magnitude if parity_sign & (1 << lane) else magnitude
                bits = int.from_bytes(struct.pack('<e', expected), 'little')
                high_byte = (value >> (8*lane)) & 255
                low_byte = {0x48: 0, 0x4e: 0x40, 0x51: 0x60}[high_byte & 127]
                if bits != (high_byte << 8) | low_byte:
                    raise ValueError('Independent parity/half encoding mismatch')
            fused.append(value)
    table = ('// SPDX-License-Identifier: MIT\n'
             '// Lossless encoding derived from independently pinned official Gufo\n'
             '// IQ2 tables. Original tables/notices remain; no model payload copied.\n'
             '// Index: (seven original sign bits << 8) | original grid code.\n'
             'static const __device__ std::uint64_t kIq2SignedHalfHighGrid[32768] = {\n')
    table += ''.join('    '+', '.join(f'0x{x:016x}ULL' for x in fused[i:i+4])+',\n'
                     for i in range(0, len(fused), 4))
    table += '};\n'
    changed = once(original, '/// Each IQ2 magnitude is exactly8,25 or43.',
                   '// SPDX-License-Identifier: MIT\n#include "'+TABLE+'"\n\n'
                   '/// Each IQ2 magnitude is exactly8,25 or43.')
    changed = once(changed,
        '''          const uint2 magnitude =
              reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          signed_codes[part] = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                          magnitude.y ^ (mask.y & 0x80808080U));''',
        '''          // One exact signed-code lookup replaces two loads and sign XOR.
          signed_codes[part] = reinterpret_cast<const uint2*>(
              kIq2SignedHalfHighGrid)[(sign << 8U) | code];''')
    source = ROOT/'.deps/gufo-q2-iq2-fused-grid-run'
    patch = ROOT/'experiments/q2-iq2-fused-grid.patch'
    manifest = ROOT/'config/q2-iq2-fused-grid-source.json'
    control = ROOT/'experiments/q2-iq2-fused-grid-control.inc'
    if any(p.exists() for p in (source, patch, manifest, control)):
        raise ValueError('Refusing to overwrite retained candidate')
    formatted = {}
    for name, text in ((REL, changed), (TABLE, table)):
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
            '--style=file:'+str(base/'.clang-format'), '--assume-filename='+str(base/name)],
            input=text, text=True, capture_output=True)
        if result.returncode:
            raise ValueError('Formatting failed: '+result.stderr)
        formatted[name] = result.stdout
    shutil.copytree(base, source)
    for name, text in formatted.items():
        (source/name).write_text(text)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1026 or delta != sorted((REL, TABLE)):
        raise ValueError('Unexpected provider delta')
    kernel = literal.function(original, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    with control.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n// Literal measured IQ2 raw-prefetch parent; numerical helpers unchanged.\n')
        stream.write(kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2FusedGridControlKernel')+'\n')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in (REL, TABLE):
            stream.write(''.join(difflib.unified_diff((original if name == REL else '').splitlines(True),
                formatted[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-raw-prefetch-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-iq2-raw-prefetch-model-results.json'),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch), table_file=TABLE,
        table_sha256=sha(source/TABLE), table_entries=32768, table_device_bytes=262144,
        independent_scalar_format_checks=262144,
        affected='Eight IQ2 paired routed prefill specializations; Q2 down/decode/dense/attention unchanged.',
        numerical_contract='Same signed half operands, raw group/header prefetch, F32 scale expression/F16 rounding, '
                           'compact LDS layout, packed F16 FMA, sequential K16 WMMA, routing/tails/SwiGLU.',
        mechanism='One signed-high-byte codebook lookup replaces separate magnitude/sign table loads, masking and XOR.',
        risks='262144-byte table instead of 2048-byte magnitude table may amplify random cache traffic. '
              'Earlier Q8 LUT regression remains preserved; static instruction savings predict no model gain.',
        stage_layout_unchanged=True, tile_geometry_unchanged=True, additional_runtime_allocations=0,
        additional_streams=0, full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-fused-grid-source.v1', variants={'iq2-fused-grid': variant},
                       gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(source_files=len(files), changed_files=delta, table_bytes=262144,
                         independent_format_checks=262144, gpu_run=False)))


if __name__ == '__main__':
    main()
