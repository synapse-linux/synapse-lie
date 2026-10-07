#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the exact host-qualified new BF16 row-sized reader trial and saved native client."""
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
PREFIX = 'q2-ple-row-bytes'
PREVIOUS_SHA = 'cb2b68d917657404da7d011b0788cd8defdb10b5add1178e4466abc769f8d6f5'


def main():
    output = ROOT/('config/'+PREFIX+'-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT/'config/q2-long-profile-plan.json')
    names = set(prior['fixtures']) | {
        'tools/q2_ple_row_bytes_model.py', 'tools/prepare-q2-ple-row-bytes.py',
        'tests/q2_ple_row_bytes.cpp', 'experiments/q2-ple-row-bytes-ngram.cpp',
        'experiments/q2-ple-row-bytes.patch', 'tools/'+PREFIX+'-phase.py',
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
        require('100% tests passed out of 42' in log and 'q2_remote' in log,
                'Current Debug/ASan launcher checks missing')
    manifests = {name: sha(ROOT/name) for name in (
        'config/q2-ple-row-bytes-source.json', 'config/q2-curve128-binaries.json', 'config/q2-curve128-source.json',
        'config/q2-native-bench-source.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-inputs.json', 'config/q2-full-prefill128-requests.jsonl',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory/'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: '+name)
    previous = 'config/q2-long-profile-window-release.json'
    require(sha(ROOT/previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.'+PREFIX+'-plan.v1', fixtures=fixtures, manifests=manifests,
        components=[], arms=[dict(label=PREFIX+'-r1', mode='q2-prefill-ple-row-bytes', variant='prefill-ple-row-bytes-q2',
                                 flags=['--native-curve'])],
        host=label, host_result_sha256=sha(directory/'results/result.json'),
        host_test_counts=dict(debug=42, asan_ubsan=42),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/'+PREFIX+'-window.py', window_helper_sha256=sha(ROOT/('tools/'+PREFIX+'-window.py')),
        admission_path='config/'+PREFIX+'-window-admission.json',
        release_path='config/'+PREFIX+'-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[],
        candidate_binary_build=True, mmq_rebuild=False, controls_rebuilt_or_rerun=False, headline_eligible=False,
        model_inference=True, GPU_admission=False,
        scope='One new BF16 exact-row reader candidate on the retained1028-file provider. Only ngram.cpp '
              'descriptor selection changes: BF16/160 reads320 bytes, other formats/shapes keep original '
              'direct mode/fallback. Same encoded row cache, workers, ordering, dequantization, GPU bodies. '
              'New server build reuses retained MMQ; original native client reused. Original9 preparation/prefix '
              'requests through32711 tokens, capacity133760/chunk2048/C1/AR/no prefix hits. Compare saved '
              'unprofiled references/replies, never the instrumented profile. No control rebuild/rerun, Q4, '
              'longer curve, token changes, model mutation, eviction, tuning, dependency or cleanup. '
              'Buffered file-cache residency is allowed; telemetry reports actual memory/I/O. '
              'Collect and release before analysis.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
