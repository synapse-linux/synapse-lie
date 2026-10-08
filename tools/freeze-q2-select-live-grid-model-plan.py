#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the new live-grid model trial after actual .157 host checks."""
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
PREFIX = 'q2-select-live-grid-model'
PREVIOUS_SHA = '358b1fd01d73489857289961025ea15a18a33d94228970b18fb34070a6220e4a'


def main():
    output = ROOT / ('config/' + PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-select-live-grid-plan.json')
    names = set(prior['fixtures']) | {
        'tools/q2_select_live_grid_model.py', 'tools/prepare-' + PREFIX + '.py',
        'experiments/' + PREFIX + '.patch', 'tools/' + PREFIX + '-window.py',
        'tools/' + PREFIX + '-phase.py', 'cmake/curve/CMakeLists.txt',
        'tools/q2_native_curve.py', 'tools/q2-curve-session.py'}
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
        'config/' + PREFIX + '-source.json', 'config/' + PREFIX + '-static.json',
        'config/q2-select-live-grid-results.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json',
        'config/q2-full-prefill128-inputs.json', 'config/q2-full-prefill128-requests.jsonl',
        'config/q2-curve128-source.json', 'config/q2-curve128-binaries.json',
        'config/q2-native-bench-source.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    from q2_select_live_grid_model import verify_provider, inputs
    candidate = read(ROOT / ('config/' + PREFIX + '-source.json'))
    verify_provider(ROOT, ROOT / candidate['candidate'])
    static = read(ROOT / ('config/' + PREFIX + '-static.json'))
    require(static['source_manifest_sha256'] == sha(ROOT / ('config/' + PREFIX + '-source.json')) and
            static['all_device_bodies_exact'] == 164 and static['provider_files'] == 1028,
            'Model numerical bodies changed')
    component = read(ROOT / 'config/q2-select-live-grid-results.json')
    require(component['commands'] == [0,0,0] and component['numerical_pass'] and
            component['exact_pairs'] == component['oracle_passes'] == 62,
            'Component quality gate differs')
    selected = inputs(ROOT)
    previous = 'config/q2-select-live-grid-window-release.json'
    require(sha(ROOT / previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.' + PREFIX + '-plan.v1', fixtures=fixtures,
        manifests=manifests, components=[],
        preparation_tools={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        arms=[dict(label=PREFIX + '-r1', mode='q2-prefill-live-grid', variant='prefill-live-grid-q2')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=39, asan_ubsan=39),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/' + PREFIX + '-window.py',
        window_helper_sha256=sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        admission_path='config/' + PREFIX + '-window-admission.json',
        release_path='config/' + PREFIX + '-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], run_controls=False, controls_rebuilt_or_rerun=False,
        component_qualification='config/q2-select-live-grid-results.json',
        source_variant_manifest='config/' + PREFIX + '-source.json',
        provider_file_count=1028, all_device_bodies_exact=164, component_rerun=False,
        context_capacity=133760, chunk=2048, concurrency=1, prefix_budget_bytes=16*1024**3,
        workload_cases=[binding for _,binding in selected],
        client='Unchanged native C synapse-lie-bench binary87d856cf',
        model_inference=True, GPU_admission=False,
        scope='One new original-Q2 model candidate: bound score grid only during eager prefill. '
              'Original164 numerical device bodies, score pitch/mask stride, captured decode, '
              'retained1028-file provider except3 host/dispatch files, native C benchmark binary, '
              'capacity133760/chunk2048/C1/MTPoff and original saved requests unchanged. '
              'Replay the first9 original requests, including preparation and both8K attempts, '
              'through32K with their original8-token prefix replies. All full chunks remain2048 '
              'and only final tails are partial. No new padding, normalization or sampling changes. '
              'Reuse the qualified retained MMQ archive and client without rebuilding controls. '
              'Completed full-prefill executor time is the comparison, not a continuation timer. '
              'No Q4,64K/128K sweep, foreign action or remote cleanup. Collect/release before analysis.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
