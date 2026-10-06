#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare exact compact IQ2 magnitude/sign LDS reuse on the measured parent."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-iq2-register-stage.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once
REL = prepare.REL
INC = 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_table_lds.inc'
NAME = 'RoutedIq2TableLdsKernel'


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory differs')
    original = (base / REL).read_text()
    parent_include = (base / 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_fixed_bounds.inc').read_text()
    old = prepare.function(parent_include, prepare.PREFIX)
    kernel = old.replace('RoutedIq2FixedBoundsKernel', NAME)
    kernel = once(kernel, '  const int lane_id = tid & 31;',
        """  const int lane_id = tid & 31;
  // Cache the existing compact IEEE half-high table plus sign words once.
  // All256 lanes publish magnitudes; the first128 publish original signs.
  // These bytes are disjoint from the activation/code/epilogue stage LDS.
  __shared__ uint2 iq2_tables[384];
  iq2_tables[tid] = reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[tid];
  if (tid < 128) {
    const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[tid];
    iq2_tables[256 + tid] = make_uint2(mask.x & 0x80808080U, mask.y & 0x80808080U);
  }
  __syncthreads();""")
    kernel = once(kernel, 'reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code]',
                         'iq2_tables[code]')
    kernel = once(kernel, 'reinterpret_cast<const uint2*>(ksigns64)[sign]',
                         'iq2_tables[256 + sign]')
    kernel = once(kernel, 'magnitude.x ^ (mask.x & 0x80808080U)', 'magnitude.x ^ mask.x')
    kernel = once(kernel, 'magnitude.y ^ (mask.y & 0x80808080U)', 'magnitude.y ^ mask.y')
    include = '// SPDX-License-Identifier: MIT\n// Official-Gufo-derived compact table reuse; numerical operations unchanged.\n' + kernel + '\n'
    candidate = once(original, '#include "q2_iq2_fixed_bounds.inc"',
                     '#include "q2_iq2_fixed_bounds.inc"\n#include "q2_iq2_table_lds.inc"')
    candidate = once(candidate,
        '(RoutedIq2FixedBoundsKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, false>)',
        '(RoutedIq2TableLdsKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, false>)')
    out = ROOT / '.deps/gufo-q2-iq2-table-lds-run'
    manifest = ROOT / 'config/q2-iq2-table-lds-source.json'
    patch = ROOT / 'experiments/q2-iq2-table-lds.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing experiment')
    shutil.copytree(base, out)
    (out / REL).write_text(candidate)
    (out / INC).write_text(include)
    files = inventory(out)
    changed = sorted(name for name in files if files[name] != parent['files'].get(name))
    if len(files) != 1029 or changed != sorted([REL, INC]):
        raise ValueError('Provider scope differs')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
        fromfile='a/' + REL, tofile='b/' + REL)) + ''.join(difflib.unified_diff([], include.splitlines(True),
        fromfile='/dev/null', tofile='b/' + INC)))
    value = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=changed,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-fixed-bounds-model-results.json'),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        numerical_include=INC, numerical_include_sha256=sha(out / INC),
        selected_shapes=dict(BN=[64, 128], m=640, k=2560, packed=False),
        output_grid_blocks=10, output_rows_per_block=64,
        output_bounds_proof='Ten grid blocks times64 logical rows exactly cover640. '
                            'Every pair starts at an even row, stays within its block and has aligned float2 output.',
        mechanism='Cache existing2048-byte half-high magnitude and1024-byte sign words once per workgroup; exact sign masks precomputed once. '
                  'Original sign table, four-lane ownership, F16 rounded products/K16 WMMA/SwiGLU order unchanged.',
        additional_runtime_allocations=0, extra_stage_LDS_bytes=3072, extra_barriers_outside_K=1, callbacks_or_streams_changed=False,
        original_template_source_unchanged=True, gpu_run=False, full_model_measured=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-table-lds-source.v1', variants={'iq2-table-lds': value}),
                  stream, indent=2)
        stream.write('\n')
    if inventory(base) != parent['files']:
        raise ValueError('Parent mutated')
    print(json.dumps(dict(provider_files=1029, grid_blocks=10, rows=640, GPU_run=False)))


if __name__ == '__main__':
    main()
