#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Select the fixed down draft only for its proven rows, K extent and alignment."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-hc-inject-raw-q8.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once
REL = prepare.REL + 'q2_down_half_storage.inc'
INC = prepare.REL + 'q2_down_fixed_bounds.inc'


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files']
    draft_path = ROOT / 'experiments/q2-down-fixed-bounds-draft.inc'
    draft_manifest = ROOT / 'config/q2-down-fixed-bounds-draft.json'
    draft_static = ROOT / 'config/q2-down-fixed-bounds-draft-static.json'
    draft = json.loads(draft_manifest.read_text())
    assert sha(draft_path) == draft['include_sha256'] and sha(base / REL) == draft['donor_sha256']
    original = (base / REL).read_text()
    control = (ROOT / 'experiments/q2-down-register-palette-control.inc').read_text()
    assert control.replace('RoutedQ2RegisterPaletteControlKernel', 'RoutedQ2HalfStorageKernel') == original[:original.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')]
    candidate = once(original, 'template<int BN>\nvoid LaunchRoutedQ2HalfStorage',
        '#include "q2_down_fixed_bounds.inc"\n\ntemplate<int BN>\nvoid LaunchRoutedQ2HalfStorage')
    begin = candidate.index('  hipLaunchKernelGGL(', candidate.index('void LaunchRoutedQ2HalfStorage'))
    end = candidate.index('\n}', begin)
    launch = candidate[begin:end]
    selected = '''  if (m == 2560 && k == 640 &&
      reinterpret_cast<std::uintptr_t>(out) % 16 == 0) {
''' + launch.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2FixedBoundsDraftKernel') + '''
    return;
  }
'''
    candidate = candidate[:begin] + selected + candidate[begin:]
    target = ROOT / '.deps/gufo-q2-down-fixed-bounds-run'
    patch_path = ROOT / 'experiments/q2-down-fixed-bounds.patch'
    output = ROOT / 'config/q2-down-fixed-bounds-source.json'
    assert not any(path.exists() for path in (target, patch_path, output))
    shutil.copytree(base, target)
    (target / REL).write_text(candidate)
    (target / INC).write_bytes(draft_path.read_bytes())
    patch_path.write_text(''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
        fromfile='a/' + REL, tofile='b/' + REL)) + ''.join(difflib.unified_diff([], draft_path.read_text().splitlines(True),
        fromfile='/dev/null', tofile='b/' + INC)))
    files = inventory(target)
    assert len(files) == 1029 and sorted(name for name in files if files[name] != parent['files'].get(name)) == sorted([REL, INC])
    row = dict(source=str(target.relative_to(ROOT)), files=files, changed_files=[REL, INC],
        numerical_include=INC, numerical_include_sha256=sha(target / INC),
        shape=dict(m=2560, k=640, BM=128, BN=[16,48,64], output_alignment=16),
        original_half_storage_body_unchanged=True, literal_control_matches_parent=True,
        additional_runtime_allocations=0, executor_lifetimes_changed=False,
        mechanism='Constant actual down bounds and row stride; omit proven full-row tail checks and aligned-output fallback. Retain affine FMA/half palette/K16 WMMA/inverse product/half storage and ragged token checks.',
        GPU_run=False, full_model_measured=False, numerical_acceptance=False, performance_gain=False)
    for key, path in dict(parent_manifest=parent_path,
            measured_parent=ROOT / 'config/q2-iq2-fixed-bounds-model-results.json',
            draft_manifest=draft_manifest, draft_static=draft_static,
            donor_include=draft_path, patch=patch_path, generator=Path(__file__)).items():
        row[key], row[key + '_sha256'] = str(path.relative_to(ROOT)), sha(path)
    output.write_text(json.dumps(dict(schema='synapse-lie.q2-down-fixed-bounds-source.v1',
        variants={'down-fixed-bounds': row}), indent=2) + '\n')
    assert inventory(base) == parent['files']
    prep = ROOT / 'evidence/q2-down-fixed-bounds-preparation'
    prep.mkdir(exist_ok=True)
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = [v.replace('q2-iq2-fixed-bounds', 'q2-down-fixed-bounds') for v in argv]
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    print(json.dumps(dict(provider_files=1029, private_bodies=3, new_runtime_allocations=0)))


if __name__ == '__main__':
    main()
