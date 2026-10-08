#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Defer active Q2_K down unpacking until LDS commit, preserving IQ2 raw prefetch."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
SIGNATURE = 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prepare = module('prepare-q2-q8-halfpair.py')
literal = module('prepare-q2-q8-grouped.py')
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once


def main():
    parent_path = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured IQ2 raw-prefetch parent inventory changed')
    original = (base / REL).read_text()
    kernel = literal.function(original, SIGNATURE)
    unpack = '''        const unsigned shift = 2U * unsigned(sb32 % 4);
        const auto unpack = [shift](uint4 v) {
          return make_uint4(
              (v.x >> shift) & 0x03030303U, (v.y >> shift) & 0x03030303U,
              (v.z >> shift) & 0x03030303U, (v.w >> shift) & 0x03030303U);
        };
        f_codes[u] = unpack(f_codes[u]);
        f_codes_hi[u] = unpack(f_codes_hi[u]);'''
    changed = once(kernel, unpack,
        '''        // SPDX-License-Identifier: MIT
        // Active scaled-Q2 down keeps original code bytes in the prefetch;
        // unpacking at commit avoids a dependency on these loads here.
        if constexpr (!kScaled) {
''' + '\n'.join('  ' + line for line in unpack.splitlines()) + '''
        }''')
    changed = once(changed, '  const auto commit_stage = [&]() {',
                   '  const auto commit_stage = [&](int kb0) {')
    changed = once(changed,
        '''      } else if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''',
        '''      } else if constexpr (kQ2 && kScaled) {
        const unsigned shift = 2U * unsigned((kb0 + f_c) % 4);
        const auto unpack = [shift](uint4 v) {
          return make_uint4(
              (v.x >> shift) & 0x03030303U, (v.y >> shift) & 0x03030303U,
              (v.z >> shift) & 0x03030303U, (v.w >> shift) & 0x03030303U);
        };
        s_codes[swizzle(row, 2 * f_c)] = unpack(f_codes[u]);
        s_codes[swizzle(row, (2 * f_c) + 1)] = unpack(f_codes_hi[u]);
      } else if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''')
    changed = once(changed, '    commit_stage();', '    commit_stage(kb0);')
    changed = once(original, kernel, changed)
    source = ROOT / '.deps/gufo-q2-down-raw-prefetch-run'
    patch = ROOT / 'experiments/q2-down-raw-prefetch.patch'
    manifest = ROOT / 'config/q2-down-raw-prefetch-source.json'
    control = ROOT / 'experiments/q2-down-raw-prefetch-control.inc'
    if any(path.exists() for path in (source, patch, manifest, control)):
        raise ValueError('Refusing to overwrite retained experiment')
    result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
        '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / REL)],
        input=changed, capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Formatting failed: ' + result.stderr)
    changed = result.stdout
    format_checks = 0
    for byte in range(256):
        word = byte * 0x01010101
        for shift in (0, 2, 4, 6):
            got = (word >> shift) & 0x03030303
            expected = ((byte >> shift) & 3) * 0x01010101
            if got != expected:
                raise ValueError('Packed shifts cross byte lanes')
            format_checks += 1
    shutil.copytree(base, source)
    (source / REL).write_text(changed)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    with control.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write('// Literal saved IQ2 raw-prefetch parent; original Q2 down unpacking.\n')
        stream.write(kernel.replace('RoutedF16GEMMKernel', 'RoutedDownRawControlKernel') + '\n')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
            fromfile='a/' + REL, tofile='b/' + REL)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-raw-prefetch-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-raw-prefetch-model-results.json'),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch), host_packed_shift_checks=format_checks,
        affected='Active scaled-Q2_K down prefill specializations at BN16/48/64 only.',
        numerical_contract='Same original code/header bytes and integer shifts/masks; unchanged F32 affine, '
                           'F16 operands, ordered K16 WMMA, inverse row scale, routing, tails and output stores.',
        mechanism='Keep raw Q2 code bytes during one-stage prefetch; extract the original bit plane '
                  'when committing the current stage to LDS. Weight fetch frequency and quantities unchanged.',
        risks='No payload reduction unlike IQ2; current K coordinate and load scheduling may add instructions '
              'or registers. Only full output and original model measurements can establish benefit.',
        iq2_raw_prefetch_retained=True, code_cache_added=False, stage_layout_unchanged=True,
        tile_geometry_unchanged=True, additional_runtime_allocations=0, additional_streams=0,
        additional_device_tables=0, full_model_measured=False, numerical_acceptance=False,
        gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-down-raw-prefetch-source.v1',
                       variants={'down-raw-prefetch': variant}, gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
                         host_packed_shift_checks=format_checks, gpu_run=False)))


if __name__ == '__main__':
    main()
