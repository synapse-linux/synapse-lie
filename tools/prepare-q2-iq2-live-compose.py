#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the retained unread-store predicate with the measured compact IQ2 parent."""
import ast
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('lane', ROOT/'tools/prepare-q2-iq2-lane-commit.py')
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
sha, inventory = lane.sha, lane.inventory


def main():
    parent_path = ROOT/'config/q2-iq2-lane-commit-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-lane-commit']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained nominal best source changed')
    opportunity = json.loads((ROOT/'config/q2-iq2-live-stage-composition-opportunity.json').read_text())
    retained = ROOT/'config/q2-live-stage-results.json'
    saved_patch = ROOT/'experiments/q2-iq2-live-stage.patch'
    if (sha(parent_path) != opportunity['parent_manifest_sha256'] or
            sha(retained) != opportunity['retained_component_result_sha256'] or
            sha(saved_patch) != opportunity['retained_patch_sha256']):
        raise ValueError('Retained composition evidence changed')
    transformer = ROOT/'tools/prepare-q2-iq2-live-stage.py'
    tree = ast.parse(transformer.read_text())
    pieces = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('old', 'new'):
                if name in pieces:
                    raise ValueError('Ambiguous retained predicate')
                pieces[name] = ast.literal_eval(node.value)
    if set(pieces) != {'old', 'new'}:
        raise ValueError('Retained predicate missing')
    original = (base/REL).read_text()
    if original.count(pieces['old']) != 1 or pieces['new'] in original:
        raise ValueError('Composition anchor changed or already applied')
    changed = original.replace(pieces['old'], pieces['new'])
    out = ROOT/'.deps/gufo-q2-iq2-live-compose-run'
    manifest = ROOT/'config/q2-iq2-live-compose-source.json'
    patch = ROOT/'experiments/q2-iq2-live-compose.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite experiment')
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    measured = ROOT/'config/q2-iq2-lane-commit-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        retained_component=str(retained.relative_to(ROOT)), retained_component_sha256=sha(retained),
        retained_patch=str(saved_patch.relative_to(ROOT)), retained_patch_sha256=sha(saved_patch),
        retained_transformer=str(transformer.relative_to(ROOT)), retained_transformer_sha256=sha(transformer),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        affected='Paired IQ2 prefill widths greater than16; compact/four-lane producer retained.',
        numerical_contract='Every live16-row activation fragment and its padding remain written; '
            'unchanged weight bytes, decode, scales, WMMA order, barriers, epilogue, maps and geometry.',
        mechanism='Compute the existing live-fragment store predicate once, outside the K loop; '
            'omit repeated zero stores only for fragments the existing matrix loop never reads.',
        risks='Predicate/register scheduling in the new composition can offset the retained component gain.',
        retained_component_rerun=False, new_composition_model_required=True,
        additional_runtime_allocations=0, additional_streams=0,
        gpu_run=False, model_inference=False, goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-iq2-live-compose-source.v1',
        variants={'iq2-live-compose': variant}, gpu_run=False, goal_met=False), indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
        retained_predicate_exact=True, retained_component_rerun=False, gpu_run=False)))


if __name__ == '__main__':
    main()
