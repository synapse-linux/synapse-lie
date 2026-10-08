#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one host-qualified 128K diagnostic with the saved model binaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require
PREFIX = 'q2-long-profile128'
PREVIOUS = 'config/q2-iq2-token256-window-release.json'
PREVIOUS_SHA = 'f2b163b68e87cf5cfa1e68733fd41c9535e2818a9c794c7fc7771c91813381a6'


def main():
    output = ROOT/('config/'+PREFIX+'-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    names = ('CMakeLists.txt', 'cmake/curve/CMakeLists.txt', 'cmake/hip/CMakeLists.txt',
             'tools/q2-remote.py', 'tools/q2-runner.py', 'tools/q2-curve-session.py',
             'tools/q2_window_registry.py', 'tools/q2_process.py', 'tools/q2_thermal.py',
             'tools/q2_long_profile.py', 'tools/q2_long_profile128.py',
             'tools/'+PREFIX+'-phase.py', 'tools/'+PREFIX+'-window.py',
             'tools/'+PREFIX+'-preflight.py',
             'tools/freeze-'+PREFIX+'-plan.py', 'tools/analyze-'+PREFIX+'.py',
             'tools/q2_full_prefill128.py', 'tests/q2_remote_test.py')
    fixtures = {name: sha(ROOT/name) for name in names}
    manifests = {name: sha(ROOT/name) for name in (
        'config/q2-curve128-binaries.json', 'config/q2-curve128-source.json',
        'config/q2-native-bench-source.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-inputs.json', 'config/q2-full-prefill128-requests.jsonl',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    host_label = PREFIX+'-host-r1'
    directory = ROOT/'evidence'/host_label
    host, transport = curve.artifact_integrity(directory)
    exits = [c['exit_code'] for c in host['commands']]
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
            host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and exits == [0]*6 and transport['exit_code'] == 0,
            'Actual .157 host gate incomplete')
    for name in ('03.log', '06.log'):
        log = (directory/'results'/name).read_text()
        require('100% tests passed out of 43' in log and 'q2_remote' in log,
                'Current Debug/ASan host checks missing')
    with tarfile.open(directory/'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: '+name)
    require(sha(ROOT/PREVIOUS) == PREVIOUS_SHA, 'Previous Q2 release differs')
    plan = dict(schema='synapse-lie.'+PREFIX+'-plan.v1', fixtures=fixtures,
        manifests=manifests, components=[],
        arms=[dict(label=PREFIX+'-r1', mode='q2-prefill128', variant='prefill128-q2',
                   flags=['--native-curve','--profile-prefix128k'])],
        host=host_label, host_result_sha256=sha(directory/'results/result.json'),
        host_source_capsule_sha256=sha(directory/'source.tar.gz'),
        host_collection_sha256=sha(directory/'results.tar.gz'),
        host_test_counts=dict(debug=43, asan_ubsan=43),
        previous_release=PREVIOUS, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/'+PREFIX+'-window.py',
        window_helper_sha256=sha(ROOT/('tools/'+PREFIX+'-window.py')),
        phase_helper='tools/'+PREFIX+'-phase.py',
        phase_helper_sha256=sha(ROOT/('tools/'+PREFIX+'-phase.py')),
        preflight_helper='tools/'+PREFIX+'-preflight.py',
        preflight_helper_sha256=sha(ROOT/('tools/'+PREFIX+'-preflight.py')),
        admission_path='config/'+PREFIX+'-window-admission.json',
        release_path='config/'+PREFIX+'-window-release.json',
        gpu_admitted=False, model_inference=True, production_dispatch_changed=False,
        scope='One profiler-instrumented native C1 original 130925-token Q2 request using saved '
              'server9993fdce and client87d856cf. Original three preparations, capacity133760, '
              'chunks2048, AR output8 and zero prefix hits. No model/source rebuild, prompt change, '
              'control rerun, cache reset, dependency install, host tuning or remote cleanup. '
              'Instrumented timings are diagnostic, not throughput rates. Collect and release '
              'before offline analysis.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifests),
                          plan_sha256=sha(output), gpu_admitted=False)))


if __name__ == '__main__':
    main()
