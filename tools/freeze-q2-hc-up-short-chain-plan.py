#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the HC up short-chain component after actual .157 host collection."""
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
    output = ROOT / 'config/q2-hc-up-short-chain-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-iq2-whole640-chain-plan.json')
    names = set(prior['fixtures']) | {
        'experiments/q2-hc-up-short-chain-draft.inc',
        'experiments/q2-hc-up-short-chain-phased-draft.inc',
        'experiments/q2-ssm-resident-draft.inc',
        'experiments/q2-ssm-resident-fence-draft.inc',
        'tests/q2_hc_up_short_chain.hip',
        'tools/prepare-q2-hc-up-short-chain.py',
        'tools/prepare-q2-ssm-resident-draft.py',
        'tools/analyze-q2-hc-up-short-chain-static.py',
        'tools/freeze-q2-hc-up-short-chain-plan.py',
        'tools/q2-hc-up-short-chain-window.py',
        'tools/q2-hc-up-short-chain-phase.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    label = 'q2-hc-up-short-chain-host-r1'
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
        'config/q2-hc-up-short-chain-static.json', 'config/q2-hc-focus-reassessment.json',
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
    require(static['selected'] == 'hc-up-short-chain-phased' and
            static['fixture_sha256'] == sha(ROOT / 'tests/q2_hc_up_short_chain.hip') and
            read(ROOT / 'evidence/q2-hc-up-short-chain-fixture-preparation/compile-command.json')['exit_code'] == 0,
            'Selected fixture binding or compilation differs')
    previous = 'config/q2-iq2-whole640-chain-window-release.json'
    require(sha(ROOT / previous) == 'cb652eb5be2dccd340ba35a03c4aaa418de5c45994ea94616da85c8f4f29a136',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-hc-up-short-chain-plan.v1',
        fixtures=fixtures, manifests=manifests, arms=[],
        components=[dict(label='q2-hc-up-short-chain-component-r1',
                         mode='hc-up-short-chain-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT / previous),
        window_helper='tools/q2-hc-up-short-chain-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-hc-up-short-chain-window.py'),
        admission_path='config/q2-hc-up-short-chain-window-admission.json',
        release_path='config/q2-hc-up-short-chain-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], cases=12, pair_records=702, oracle_records=468,
        timing_records=28, timing_cases=2, warmups=2, measured_repeats=5,
        timing_weight_banks=16, timing_weight_bytes=104857600,
        timing_arms=['retained_paired_waves', 'short_chain_phased'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='One new synthetic original-F16 HC up/mix component on .157, ordinary and '
              'deferred normalization. Twelve guarded cases include ragged rows, tiny values, '
              'cancellation and repeated rows; two full2048 timing cases rotate100MiB weights '
              'through16 distinct output states, two warmups and five alternating repeats. '
              'Every actual timed buffer is checked before overwrite; independent FP64 formula '
              'and complete parent/candidate comparison retain finite disagreements and all timings. '
              'Guard/unwritten/nonfinite/device failures stop subsequent GPU work. '
              'The candidate deliberately changes FP32 reduction order; no tolerance relaxation. '
              'No model, saved model-control rerun, curve, Q4 or cleanup. Collect every artifact, '
              'retire and publish release before analysis. Original2048/TG128 reference, source '
              'and production selectors remain unchanged.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts,
                         plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
