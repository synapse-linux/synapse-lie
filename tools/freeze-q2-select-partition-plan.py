#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the new exact partition selector after its actual .157 host checks."""
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
PREFIX = 'q2-select-partition'
PREVIOUS_SHA = '7c5193f944c7e135e678b48bc62e2517d2c913c80e6215f4817a25f03ee7042b'


def main():
    output = ROOT / ('config/' + PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-attention-v-stage-plan.json')
    names = set(prior['fixtures']) | {
        'tests/q2_select_partition.hip', 'experiments/q2-select-partition.inc', 'tools/freeze-' + PREFIX + '-plan.py',
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
        require('100% tests passed out of 42' in log and 'q2_remote' in log,
                'Current Debug/ASan launcher checks missing')
    manifests = {name: sha(ROOT / name) for name in (
        'config/q2-select-partition-static.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-full-prefill128-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    previous = 'config/q2-attention-v-stage-window-release.json'
    require(sha(ROOT / previous) == PREVIOUS_SHA, 'Latest release differs')
    plan = dict(schema='synapse-lie.' + PREFIX + '-plan.v1', fixtures=fixtures,
        manifests=manifests, arms=[],
        preparation_tools={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        components=[dict(label=PREFIX + '-component-r1', mode='select-partition-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=42, asan_ubsan=42),
        previous_release=previous, previous_release_sha256=PREVIOUS_SHA,
        window_helper='tools/' + PREFIX + '-window.py',
        window_helper_sha256=sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        admission_path='config/' + PREFIX + '-window-admission.json',
        release_path='config/' + PREFIX + '-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], cases=16, pair_records=56,
        timing_records=88, timing_cases=4, warmups=2, measured_repeats=9,
        timing_shapes=[dict(name=name,complete=n) for name,n in (
            ('decode32',8178), ('decode64',16360), ('decode128',32731), ('ties128',32731))],
        mask_words=1045, score_pitch=33440, ratio=4, budget=512, capacity=133760,
        timing_arms=['retained_single_workgroup','two_stage_partition'],
        partitions=9, partition_blocks=4096, candidate_slots=4608, scratch_bytes=36864,
        synthetic_scores=True, controls_rebuilt_or_rerun=False, model_inference=False,
        GPU_admission=False,
        scope='One new C1 decode selection component, fixed HIP graphs reused across device '
              'positions. Exact local top512 over nine4096-block slices, compact512 candidates '
              'per slice, then exact merge and original-index scatter. Integer score keys, '
              'same lower-index tie rule. Full host sort oracle for every timed/untimed output; '
              'device/input guards. Boundary511/512/513/4095/4096/4097, capacity33440, zeros, '
              'ties, ordered/clipped/adjacent/subnormal keys. Four timing cases, two warmups '
              'and nine repetitions, original control literal on same input. No model/control '
              'replay or rebuild, prefill/chunk change, Q4, dependencies, tuning or cleanup. '
              'Collect and release before analysis.')

    with output.open('x') as stream:
        json.dump(plan, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
