#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate scalar decode code generation; retain every common prefill source."""

import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Non-unique source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT / 'config/q2-hc-scalar-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT / parent['source']
    for name, digest in parent['files'].items():
        if sha(base / name) != digest:
            raise ValueError('Parent changed: ' + name)
    original = json.loads((ROOT / 'config/q2-iq2-fixed-bounds-source.json').read_text())['variants']['iq2-fixed-bounds']
    out = ROOT / '.deps/gufo-q2-hc-scalar-isolated-run'
    manifest = ROOT / 'config/q2-hc-scalar-isolated-source.json'
    patch = ROOT / 'experiments/q2-hc-scalar-isolated.patch'
    if any(path.exists() for path in (out, manifest, patch)):
        raise ValueError('Preserve existing isolated provider')
    edits = {}
    name = REL + 'kernels.hip.cpp'
    common = once((base / name).read_text(), '\n#include "q2_hc_scalar_up_mix.inc"\n', '')
    if hashlib.sha256(common.encode()).hexdigest() != original['files'][name]:
        raise ValueError('Common kernel source is not the original retained file')
    edits[name] = common
    # These two helper bodies are copied exactly from the pinned original
    # Gufo translation unit; its licenses/notices remain in this provider.
    sigmoid = common[common.index('__device__ __forceinline__ float SigmoidF('):
                     common.index('__device__ __forceinline__ float SoftplusF(')]
    wave_start = common.index('__device__ __forceinline__ float WaveSum(')
    wave = common[wave_start:common.index('\n}\n', wave_start) + 3]
    edits[REL + 'hc_scalar_up_mix.hip'] = '''// SPDX-License-Identifier: MIT
// Original Gufo F16/F32 scalar HC arithmetic, pin
// f783fedb9bea2ec7de941f6da4e02f4a4596b29e. Helpers are exact excerpts of
// kernels.hip.cpp; upstream notices are retained. A separate translation unit
// prevents decode codegen from changing prefill.
#include <hip/hip_fp16.h>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
namespace gufo::models::qwen38_flash_next::rocm {
namespace {
''' + sigmoid + wave + '''}  // namespace
#include "q2_hc_scalar_up_mix.inc"
}  // namespace gufo::models::qwen38_flash_next::rocm
'''
    name = 'src/models/qwen38_flash_next/CMakeLists.txt'
    cmake = once((base / name).read_text(), '${QFN_ROCM_DIR}/kernels.hip.cpp\n',
                 '${QFN_ROCM_DIR}/kernels.hip.cpp\n    ${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n')
    cmake = once(cmake,
        '  set_source_files_properties(${QFN_ROCM_DIR}/kernels.hip.cpp PROPERTIES LANGUAGE HIP)\n',
        '''  set_source_files_properties(${QFN_ROCM_DIR}/kernels.hip.cpp PROPERTIES LANGUAGE HIP)
  # Keep the measured scalar component codegen local. The common backend
  # retains the saved RelWithDebInfo flags and its prefill instruction stream.
  set_source_files_properties(${QFN_ROCM_DIR}/hc_scalar_up_mix.hip
    PROPERTIES COMPILE_OPTIONS "-g0")
''')
    edits[name] = cmake
    shutil.copytree(base, out)
    patches = []
    for name, content in sorted(edits.items()):
        old = (base / name).read_text() if (base / name).exists() else ''
        (out / name).write_text(content)
        patches.append(''.join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
            fromfile='a/' + name if old else '/dev/null', tofile='b/' + name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out / name) for name in sorted(set(parent['files']) | set(edits))}
    report = {'schema': 'synapse-lie.q2-hc-scalar-isolated-source.v1',
              'source': str(out.relative_to(ROOT)), 'files': files,
              'official_gufo_pin': parent['official_gufo_pin'],
              'parent_manifest': str(parent_path.relative_to(ROOT)),
              'parent_manifest_sha256': sha(parent_path), 'changed_files': sorted(edits),
              'common_kernel_sha256': files[REL + 'kernels.hip.cpp'],
              'executor_unchanged_from_phase_guarded_parent': True,
              'qualified_include_sha256': sha(out / REL / 'q2_hc_scalar_up_mix.inc'),
              'common_build_type': 'RelWithDebInfo', 'decode_file_only_compile_option': '-g0',
              'new_precision_boundary': False, 'additional_runtime_allocations': 0,
              'prefill_phase_excluded': True, 'runtime_qualified': False,
              'generator_sha256': sha(Path(__file__)),
              'patch': str(patch.relative_to(ROOT)), 'patch_sha256': sha(patch)}
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'changed_from_parent': sorted(edits),
                      'prefill_common_source_exact_to_retained': True}))


if __name__ == '__main__':
    main()
