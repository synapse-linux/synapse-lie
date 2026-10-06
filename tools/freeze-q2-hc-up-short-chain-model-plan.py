#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the HC up short-chain model after actual .157 host collection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require


def main():
    output = ROOT / 'config/q2-hc-up-short-chain-model-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-hc-up-short-chain-plan.json')
    contract = read(ROOT / 'config/q2-iq2-fixed-bounds-plan.json')
    names = set(prior['fixtures']) | {
        'tools/prepare-q2-hc-up-short-chain-model.py',
        'tools/analyze-q2-hc-up-short-chain-model-static.py',
        'experiments/q2-hc-up-short-chain-model.patch',
        'tools/q2-hc-up-short-chain-model-window.py',
        'tools/q2-hc-up-short-chain-model-phase.py',
        'tools/freeze-q2-hc-up-short-chain-model-plan.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    label = 'q2-hc-up-short-chain-model-host-r1'
    directory = ROOT / 'evidence' / label
    host, transport = curve.artifact_integrity(directory)
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
            host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Actual .157 host gate incomplete')
    counts = []
    for name in ('03.log', '06.log'):
        text = (directory / 'results' / name).read_text()
        matched = re.search(r'100% tests passed[^\n]*?out of ([0-9]+)', text)
        require(matched and 'q2_remote' in text, 'Launcher checks missing')
        counts.append(int(matched[1]))
    require(counts == [39, 39], 'Host gate differs')
    manifests = {name: sha(ROOT / name) for name in (
        'config/q2-hc-up-short-chain-model-source.json',
        'config/q2-hc-up-short-chain-model-static.json',
        'config/q2-hc-up-short-chain-results.json',
        'config/q2-hc-up-short-chain-static.json',
        'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-iq2-fixed-bounds-model-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    variant = read(ROOT / 'config/q2-hc-up-short-chain-model-source.json')['variants']['hc-up-short-chain']
    provider = ROOT / variant['source']
    require({p.relative_to(provider).as_posix(): sha(p) for p in provider.rglob('*')
             if p.is_file()} == variant['files'] and len(variant['files']) == 1029,
            'Private provider inventory differs')
    static = read(ROOT / 'config/q2-hc-up-short-chain-model-static.json')
    require(static['source_manifest_sha256'] == sha(ROOT / 'config/q2-hc-up-short-chain-model-source.json') and
            static['all_device_bodies_exact'] == 166 and static['provider_files'] == 1029,
            'Measured bodies changed during integration')
    component = read(ROOT / 'config/q2-hc-up-short-chain-results.json')
    require(component['commands'] == [0, 0, 1] and component['completion']['safe_completion'] and
            component['completion']['independent_pass'], 'Safe component gate differs')
    previous = 'config/q2-hc-up-short-chain-window-release.json'
    require(sha(ROOT / previous) == '79baceeeada040899b48da044a7081f890d2447954624fff360fd7affcb5bc27',
            'Latest release differs')
    require(component['release_sha256'] == sha(ROOT / previous), 'Component release differs')
    point_keys = ('input_sha256', 'context_capacity', 'chunk', 'prompt_tokens', 'output_tokens',
                  'timed_decode_calls', 'warmups', 'repetitions', 'cooldown_seconds', 'mtp', 'run_controls')
    plan = dict(schema='synapse-lie.q2-hc-up-short-chain-model-plan.v1',
        fixtures=fixtures, manifests=manifests, components=[],
        arms=[dict(label='q2-hc-up-short-chain-model-r1',
                   mode='q2-counting-hc-up-short-chain', variant='hc-up-short-chain')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=39, asan_ubsan=39),
        previous_release=previous, previous_release_sha256=sha(ROOT / previous),
        window_helper='tools/q2-hc-up-short-chain-model-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-hc-up-short-chain-model-window.py'),
        admission_path='config/q2-hc-up-short-chain-model-window-admission.json',
        release_path='config/q2-hc-up-short-chain-model-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], source_variant_manifest='config/q2-hc-up-short-chain-model-source.json',
        component_qualification='config/q2-hc-up-short-chain-results.json',
        provider_file_count=1029, component_rerun=False, controls_rebuilt_or_rerun=False,
        original_tester_unchanged=True, **{key: contract[key] for key in point_keys},
        scope='One new original-Q2 HC-up short-chain candidate at exact2048/TG128. '
              'Only ordinary/deferred original-F16 HC-up dispatch changes; scalar and raw-Q8 stay unchanged. '
              'Original weight bits, input, capacity9216, chunk2048, C1/MTPoff, one warmup, '
              'three repeats and15s cooldown outside timers remain fixed. '
              'Already collected component and saved Q2/UD/1587-parent are not rerun or rebuilt. '
              'Finite numerical changes remain explicit; original-model timing and quality are separate. '
              'No new buffers, callbacks, stream, Q4 or full curve. Collect and release before analysis.')
    require(not plan['run_controls'], 'Saved controls must not be rerun')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts,
                         plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
