#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one retained Q2 curve under the original native 0..128K protocol."""
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
    output = ROOT/'config/q2-curve128-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT/'config/q2-attention-capacity-plan.json')
    names = set(prior['fixtures']) | {'tools/q2_curve128.py', 'tools/q2-curve128-window.py',
        'tools/q2-curve128-phase.py', 'tools/freeze-q2-curve128-plan.py'}
    fixtures = {name: sha(ROOT/name) for name in sorted(names)}
    label = 'q2-curve128-host-r2'
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
    previous = 'config/q2-curve256-v3-window-release.json'
    require(sha(ROOT/previous) == '3e59f4175fec424ff6695121becf3c2f66228da89136ab5bd05ada39920cd664',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-curve128-plan.v1', fixtures=fixtures, manifests=manifests,
        components=[], arms=[dict(label='q2-curve128-retained-r1', mode='q2-curve128', variant='curve128-q2')],
        host=label, host_result_sha256=sha(path/'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT/previous),
        window_helper='tools/q2-curve128-window.py', window_helper_sha256=sha(ROOT/'tools/q2-curve128-window.py'),
        admission_path='config/q2-curve128-window-admission.json', release_path='config/q2-curve128-window-release.json',
        **{k: prior[k] for k in ('core_closure_sha256', 'core_cpu_lease', 'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[dict(label='q2-curve128-host-r1', result_sha256=sha(ROOT/'evidence/q2-curve128-host-r1/results/result.json')), dict(label='q2-attention-capacity-host-r1',
            result_sha256=sha(ROOT/'evidence/q2-attention-capacity-host-r1/results/result.json'))],
        depths=[0,4096,8192,12288,16384,32768,65536,131072], context_capacity=133760,
        prompt_tokens=2048, output_tokens=128, prefill_chunk=2048, cache_ram_mib=16384,
        warmups=1, repetitions=1, depth_tolerance=0.005,
        workload='Frozen native C synapse-lie-bench http-curve; prose seed1, AR/C1, MTP/vision/SSD off; original completed executor-call timers. No prompt padding or token substitution.',
        benchmark_comparison='New retained Q2 versus saved native-row Q2 before/after and UD, all at133760 capacity. Archived UD128K prefill1280.583. Not contemporaneous paired evidence.',
        source_files=len(source['variants']['q2']['files']), core_files=len(source['core_files']),
        fixed_point_priority_retained=True, owner_requested_curve=True, run_controls=False,
        native_client_rebuilt=False, server_rebuilt=False, MMQ_rebuilt=False,
        scope='One new complete native Q2 curve through prefix131072 at original133760 capacity. Reuse unchanged retained numerical provider1028 files and server r2, without the later engine headroom patch. C17 upper-limit-only edits are inactive here. Saved controls and original input recipe remain unchanged. No GPU build, Q4, tuning, conversion, dependency installation or remote cleanup. Collect artifacts and release before analysis.',
        phase_helper='tools/q2-curve128-phase.py', model_inference=False, GPU_admission=False)
    output.write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts, plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
