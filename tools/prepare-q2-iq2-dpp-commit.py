#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare exact DPP quad broadcasts on the retained fixed-bound IQ2 parent."""
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
INC = 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_dpp_commit.inc'
NAME = 'RoutedIq2DppCommitKernel'


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
    kernel = once(kernel, '          const int peer_lane = (lane_id & ~3) + owner;\n', '')
    kernel = once(kernel, '__shfl(group.x, peer_lane, 32)', 'Iq2QuadBroadcast(group.x, owner)')
    kernel = once(kernel, '__shfl(group.y, peer_lane, 32)', 'Iq2QuadBroadcast(group.y, owner)')
    helper = """// SPDX-License-Identifier: MIT
// Official-Gufo-derived IQ2 commit; exact quad-owner integer transport.
__device__ __forceinline__ std::uint32_t Iq2QuadBroadcast(std::uint32_t value, int owner) {
  // quad_perm selects one owner from each four-lane group. All lanes are live
  // in this uniform commit. Immediate controls are required by the builtin.
  const int bits = __builtin_bit_cast(int, value);
  switch (owner) {
    case 0: return __builtin_bit_cast(std::uint32_t,
        __builtin_amdgcn_update_dpp(bits, bits, 0x00, 0xf, 0xf, true));
    case 1: return __builtin_bit_cast(std::uint32_t,
        __builtin_amdgcn_update_dpp(bits, bits, 0x55, 0xf, 0xf, true));
    case 2: return __builtin_bit_cast(std::uint32_t,
        __builtin_amdgcn_update_dpp(bits, bits, 0xaa, 0xf, 0xf, true));
    default: return __builtin_bit_cast(std::uint32_t,
        __builtin_amdgcn_update_dpp(bits, bits, 0xff, 0xf, 0xf, true));
  }
}
"""
    include = helper + kernel + '\n'
    candidate = once(original, '#include "q2_iq2_fixed_bounds.inc"',
                     '#include "q2_iq2_fixed_bounds.inc"\n#include "q2_iq2_dpp_commit.inc"')
    candidate = once(candidate,
        '(RoutedIq2FixedBoundsKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, false>)',
        '(RoutedIq2DppCommitKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, false>)')
    out = ROOT / '.deps/gufo-q2-iq2-dpp-commit-run'
    manifest = ROOT / 'config/q2-iq2-dpp-commit-source.json'
    patch = ROOT / 'experiments/q2-iq2-dpp-commit.patch'
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
        mechanism='Replace eight LDS-backed four-lane shuffles with exact quad DPP integer broadcasts. '
                  'Original sign table, four-lane ownership, F16 rounded products/K16 WMMA/SwiGLU order unchanged.',
        additional_runtime_allocations=0, callbacks_or_streams_changed=False,
        original_template_source_unchanged=True, gpu_run=False, full_model_measured=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-dpp-commit-source.v1', variants={'iq2-dpp-commit': value}),
                  stream, indent=2)
        stream.write('\n')
    if inventory(base) != parent['files']:
        raise ValueError('Parent mutated')
    print(json.dumps(dict(provider_files=1029, grid_blocks=10, rows=640, GPU_run=False)))


if __name__ == '__main__':
    main()
