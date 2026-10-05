#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Remove IQ2 sign-mask ANDs using a 1KiB exact table on the measured parent."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
TABLE = 'src/models/qwen38_flash_next/kernels/rocm/lie_iq2_sign_masks.inc'
spec = importlib.util.spec_from_file_location('fused', ROOT / 'tools/prepare-q2-iq2-fused-grid.py')
fused = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fused)
sha, inventory, once = fused.sha, fused.inventory, fused.once


def main():
    parent_path = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    original = (base / REL).read_text()
    common = (base / 'src/models/qwen38_flash_next/kernels/rocm/mmq/ggml-common.h').read_text()
    high = fused.table_values(original, r'kIq2HalfHighGrid\[256\]\s*=\s*\{(.*?)\};', 256)
    grid = fused.table_values(common, r'GGML_TABLE_BEGIN\(uint64_t, iq2xxs_grid, 256\)(.*?)GGML_TABLE_END', 256)
    signs = fused.table_values(common, r'GGML_TABLE_BEGIN\(uint64_t, ksigns64, 128\)(.*?)GGML_TABLE_END', 128)
    masks = [value & 0x8080808080808080 for value in signs]
    checks = 0
    for sign in range(128):
        parity_sign = sign | ((sign.bit_count() & 1) << 7)
        independent_mask = sum(0x80 << (8 * lane) for lane in range(8) if parity_sign & (1 << lane))
        if masks[sign] != independent_mask:
            raise ValueError('Original parity/sign mask differs')
        for code in range(256):
            value = high[code] ^ masks[sign]
            for lane in range(8):
                magnitude = (grid[code] >> (8 * lane)) & 255
                expected = -magnitude if parity_sign & (1 << lane) else magnitude
                bits = int.from_bytes(struct.pack('<e', expected), 'little')
                high_byte = (value >> (8 * lane)) & 255
                low_byte = {0x48: 0, 0x4e: 0x40, 0x51: 0x60}[high_byte & 127]
                if bits != (high_byte << 8) | low_byte:
                    raise ValueError('Independent IEEE half encoding differs')
                checks += 1
    table = ('// SPDX-License-Identifier: MIT\n'
             '// Exact high-byte sign masks from independently pinned official Gufo.\n'
             '// Original tables/notices remain; no model payload is copied.\n'
             'static const __device__ std::uint64_t kIq2HalfSignMasks[128] = {\n')
    table += ''.join('    ' + ', '.join(f'0x{x:016x}ULL' for x in masks[i:i + 4]) + ',\n'
                     for i in range(0, len(masks), 4))
    table += '};\n'
    changed = once(original, '/// Each IQ2 magnitude is exactly8,25 or43.',
                   '// SPDX-License-Identifier: MIT\n#include "' + TABLE + '"\n\n'
                   '/// Each IQ2 magnitude is exactly8,25 or43.')
    changed = once(changed,
        '''          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          signed_codes[part] = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                          magnitude.y ^ (mask.y & 0x80808080U));''',
        '''          // Same sign bits; the 1KiB table already contains only bit7.
          const uint2 mask = reinterpret_cast<const uint2*>(kIq2HalfSignMasks)[sign];
          signed_codes[part] = make_uint2(magnitude.x ^ mask.x, magnitude.y ^ mask.y);''')
    source = ROOT / '.deps/gufo-q2-iq2-sign-mask-run'
    patch = ROOT / 'experiments/q2-iq2-sign-mask.patch'
    manifest = ROOT / 'config/q2-iq2-sign-mask-source.json'
    control = ROOT / 'experiments/q2-iq2-sign-mask-control.inc'
    if any(p.exists() for p in (source, patch, manifest, control)):
        raise ValueError('Refusing to overwrite retained experiment')
    formatted = {}
    for name, text in ((REL, changed), (TABLE, table)):
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
            '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / name)],
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
        raise ValueError('Unexpected provider delta')
    kernel = fused.literal.function(original, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    with control.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n// Literal measured raw-prefetch parent, not a rebuilt old cohort.\n')
        stream.write(kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2SignMaskControlKernel') + '\n')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in (REL, TABLE):
            stream.write(''.join(difflib.unified_diff((original if name == REL else '').splitlines(True),
                formatted[name].splitlines(True), fromfile='a/' + name, tofile='b/' + name)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-raw-prefetch-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-raw-prefetch-model-results.json'),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch), table_file=TABLE,
        table_sha256=sha(source / TABLE), table_entries=128, table_device_bytes=1024,
        independent_scalar_format_checks=checks,
        affected='Eight IQ2 paired routed prefill bodies; down/decode/dense/attention unchanged.',
        numerical_contract='Same signed half operands, raw prefetch, F32 scale/F16 rounding, '
                           'compact LDS, packed F16 FMA, ordered K16 WMMA, routing/tails/SwiGLU.',
        mechanism='Replace original sign table followed by bit7 AND with exact pre-masked sign table; original 2KiB magnitude grid unchanged.',
        risks='Eight removed scalar masks may be immaterial to model time; extra1KiB constant storage and compiler scheduling can regress.',
        rejected_large_table='config/q2-iq2-fused-grid-model-results.json',
        stage_layout_unchanged=True, tile_geometry_unchanged=True, additional_runtime_allocations=0,
        additional_streams=0, full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-sign-mask-source.v1', variants={'iq2-sign-mask': variant},
                       gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(source_files=len(files), changed_files=delta, table_bytes=1024,
                         independent_format_checks=checks, gpu_run=False)))


if __name__ == '__main__':
    main()
