#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Share scaled-Q2 activation staging across 256 output rows at BN48 only."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc'
KERNEL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('lane', ROOT/'tools/prepare-q2-iq2-lane-commit.py')
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
sha, inventory = lane.sha, lane.inventory


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source anchor is not unique: '+old[:100])
    return text.replace(old, new)


def main():
    parent_path = ROOT/'config/q2-iq2-lane-commit-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-lane-commit']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained nominal best source changed')
    out = ROOT/'.deps/gufo-q2-down-output-reuse-run'
    manifest = ROOT/'config/q2-down-output-reuse-source.json'
    patch = ROOT/'experiments/q2-down-output-reuse.patch'
    control = ROOT/'experiments/q2-down-output-reuse-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    old = '''  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kQ2_K, 128, BN, 2, false, false, true>),
      dim3(static_cast<unsigned>((m + 127) / 128), n_tiles), dim3(256), 0,'''
    new = '''  // Reuse each activation stage across twice as many output rows.
  // Keep the existing token tiles, K order and all other dispatches.
  constexpr unsigned BM = BN == 48 ? 256 : 128;
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kQ2_K, BM, BN, 2, false, false, true>),
      dim3(static_cast<unsigned>((m + BM - 1) / BM), n_tiles), dim3(256), 0,'''
    changed = once(original, old, new)
    kernel = lane.prior.prior.literal.function((base/KERNEL).read_text(),
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured lane-commit1509 parent; original BM128 Q2 down.\n'+
        kernel.replace('RoutedF16GEMMKernel', 'RoutedDownOutputControlKernel')+'\n')
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    measured = ROOT/'config/q2-iq2-lane-commit-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        affected='Scaled Q2_K down BN48 only: BM128 becomes BM256.',
        numerical_contract='Original encoded weights, scaled-half activations, K16 WMMA order, '
            'row inverse, F32 output and logical640/stored768 tail remain unchanged.',
        mechanism='Two output fragments per wave share one activation stage; output grid halves '
            'at M2560. Token routing geometry, weight decode and useful matrix work do not change.',
        risks='Doubled accumulators and increased LDS may reduce occupancy or cause spills.',
        numerical_kernel_source_unchanged=True, additional_runtime_allocations=0,
        additional_streams=0, gpu_run=False, model_inference=False, goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-down-output-reuse-source.v1',
        variants={'down-output-reuse': variant}, gpu_run=False, goal_met=False), indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta, gpu_run=False)))


if __name__ == '__main__':
    main()
