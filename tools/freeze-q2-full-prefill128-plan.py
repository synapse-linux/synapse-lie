#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one exact saved-input full-prefill replay through128K."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require


def main():
    output = ROOT/'config/q2-full-prefill128-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT/'config/q2-curve128-plan.json')
    names = set(prior['fixtures']) | {'tools/q2_full_prefill128.py', 'tools/q2-full-prefill128-window.py',
        'tools/q2-full-prefill128-phase.py', 'tools/freeze-q2-full-prefill128-plan.py'}
    fixtures = {name: sha(ROOT/name) for name in sorted(names)}
    label = 'q2-full-prefill128-host-r1'
    path = ROOT/'evidence'/label
    host, transport = curve.artifact_integrity(path)
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
        host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
        len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
        transport['exit_code'] == 0, 'Actual .157 host gate incomplete')
    counts = []
    for name in ('03.log', '06.log'):
        log = (path/'results'/name).read_text()
        m = re.search(r'100% tests passed[^\n]*?out of ([0-9]+)', log)
        require(m and 'q2_remote' in log, 'Host launch gate missing')
        counts.append(int(m[1]))
    require(counts[0] == counts[1] and counts[0] >= 38, 'Host gate differs')
    manifests = {name: sha(ROOT/name) for name in (
        'config/q2-full-prefill128-inputs.json', 'config/q2-full-prefill128-requests.jsonl',
        'config/q2-curve128-source.json', 'config/q2-curve128-binaries.json',
        'config/q2-native-bench-source.json', 'config/q2-native-row-curve-results.json',
        'config/q2-iq2-fixed-bounds-source.json', 'config/q2-iq2-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(path/'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    source = read(ROOT/'config/q2-curve128-source.json')
    for directory, files in [(source['core_source'], source['core_files']),
            (source['variants']['q2']['source'], source['variants']['q2']['files'])]:
        base = ROOT/directory
        require({p.relative_to(base).as_posix(): sha(p) for p in base.rglob('*')
                 if p.is_file()} == files, 'Frozen source inventory differs')
    previous = 'config/q2-curve128-window-release.json'
    require(sha(ROOT/previous) == 'b9c8f3f1dd18fbc0fc200a060692b4479afcec285803e3a9916f454f19bd1da1',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-full-prefill128-plan.v1', fixtures=fixtures, manifests=manifests,
        components=[], arms=[dict(label='q2-full-prefill128-retained-r1', mode='q2-prefill128', variant='prefill128-q2')],
        host=label, host_result_sha256=sha(path/'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT/previous),
        window_helper='tools/q2-full-prefill128-window.py', window_helper_sha256=sha(ROOT/'tools/q2-full-prefill128-window.py'),
        admission_path='config/q2-full-prefill128-window-admission.json', release_path='config/q2-full-prefill128-window-release.json',
        **{k: prior[k] for k in ('core_closure_sha256', 'core_cpu_lease', 'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[],
        depths=[4096,8192,12288,16384,32768,65536,131072], context_capacity=133760,
        prefill_chunk=2048, cache_ram_mib=16384, repetitions=1,
        input_manifest='config/q2-full-prefill128-inputs.json',
        workload='Native C synapse-lie-bench http --requests: exact historical calibration/warmup and all full prefix requests including both8K attempts. No continuation measurements, padding, truncation, replacement or new calibration.',
        benchmark_comparison='Completed whole-prefill times for exactly saved messages and physical counts; all prefix requests must have zero cached tokens and ceil(tokens/2048) calls. Compare archived Q2 before/after and UD. SSE transport differs; HTTP wall is separate and no causal/statistical claim is implied.',
        source_files=len(source['variants']['q2']['files']), core_files=len(source['core_files']),
        fixed_point_priority_retained=True, owner_requested_curve=True, run_controls=False,
        native_client_rebuilt=False, server_rebuilt=False, MMQ_rebuilt=False,
        scope='One new full-prefill replay through128K on latest retained Q2; reuse unchanged1028-file provider and existing server/native client binaries. Exact saved inputs; full2048 chunks plus natural last remainder. Existing server capacity133760/chunk2048/C1 and prefix policy retained, but zero cached tokens required for every prefix measurement. All calibration attempts preserved; no partial-tail benchmark. No GPU build, control rerun, model conversion, tuning or remote cleanup. Collect and release before analysis.',
        phase_helper='tools/q2-full-prefill128-phase.py', model_inference=False, GPU_admission=False)
    output.write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts, plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
