#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reduce token width of both fixed shared-down paths after measured spills."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT/'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    previous_path = ROOT/'config/q2-shared-down-fixed-source.json'
    previous = json.loads(previous_path.read_text())['variants']['shared-down-fixed']
    base = ROOT/previous['source']
    assert ssm.inventory(base) == previous['files']
    rel = str(Path(ssm.REL).parent/'q2_shared_down_mirror.inc')
    original = (base/rel).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,',
                           original.index('bool SharedDownMirrorGemm('))
    head, fixed = original[:start], original[start:]
    fixed = ssm.once(fixed, 'BM == 256 && BN == 128 && BK == 1', 'BM == 256 && BN == 64 && BK == 1')
    assert fixed.count('SharedDownFixedKernel<256, 128, 1, 4, 2') == 2
    assert fixed.count('dim3((batch + 127) / 128, 10)') == 2
    fixed = fixed.replace('SharedDownFixedKernel<256, 128, 1, 4, 2',
                          'SharedDownFixedKernel<256, 64, 1, 4, 2')
    fixed = fixed.replace('dim3((batch + 127) / 128, 10)', 'dim3((batch + 63) / 64, 10)')
    target = ROOT/'.deps/gufo-q2-shared-down-n64-run'
    manifest = ROOT/'config/q2-shared-down-n64-source.json'
    patch = ROOT/'experiments/q2-shared-down-n64.patch'
    assert not any(p.exists() for p in (target, manifest, patch))
    shutil.copytree(base, target)
    (target/rel).write_text(head+fixed)
    files = ssm.inventory(target)
    assert len(files) == 1028
    assert [p for p in files if files[p] != previous['files'][p]] == [rel]
    parent = json.loads((ROOT/previous['parent_manifest']).read_text())['variants']['down-register-scatter']
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in previous['changed_files']:
            before = ROOT/parent['source']/name
            stream.write(''.join(difflib.unified_diff(before.read_text().splitlines(True) if before.exists() else [],
                (target/name).read_text().splitlines(True), fromfile='a/'+name if before.exists() else '/dev/null',
                tofile='b/'+name)))
    variant = dict(previous, source=str(target.relative_to(ROOT)), files=files,
        patch=str(patch.relative_to(ROOT)), patch_sha256=ssm.sha(patch),
        preceding_local_manifest=str(previous_path.relative_to(ROOT)), preceding_local_manifest_sha256=ssm.sha(previous_path),
        measured_component='config/q2-shared-down-component-results.json',
        measured_component_sha256=ssm.sha(ROOT/'config/q2-shared-down-component-results.json'),
        mechanism='Component-only token tile128 to64 for the two fixed-shape paths; original Q8 and generic F16 '
            'controls unchanged. Reduce accumulator/staging pressure while preserving K16 accumulation order '
            'and all token tails. Twice as many token CTAs reduce weight reuse; timing is required.',
        tile=dict(BM=256, BN=64, BK=1, WM=4, WN=2), model_dispatch_changed=False,
        model_integrated=False, gpu_run=False, numerical_acceptance=False)
    with manifest.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-shared-down-n64-source.v1',
                       variants={'shared-down-n64': variant}, goal_met=False), f, indent=2)
        f.write('\n')
    print(json.dumps(dict(provider_files=1028, changed_from_previous=[rel], token_tile=64,
                         model_dispatch_changed=False, gpu_run=False)))


if __name__ == '__main__':
    main()
