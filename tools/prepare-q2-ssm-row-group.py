#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare one SSM grid-order experiment from the retained 1574 provider."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function
ASSERT_BEFORE = '          static_assert(!kHcMix && kRowGroup == 1);'
ASSERT_AFTER = '          static_assert(!kHcMix && (kRowGroup == 1 || kRowGroup == 4));'
LAUNCH_BEFORE = 'DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>'
LAUNCH_AFTER = 'DenseF16GEMMKernel<256, 128, 2, 8, 1, 4, false, true>'


def main():
    parent_path = ROOT/'config/q2-scaled-wave-pack-source.json'
    parent = json.loads(parent_path.read_text())['variants']['scaled-wave-pack']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained 1574 provider inventory changed')
    out = ROOT/'.deps/gufo-q2-ssm-row-group-run'
    manifest = ROOT/'config/q2-ssm-row-group-source.json'
    patch = ROOT/'experiments/q2-ssm-row-group.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite a retained experiment')
    original = (base/REL).read_text()
    changed = once(once(original, ASSERT_BEFORE, ASSERT_AFTER), LAUNCH_BEFORE, LAUNCH_AFTER)
    # Exactly two source substitutions. Do not format unrelated inherited code.
    assert once(once(changed, ASSERT_AFTER, ASSERT_BEFORE), LAUNCH_AFTER, LAUNCH_BEFORE) == original
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1027 and delta == [REL]
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    measured = ROOT/'config/q2-scaled-wave-pack-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mechanism='Use the existing bijective row-group mapping with group4 only in the fused SSM projection.',
        dispatch='Unchanged guard: n>=1024, M16384, K2560, channels10240, four convolution taps. Grid rows64 are divisible by4; token tails keep their original predicates.',
        numerical_contract='Preserve the entire dense template except its compile-time admissibility assertion. Only the SSM row-group template argument changes; weight decoding, rounded operands, ordered K16 WMMA, convolution and boundary kernel remain literal.',
        geometry=dict(BM=256, BN=128, BK=2, WM=8, WN=1, row_group_before=1, row_group_after=4),
        additional_allocations=0, additional_streams=0, additional_launches=0,
        risks='Closer activation-tile reuse also separates weight-tile reuse. Hardware block scheduling/cache residency are not guaranteed by grid enumeration; code generation can change.',
        inherited_quality='Retained1574 F16 lineage still lacks independent task-quality acceptance.',
        parent_rebuilt=False, gpu_run=False, model_inference=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-ssm-row-group-source.v1',
                       variants={'ssm-row-group':variant}, gpu_run=False, goal_met=False), f, indent=2)
        f.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
                         substitutions=2, gpu_run=False)))


if __name__ == '__main__':
    main()
