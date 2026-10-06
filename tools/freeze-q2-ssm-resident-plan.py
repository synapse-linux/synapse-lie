#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the SSM resident component after actual .157 host collection."""
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
    output = ROOT / 'config/q2-ssm-resident-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-hc-up-short-chain-model-plan.json')
    names = set(prior['fixtures']) | {
        'tests/q2_ssm_resident.hip', 'experiments/q2-ssm-resident-oracle.inc',
        'tools/q2-ssm-resident-window.py', 'tools/q2-ssm-resident-phase.py',
        'tools/freeze-q2-ssm-resident-plan.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    label = 'q2-ssm-resident-host-r1'
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
        'config/q2-ssm-resident-fixture.json', 'config/q2-hc-up-short-chain-static.json',
        'config/q2-hc-focus-reassessment.json',
        'config/q2-iq2-fixed-bounds-source.json',
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
    static = read(ROOT / 'config/q2-hc-up-short-chain-static.json')
    require(static['source_manifest_sha256'] == sha(ROOT / 'config/q2-iq2-fixed-bounds-source.json') and
            all(v['original_kernels_exact'] == 164 and sha(ROOT / v['draft']) == v['draft_sha256']
                for v in static['variants'].values()), 'Draft source binding differs')
    fixture = read(ROOT / 'config/q2-ssm-resident-fixture.json')
    require(all(sha(ROOT / name) == value for name, value in fixture['bindings'].items()) and
            fixture['selected'] == 'ssm-resident-fence' and
            sha(ROOT / fixture['compile_receipt']) == fixture['compile_receipt_sha256'] and
            read(ROOT / fixture['compile_receipt'])['exit_code'] == 0,
            'SSM fixture or compilation binding differs')
    previous = 'config/q2-hc-up-short-chain-model-window-release.json'
    require(sha(ROOT / previous) == '39a36b31c64fb3d6dd54104ca3deee203ee2a513e3884946e63da43d05281398',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-ssm-resident-plan.v1',
        fixtures=fixtures, manifests=manifests, arms=[],
        components=[dict(label='q2-ssm-resident-component-r1',
                         mode='ssm-resident-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT / previous),
        window_helper='tools/q2-ssm-resident-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-ssm-resident-window.py'),
        admission_path='config/q2-ssm-resident-window-admission.json',
        release_path='config/q2-ssm-resident-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], cases=5, pair_records=72, oracle_records=144,
        timing_records=14, timing_cases=1, warmups=2, measured_repeats=5,
        timing_weight_banks=3, timing_weight_bytes=133693440,
        timed_output_pairs_before_overwrite=42,
        timing_arms=['retained_SSM', 'resident_fence_SSM'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='One new synthetic SSM projection+convolution component on .157, M16384/K2560. '
              'Five guarded1024/1025/1057/2048/2049-row cases preserve raw-live masks and boundary history. '
              'Three independent weight rotations beyond32MiB, two warmups and five alternating repeats. '
              'Three distinct timed destinations per arm are checked before overwrite. '
              'Both complete buffers plus sampled FP64 dot/convolution/SiLU formulas use original0.002 limits. '
              'Finite disagreement retains all timings and exit1; guard/unwritten/nonfinite/device errors stop. '
              'Completed monotonic wall and raw HIP timers stay separate; invalid events are not speed evidence. '
              'No model, saved model-control rerun, Q4, full curve or cleanup. '
              'Collect every artifact, retire and publish closure before analysis; fixed2048/TG128 reference unchanged.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts,
                         plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
