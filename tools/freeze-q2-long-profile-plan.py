#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the exact host-qualified native long-prefix diagnostic and saved binaries."""
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
PREFIX = 'q2-long-profile'
PREVIOUS_SHA = '4a7c9768d22ade5458adb6fe0fedf5eeb17bb91072f0260ccb723404c84439c5'


def main():
    output = ROOT/('config/'+PREFIX+'-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT/'config/q2-decode-q8-compact-plan.json')
    names = set(prior['fixtures']) | {
        'tools/q2_long_profile.py', 'tools/'+PREFIX+'-phase.py',
        'tools/'+PREFIX+'-window.py', 'tools/freeze-'+PREFIX+'-plan.py',
        'tests/q2_decode_q8_oracle_rows.hpp', 'tests/q2_decode_q8_oracle_rows_test.cpp'}
    fixtures = {name: sha(ROOT/name) for name in sorted(names)}
    label = PREFIX+'-host-r1'
    directory = ROOT/'evidence'/label
    host, transport = curve.artifact_integrity(directory)
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
            host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Actual .157 host gate incomplete')
    for name in ('03.log', '06.log'):
        log = (directory/'results'/name).read_text()
        require('100% tests passed out of 40' in log and 'q2_remote' in log,
                'Current Debug/ASan launcher checks missing')
    manifests = {name: sha(ROOT/name) for name in (
        'config/q2-curve128-binaries.json', 'config/q2-curve128-source.json',
        'config/q2-native-bench-source.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-inputs.json', 'config/q2-full-prefill128-requests.jsonl',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory/'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: '+name)
    previous = 'config/q2-decode-q8-compact-window-release.json'
    require(sha(ROOT/previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.'+PREFIX+'-plan.v1', fixtures=fixtures, manifests=manifests,
        components=[], arms=[dict(label=PREFIX+'-r1', mode='q2-prefill128', variant='prefill128-q2',
                                 flags=['--native-curve','--profile-prefix32k'])],
        host=label, host_result_sha256=sha(directory/'results/result.json'),
        host_test_counts=dict(debug=40, asan_ubsan=40),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/'+PREFIX+'-window.py', window_helper_sha256=sha(ROOT/('tools/'+PREFIX+'-window.py')),
        admission_path='config/'+PREFIX+'-window-admission.json',
        release_path='config/'+PREFIX+'-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[dict(label='q2-decode-q8-compact-oracle-host-r1',
            result_sha256='d80c7d2a568c3dc936f4643bda3535a2b439946b9456b5cc425e539a9db07b0a')],
        binary_rebuild=False, controls_rebuilt_or_rerun=False, headline_eligible=False,
        model_inference=True, GPU_admission=False,
        scope='Diagnostic-only kernel/HIP/copy trace on the saved retained Q2 server9993fdce and native '
              'bench87d856cf. Original three preparation inputs and exact32711-token full prefix, '
              'capacity133760/chunk2048/C1/AR/output8/no prefix hits. No token changes, model edits, '
              'builds, throughput-control reruns, Q4, full curve, cleanup or tuning. Instrumented '
              'rates are not throughput claims. Collect and release before numerical/performance analysis.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
