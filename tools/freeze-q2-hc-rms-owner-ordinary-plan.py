#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a one ordinary RMS model window after actual .157 host collection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require
PREVIOUS_SHA = '27506424d933e66e9db292653d130a713dac5d8c03d8f9cb05d169e1e10c3d92'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='q2-hc-rms-owner-ordinary-host-r1')
    parser.add_argument('--model', default='q2-hc-rms-owner-ordinary-model-r1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r'q2-hc-rms-owner-ordinary-host-r[1-9][0-9]*', args.host) and
            re.fullmatch(r'q2-hc-rms-owner-ordinary-model-r[1-9][0-9]*', args.model),
            'Unsafe or duplicate cohort label')
    require(not args.output.exists() and not (ROOT / 'evidence' / args.model).exists(),
            'Preserve existing plan and component evidence')
    previous_path = 'config/q2-hc-norm-owner-window-release.json'
    require(sha(ROOT / previous_path) == PREVIOUS_SHA, 'Previous release differs')
    old = read(ROOT / 'config/q2-hc-norm-owner-plan.json')
    names = set(old['fixtures']) | {
        'tools/prepare-q2-hc-rms-owner-ordinary.py',
        'tools/analyze-q2-hc-rms-owner-ordinary-static.py',
        'experiments/q2-hc-rms-owner-ordinary.patch',
        'tools/q2-hc-rms-owner-ordinary-window.py',
        'tools/q2-hc-rms-owner-ordinary-phase.py',
        'tools/freeze-q2-hc-rms-owner-ordinary-plan.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    host_dir = ROOT / 'evidence' / args.host
    host, transport = curve.artifact_integrity(host_dir)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and host['finished_at'] and len(host['commands']) == 6 and
            all(c['exit_code'] == 0 for c in host['commands']) and
            host['mode'] == transport['mode'] == 'cpu' and transport['exit_code'] == 0,
            'Actual host gate incomplete')
    for log in ('03.log', '06.log'):
        require('100% tests passed out of 36' in (host_dir / 'results' / log).read_text(),
                'Missing .157 Debug/ASan host36 checks')
    with tarfile.open(host_dir / 'source.tar.gz') as archive:
        for name, digest in fixtures.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    manifest_path = 'config/q2-hc-rms-owner-ordinary-source.json'
    variant = read(ROOT / manifest_path)['variants']['hc-rms-owner-ordinary']
    provider = ROOT / variant['source']
    inventory = {str(p.relative_to(provider)): sha(p) for p in provider.rglob('*') if p.is_file()}
    require(inventory == variant['files'] and len(inventory) == 1028,
            'New ordinary RMS provider inventory differs')
    core = ROOT.parent / 'context-million-openai/evidence/terminal-full-client-stop-closure-r16.json'
    require(sha(core) == '1141a001a8ca79f85c266f8710170bca1ead77009fa3bbc6b3b6ac94ae7fc2b9',
            'Original Core closure differs')
    supplemental = ROOT / 'evidence/q2-down-register-palette-preparation/registry-focused-ctest-v2-stdout.txt'
    supplemental_rows = [json.loads(line) for line in supplemental.read_text().splitlines()
                         if line.startswith('{')]
    require(len(supplemental_rows) == 1 and supplemental_rows[0]['exit_code'] == 0 and
            supplemental_rows[0]['owned_group_retired'], 'Supplemental CPU closure incomplete')
    retired_cpu = []
    for directory in sorted((ROOT / 'evidence').glob('q2-hc-rms-owner-ordinary-host-r*')):
        if directory.name == args.host:
            continue
        historical, historical_transport = curve.artifact_integrity(directory)
        require(historical['mode'] == historical_transport['mode'] == 'cpu' and
                historical.get('finished_at') and not historical['model_access'] and
                historical['state'] in ('FAILED', 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE'),
                'Historical CPU cohort incomplete')
        retired_cpu.append(dict(label=directory.name,
                                result_sha256=sha(directory / 'results/result.json'),
                                command_exits=[c['exit_code'] for c in historical['commands']]))
    manifests = {name: sha(ROOT / name) for name in (
        manifest_path, 'config/q2-ssm-fixed-bounds-source.json',
        'config/q2-ssm-fixed-bounds-model-results.json', 'config/q2-fixed-prefill-reference.json',
        'config/q2-hc-rms-owner-ordinary-static.json',
        'config/q2-hc-norm-owner-component-results.json')}
    component = read(ROOT / 'config/q2-hc-norm-owner-component-results.json')
    require(component['command_exits'] == [0, 0, 0] and component['device_work_safe'] and
            component['numerical_exact'] and len(component['output_records']) == 120 and
            component['release_sha256'] == PREVIOUS_SHA, 'Retained qualified component differs')
    static = read(ROOT / 'config/q2-hc-rms-owner-ordinary-static.json')
    require(static['qualified_ordinary_body_exact'] and static['candidate_bodies_exact'] == 163 and
            static['MoE_dispatch_unchanged'] and static['provider_file_inventory_exact'] == 1028,
            'Ordinary-only source static binding differs')
    point_keys = ('input_sha256', 'context_capacity', 'chunk', 'prompt_tokens', 'output_tokens',
                  'timed_decode_calls', 'warmups', 'repetitions', 'cooldown_seconds', 'mtp', 'run_controls')
    plan = dict(schema='synapse-lie.q2-hc-rms-owner-ordinary-plan.v1',
        fixtures=fixtures, manifests=manifests, components=[],
        arms=[dict(label=args.model, mode='q2-counting-hc-rms-owner-ordinary', variant='hc-rms-owner-ordinary')],
        host=args.host, host_result_sha256=sha(host_dir / 'results/result.json'),
        host_test_counts=dict(debug=36, asan_ubsan=36),
        retired_cpu_cohorts=retired_cpu,
        source_variant_manifest=manifest_path, provider_file_count=1028,
        previous_release=previous_path, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/q2-hc-rms-owner-ordinary-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-hc-rms-owner-ordinary-window.py'),
        admission_path='config/q2-hc-rms-owner-ordinary-window-admission.json',
        release_path='config/q2-hc-rms-owner-ordinary-window-release.json',
        core_closure_sha256=sha(core),
        core_cpu_lease=dict(path=REMOTE + 'root-terminal-bench-r16/client.lock', device=52, inode=4486194),
        core_identities=[dict(pid=pid, start_ticks=start) for pid, start in
                         ((20794, 179631020), (20860, 179631128), (20925, 179631192))],
        core_groups=[20794, 20860],
        supplemental_cpu=dict(path=REMOTE + 'q2-down-register-palette-registry-host-r2/result.json',
                              receipt=supplemental_rows[0], local_evidence_sha256=sha(supplemental)),
        component_qualification='config/q2-hc-norm-owner-component-results.json',
        component_rerun=False, controls_rebuilt_or_rerun=False, original_tester_unchanged=True,
        scope='One new original-Q2 ordinary RMS model candidate at exact2048/tg128. '
              'Qualified component and saved Q2/UD/1585-parent reused without rebuild or rerun. '
              'No MoE, executor lifetime, callback, buffer, Q4 or full-curve changes. '
              'Collect, retire and release before local numerical/performance analysis.',
        **{key: old[key] for key in point_keys})
    require(plan['run_controls'] is False, 'Saved controls must not be rerun')
    with args.output.open('x') as stream:
        json.dump(plan, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(plan=str(args.output), fixtures=len(fixtures), provider_files=1028,
                         host_checks=72, GPU_admission=False, model_inference=False)))


if __name__ == '__main__':
    main()
