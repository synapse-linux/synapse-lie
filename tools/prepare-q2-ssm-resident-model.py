#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Connect only the measured resident SSM body to a private model."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/prepare-q2-iq2-tail16.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files'] and len(parent['files']) == 1028
    qualification_path = ROOT / 'config/q2-ssm-resident-results.json'
    qualification = json.loads(qualification_path.read_text())
    assert qualification['completion']['safe_completion']
    assert qualification['commands'] in ([0, 0, 0], [0, 0, 1])
    donor = ROOT / 'experiments/q2-ssm-resident-fence-draft.inc'
    static_path = ROOT / 'config/q2-hc-up-short-chain-static.json'
    static = json.loads(static_path.read_text())['variants']['ssm-resident-fence']
    assert sha(donor) == static['draft_sha256']
    target = ROOT / '.deps/gufo-q2-ssm-resident-run'
    manifest = ROOT / 'config/q2-ssm-resident-model-source.json'
    patch = ROOT / 'experiments/q2-ssm-resident-model.patch'
    prep = ROOT / 'evidence/q2-ssm-resident-model-preparation'
    assert not any(p.exists() for p in (target, manifest, patch, prep))
    names = [REL + n for n in ('executor.cpp', 'kernels.hpp', 'kernels.hip.cpp')]
    original = {n: (base / n).read_text() for n in names}
    changed = dict(original)
    replacements = {'DenseF16SsmGemm': 'DenseSsmResidentFence'}
    declarations = []
    for old, new in replacements.items():
        changed[names[0]] = once(changed[names[0]], old + '(', new + '(')
        text = original[names[1]]
        start = text.index('bool ' + old + '(')
        declaration = text[start:text.index(';', start) + 1]
        declarations.append(declaration.replace(old, new))
    close = '}  // namespace gufo::models::qwen38_flash_next::rocm'
    changed[names[1]] = once(changed[names[1]], close,
        '// Private resident SSM tile; retained per-output arithmetic order.\n' +
        '\n'.join(declarations) + '\n\n' + close)
    include = REL + 'q2_ssm_resident_fence.inc'
    changed[names[2]] = once(changed[names[2]], close,
        '#include "q2_ssm_resident_fence.inc"\n\n' + close)
    shutil.copytree(base, target)
    for name, text in changed.items():
        (target / name).write_text(text)
    (target / include).write_bytes(donor.read_bytes())
    files = inventory(target)
    assert len(files) == 1029
    assert set(n for n in parent['files'] if files[n] != parent['files'][n]) == set(names)
    assert set(files) - set(parent['files']) == {include}
    with patch.open('x') as stream:
        for name in names:
            stream.write(''.join(difflib.unified_diff(original[name].splitlines(True),
                changed[name].splitlines(True), fromfile='a/' + name, tofile='b/' + name)))
    prep.mkdir()
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = [x.replace(str(base), str(target)) for x in argv]
    argv[argv.index('-S') + 1] = str(target / names[2])
    argv[argv.index('-o') + 1] = str(prep / 'candidate.s')
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    bindings = dict(parent_manifest=str(parent_path.relative_to(ROOT)),
        measured_parent='config/q2-iq2-fixed-bounds-model-results.json',
        component_qualification=str(qualification_path.relative_to(ROOT)),
        qualified_include=str(donor.relative_to(ROOT)),
        patch=str(patch.relative_to(ROOT)), generator=str(Path(__file__).relative_to(ROOT)))
    report = dict(schema='synapse-lie.q2-ssm-resident-model-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        variants={'ssm-resident': dict(source=str(target.relative_to(ROOT)), files=files,
            **bindings, **{k + '_sha256': sha(ROOT / v) for k, v in bindings.items()},
            numerical_include=include, numerical_include_sha256=sha(donor),
            changed_parent_files=names, new_source_files=[include],
            selection='Existing fused Q8 SSM branch, n>=1024 and M16384/K2560; scalar and other projections unchanged.',
            per_output_arithmetic_order_preserved=True, extra_device_or_persistent_bytes=0,
            executor_lifetimes_changed=False, new_host_callbacks_or_streams=0,
            parent_source_unchanged=True, component_rerun=False,
            controls_rebuilt_or_rerun=False, original_model_run=False,
            production_adopted=False, independent_model_quality=False, goal_met=False)})
    with manifest.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    assert inventory(base) == parent['files']
    print(json.dumps(dict(provider_files=len(files), changed_parent_files=names,
                         numerical_include_sha256=sha(donor), original_model_run=False)))


if __name__ == '__main__':
    main()
