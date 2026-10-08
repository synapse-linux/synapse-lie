#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the new scalar decode component after its actual .157 host checks."""
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
PREFIX = 'q2-decode-q8-compact'
PREVIOUS_SHA = '1d62a3a5f1535ae9fa317923b41c096507e25a0da0af49da27d933cca3a2e559'


def main():
    output = ROOT / ('config/' + PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-select-live-grid-model-plan.json')
    names = set(prior['fixtures']) | {
        'tests/q2_decode_q8_compact.hip', 'experiments/' + PREFIX + '.inc',
        'experiments/q2-decode-q8-control.inc', 'tools/prepare-' + PREFIX + '.py',
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
        'config/' + PREFIX + '-source.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    source = read(ROOT / ('config/' + PREFIX + '-source.json'))['variants']['decode-q8-compact']
    provider = ROOT / source['source']
    require({p.relative_to(provider).as_posix(): sha(p) for p in provider.rglob('*')
             if p.is_file()} == source['files'], 'Candidate provider inventory differs')
    static = read(ROOT / ('config/' + PREFIX + '-static.json'))
    require(static['source_manifest_sha256'] == sha(ROOT / ('config/' + PREFIX + '-source.json')) and
            len(static['all_q8_original_bodies_exact']) == 28 and
            sha(ROOT / static['control_include']) == static['control_sha256'],
            'Kernel/control binding differs')
    fixture = read(ROOT / ('config/' + PREFIX + '-fixture.json'))
    require(all(sha(ROOT / name) == value for name, value in fixture['bindings'].items()) and
            sha(ROOT / fixture['compile_receipt']) == fixture['compile_receipt_sha256'] and
            read(ROOT / fixture['compile_receipt'])['exit_code'] == 0,
            'Fixture compilation differs')
    previous = 'config/q2-select-live-grid-model-window-release.json'
    require(sha(ROOT / previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.' + PREFIX + '-plan.v1', fixtures=fixtures,
        manifests=manifests, arms=[],
        preparation_tools={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        components=[dict(label=PREFIX + '-component-r1', mode='decode-q8-compact-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=39, asan_ubsan=39),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/' + PREFIX + '-window.py',
        window_helper_sha256=sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        admission_path='config/' + PREFIX + '-window-admission.json',
        release_path='config/' + PREFIX + '-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[dict(label='q2-select-live-grid-model-host-r2', result_sha256='a533e7e125b4909435375ed79db2317500283c3b42bc2b4250368d9c29b29853')], cases=8, pair_records=2038, oracle_records=4076,
        timing_records=56, timing_cases=4, warmups=2, measured_repeats=5,
        timing_shapes=[dict(name=name, m=m, k=k, gated=gated, banks=banks, iterations=iterations)
                       for name,m,k,gated,banks,iterations in (
                           ('ssm-in',16384,2560,False,2,64), ('attn-out',2560,6144,False,4,64),
                           ('shared-down',2560,640,False,29,87), ('gated',640,2560,True,15,75))],
        timed_output_pairs_before_overwrite=2030,
        timing_arms=['retained_scalar_Q8', 'uniform_sweep_DPP_Q8'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='One new scalar dense-Q8 consumer component, preserving encoded operands and the FP32 tree. '
              'Uniform complete K groups plus original final-tail guard; exact permlanex16/DPP XOR exchange. '
              'Production hipMalloc placement, rotating weights above48MiB, at least64 calls with distinct '
              'destinations per sample. Four timed real shapes, K2592 tiny tail and K224/256/288 boundaries. '
              'Every timed destination is checked before overwrite; literal saved GPU control and FP64 oracle. '
              'Finite disagreements retain timings. Guard/nonfinite/unwritten/device failures stop. '
              'New component timings are not directly compared with earlier shorter microbenchmark samples. '
              'No model, quantizer, HTTP, Q4, full curve, saved model-control rerun or cleanup. '
              'Collect and release before analysis; fixed-point parity remains paused.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
