#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the new exact selector component after its actual .157 host checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require
PREFIX = 'q2-select-live-grid'
PREVIOUS_SHA = 'f40710f4068d1c59100d3d88217924bb735fc77dccc14ada3eb2cfa8d8d3b44e'


def main():
    output = ROOT / ('config/' + PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-select-query-pair-plan.json')
    names = set(prior['fixtures']) | {
        'tests/q2_select_live_grid.hip', 'experiments/' + PREFIX + '.inc', 'tools/prepare-' + PREFIX + '.py',
        'tools/' + PREFIX + '-window.py', 'tools/' + PREFIX + '-phase.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    label = PREFIX + '-host-r1'
    directory = ROOT / 'evidence' / label
    host, transport = curve.artifact_integrity(directory)
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
            host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Actual .157 host gate incomplete')
    for name in ('03.log', '06.log'):
        log = (directory / 'results' / name).read_text()
        require('100% tests passed out of 39' in log and 'q2_remote' in log,
                'Current Debug/ASan launcher checks missing')
    manifests = {name: sha(ROOT / name) for name in (
        'config/' + PREFIX + '-fixture.json', 'config/' + PREFIX + '-static.json',
        'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    static = read(ROOT / ('config/' + PREFIX + '-static.json'))
    selected = static
    require(static['parent_manifest_sha256'] == sha(ROOT / 'config/q2-iq2-fixed-bounds-source.json') and
            selected['original_device_bodies_exact'] == 164 and
            sha(ROOT / selected['include']) == selected['include_sha256'],
            'Kernel/control binding differs')
    fixture = read(ROOT / ('config/' + PREFIX + '-fixture.json'))
    require(all(sha(ROOT / name) == value for name, value in fixture['bindings'].items()) and
            sha(ROOT / fixture['compile_receipt']) == fixture['compile_receipt_sha256'] and
            read(ROOT / fixture['compile_receipt'])['exit_code'] == 0,
            'Fixture compilation differs')
    previous = 'config/q2-select-query-pair-window-release.json'
    require(sha(ROOT / previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.' + PREFIX + '-plan.v1', fixtures=fixtures,
        manifests=manifests, arms=[],
        preparation_tools={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        components=[dict(label=PREFIX + '-component-r1', mode='select-live-grid-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=39, asan_ubsan=39),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/' + PREFIX + '-window.py',
        window_helper_sha256=sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        admission_path='config/' + PREFIX + '-window-admission.json',
        release_path='config/' + PREFIX + '-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], cases=7, pair_records=62, oracle_records=62,
        timing_records=56, timing_cases=4, warmups=2, measured_repeats=5,
        timing_shapes=[dict(name=name,n=n,pos=pos,first=first) for name,n,pos,first in (
            ('last-tail4',504,2048,1536), ('last-full32',512,28672,1536), ('last-full128',512,126976,1536),
            ('last-tail128',365,129024,1536))],
        timed_output_pairs_before_overwrite=56,
        score_pitch=33440, mask_words=1045, ratio=4, budget=512,
        timing_arms=['retained_score_plus_mark','live_grid_score_plus_mark'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='Eager-prefill selector launch bound only. Original score and top-k kernels, '
              'score pitch33440/mask1045 and capacity133760 unchanged. Omit only empty blocks. '
              'Actual selector slices in original4K final tail,32K/128K last full2048 chunks '
              'and128K1901-token final tail. One/three rows, tiny and budget ties also checked. '
              'All timed scores and masks verified before overwrite. Finite differences retain timing. '
              'Captured decode remains capacity-bound; no model source dispatch is changed yet. '
              'No model/control/Q4/fullcurve run, prompt or chunk change, or remote cleanup. '
              'Collect and release before analysis; fixed parity remains paused.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
