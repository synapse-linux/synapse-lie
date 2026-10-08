#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Defer IQ2 expansion until LDS commit while prefetching the original bytes."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prepare = module('prepare-q2-q8-halfpair.py')
literal = module('prepare-q2-q8-grouped.py')
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once


def main():
    parent_path = ROOT / 'config/q2-iq2-halfbyte-perm-formatted-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-halfbyte-perm']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured compact parent inventory changed')
    original = (base / REL).read_text()
    start = original.index('      } else if constexpr (kIQ2) {', original.index('const auto fetch_stage ='))
    end = original.index('      } else if constexpr (kQ2) {', start)
    old_fetch = original[start:end]
    decode = old_fetch[old_fetch.index('        // One packed group:'):]
    decode = once(decode,
        '        f_dm[u] = __builtin_bit_cast(std::uint16_t, __float2half_rn(scale));',
        '''        const std::uint32_t dm =
            __builtin_bit_cast(std::uint16_t, __float2half_rn(scale));
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];
        s_codes[swizzle(row, (2 * f_c) + 1)] = f_codes_hi[u];
        scale_bias = f_live[u] ? dm : 0U;''')
    changed = once(original, old_fetch,
        '''      } else if constexpr (kIQ2) {
        const int sb32 = kb0 + f_c;
        const auto* block = f_ptr[u] + (sb32 / 8) * 66;
        // SPDX-License-Identifier: MIT
        // Keep only the original group/header live across current-stage WMMA.
        // No codebook/sign lookup or conversion waits on these loads here.
        __builtin_memcpy(&f_iq2_group[u], block + 2 + (sb32 % 8) * 8, 8);
        __builtin_memcpy(&f_iq2_d[u], block, 2);
''')
    changed = once(changed,
        '  uint4 f_codes[kWaveRowTiles];',
        '''  uint4 f_codes[kWaveRowTiles];
  uint2 f_iq2_group[kWaveRowTiles];
  __half f_iq2_d[kWaveRowTiles];''')
    changed = once(changed,
        '''      std::uint32_t scale_bias = 0;
      if constexpr (kSigned || kQ2) {''',
        '''      std::uint32_t scale_bias = 0;
      if constexpr (kIQ2) {
        const uint2 group = f_iq2_group[u];
        const __half d = f_iq2_d[u];
''' + decode + '''      } else if constexpr (kSigned || kQ2) {''')
    source = ROOT / '.deps/gufo-q2-iq2-raw-prefetch-run'
    patch = ROOT / 'experiments/q2-iq2-raw-prefetch.patch'
    manifest = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    control = ROOT / 'experiments/q2-iq2-raw-prefetch-control.inc'
    if any(path.exists() for path in (source, patch, manifest, control)):
        raise ValueError('Refusing to overwrite retained experiment')
    formatted = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
        '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / REL)],
        input=changed, capture_output=True, text=True)
    if formatted.returncode:
        raise ValueError('Provider formatting failed: ' + formatted.stderr)
    changed = formatted.stdout
    shutil.copytree(base, source)
    (source / REL).write_text(changed)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    kernel = literal.function(original, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    with control.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write('// Literal saved compact-parent kernel; shared half-bit helpers are unchanged.\n')
        stream.write(kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2RawControlKernel') + '\n')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
            fromfile='a/' + REL, tofile='b/' + REL)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-halfbyte-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-halfbyte-model-results.json'),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        affected='Eight IQ2 paired routed prefill specializations; no Q2_K down/decode/dense/attention dispatch change.',
        numerical_contract='Same group/header bytes, compact high-bit codebook/sign decode, F32 scale expression '
                           'and F16 rounding, packed F16 FMA, sequential K16 WMMA, routing, tails and SwiGLU.',
        mechanism='One-stage-ahead prefetch retains one raw uint2 group and half header; codebook/sign expansion '
                  'and scale conversion move unchanged to the LDS commit, before its existing barrier.',
        risks='Deferred lookups can expose codebook latency at commit; compiler scheduling/register effects '
              'and complete model time must be measured, not inferred from fewer prefetched values.',
        raw_prefetch_bytes_per_thread=10, parent_decoded_prefetch_bytes_per_thread=34,
        stage_layout_unchanged=True, tile_geometry_unchanged=True,
        additional_runtime_allocations=0, additional_streams=0, additional_device_tables=0,
        full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-raw-prefetch-source.v1',
                       variants={'iq2-raw-prefetch': variant}, gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
                         raw_prefetch_bytes=[34, 10], gpu_run=False)))


if __name__ == '__main__':
    main()
