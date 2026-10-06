#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare fixed IQ2 gate/up bounds without changing arithmetic or route geometry."""
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
INC = 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_fixed_bounds.inc'
NAME = 'RoutedIq2FixedBoundsKernel'


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory differs')
    original = (base / REL).read_text()
    old = prepare.function(original, prepare.PREFIX)
    kernel = old.replace('RoutedF16GEMMKernel', NAME)
    kernel = once(kernel, '__half* __restrict__ out_half, std::size_t m, std::size_t k,',
        '__half* __restrict__ out_half, std::size_t input_m, std::size_t input_k,')
    kernel = once(kernel, '    const void* __restrict__ w_up) {',
        '''    const void* __restrict__ w_up) {
  static_assert(kType == WeightType::kIQ2_XXS && kPair && !kPacked && !kScaled);
  static_assert(BM == 128 && (BN == 64 || BN == 128) && BK == 2);
  // Only the guarded 640x2560 launcher may enter this private body.
  constexpr std::size_t m = 640, k = 2560;''')
    kernel = once(kernel, '    f_live[u] = r < m_i;', '    f_live[u] = true;')
    kernel = once(kernel, '        if (t < bucket_rows && r_block + r < m_i) {',
                  '        if (t < bucket_rows) {')
    kernel = once(kernel, '''              if (m % 2 == 0 && r_block + r + 1 < m_i)
                *reinterpret_cast<float2*>(out + offset) =
                    make_float2(wide_values[0], wide_values[1]);
              else {
                out[offset] = wide_values[0];
                if (r_block + r + 1 < m_i)
                  out[offset + 1] = wide_values[1];
              }''', '''              *reinterpret_cast<float2*>(out + offset) =
                  make_float2(wide_values[0], wide_values[1]);''')
    include = '// SPDX-License-Identifier: MIT\n// Official-Gufo-derived fixed geometry; original arithmetic unchanged.\n' + kernel + '\n'
    candidate = once(original, old, old + '\n\n#include "q2_iq2_fixed_bounds.inc"')
    launch = '''  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),
      grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
      rows_slot, nullptr, out, nullptr, m, k, up);'''
    selected = '''  if constexpr ((BN == 64 || BN == 128) && !kPacked) {
    if (m == 640 && k == 2560) {
      hipLaunchKernelGGL(
          (RoutedIq2FixedBoundsKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, false>),
          grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
          rows_slot, nullptr, out, nullptr, m, k, up);
      return;
    }
  }
''' + launch
    candidate = once(candidate, launch, selected)
    out = ROOT / '.deps/gufo-q2-iq2-fixed-bounds-run'
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    patch = ROOT / 'experiments/q2-iq2-fixed-bounds.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing experiment')
    shutil.copytree(base, out)
    (out / REL).write_text(candidate)
    (out / INC).write_text(include)
    files = inventory(out)
    changed = sorted(name for name in files if files[name] != parent['files'].get(name))
    if len(files) != 1028 or changed != sorted([REL, INC]):
        raise ValueError('Provider scope differs')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
        fromfile='a/' + REL, tofile='b/' + REL)) + ''.join(difflib.unified_diff([], include.splitlines(True),
        fromfile='/dev/null', tofile='b/' + INC)))
    value = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=changed,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        numerical_include=INC, numerical_include_sha256=sha(out / INC),
        selected_shapes=dict(BN=[64, 128], m=640, k=2560, packed=False),
        output_grid_blocks=10, output_rows_per_block=64,
        output_bounds_proof='Ten grid blocks times64 logical rows exactly cover640. '
                            'Every pair starts at an even row, stays within its block and has aligned float2 output.',
        mechanism='Constant row stride/K bounds and no output-tail branches for complete fixed rows. '
                  'Original sign table, four-lane ownership, F16 rounded products/K16 WMMA/SwiGLU order unchanged.',
        additional_runtime_allocations=0, callbacks_or_streams_changed=False,
        original_template_source_unchanged=True, gpu_run=False, full_model_measured=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-fixed-bounds-source.v1', variants={'iq2-fixed-bounds': value}),
                  stream, indent=2)
        stream.write('\n')
    if inventory(base) != parent['files']:
        raise ValueError('Parent mutated')
    print(json.dumps(dict(provider_files=1028, grid_blocks=10, rows=640, GPU_run=False)))


if __name__ == '__main__':
    main()
