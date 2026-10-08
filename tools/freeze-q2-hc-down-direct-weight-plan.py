#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze only the new HC-down component after actual .157 host collection."""
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
PREFIX = 'q2-hc-down-direct-weight'
PREVIOUS_SHA = '8410ceb712d72e9bbc531cb49e49800062be3f476574cfd47a0fb61729388fe0'


def main():
    output = ROOT / ('config/' + PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-ssm-resident-plan.json')
    names = set(prior['fixtures']) | {
        'tests/q2_hc_down_direct_weight.hip', 'experiments/' + PREFIX + '.inc',
        'tools/prepare-' + PREFIX + '.py', 'tools/' + PREFIX + '-window.py',
        'tools/' + PREFIX + '-phase.py'}
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
        'config/q2-hc-focus-reassessment.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-iq2-fixed-bounds-model-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    variant = read(ROOT / 'config/q2-iq2-fixed-bounds-source.json')['variants']['iq2-fixed-bounds']
    provider = ROOT / variant['source']
    require({p.relative_to(provider).as_posix(): sha(p) for p in provider.rglob('*')
             if p.is_file()} == variant['files'] and len(variant['files']) == 1028,
            'Retained provider inventory differs')
    static = read(ROOT / ('config/' + PREFIX + '-static.json'))
    require(static['parent_manifest_sha256'] == sha(ROOT / 'config/q2-iq2-fixed-bounds-source.json') and
            static['original_device_bodies_exact'] == 164 and
            static['draft_sha256'] == sha(ROOT / ('experiments/' + PREFIX + '.inc')),
            'Private draft binding differs')
    fixture = read(ROOT / ('config/' + PREFIX + '-fixture.json'))
    require(all(sha(ROOT / name) == value for name, value in fixture['bindings'].items()) and
            sha(ROOT / fixture['compile_receipt']) == fixture['compile_receipt_sha256'] and
            read(ROOT / fixture['compile_receipt'])['exit_code'] == 0,
            'Fixture compilation differs')
    previous = 'config/q2-ssm-resident-window-release.json'
    require(sha(ROOT / previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.' + PREFIX + '-plan.v1', fixtures=fixtures,
        manifests=manifests, arms=[],
        preparation_tools={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        components=[dict(label=PREFIX + '-component-r1', mode='hc-down-direct-weight-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=39, asan_ubsan=39),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/' + PREFIX + '-window.py',
        window_helper_sha256=sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        admission_path='config/' + PREFIX + '-window-admission.json',
        release_path='config/' + PREFIX + '-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], cases=4, pair_records=160, oracle_records=160,
        timing_records=14, timing_cases=1, warmups=2, measured_repeats=5,
        timing_weight_banks=8, timing_weight_bytes=52428800,
        timed_output_pairs_before_overwrite=112,
        timing_arms=['retained_HC_down', 'direct_weight_HC_down'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='One new synthetic HC-down/SiluScale/F16 consumer sequence, M320/K10240. '
              'N96/97/129/2048 with ordinary, tiny and cancellation inputs. '
              'Eight original-F16 weight banks beyond32MiB and eight distinct output states per arm. '
              'Two warmups/five alternating timed repeats; every timed buffer checked before reuse. '
              'Sampled independent FP64 formula keeps2e-5 limits; exact replay is separate. '
              'Finite disagreement retains timings; guard/nonfinite/unwritten/device faults stop. '
              'Completed monotonic wall time and raw HIP event validity remain separate. '
              'Normalization producer and model cache traffic are not represented by this component. '
              'No model, Q4, full curve, saved model-control rerun or remote cleanup. '
              'Collect and release before analysis; original2048/TG128 benchmark unchanged.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
