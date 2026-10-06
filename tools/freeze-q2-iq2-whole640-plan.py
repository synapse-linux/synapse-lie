#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze only the new whole640 component after actual .157 host collection."""
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
    output = ROOT / 'config/q2-iq2-whole640-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT / 'config/q2-full-prefill128-final-plan.json')
    names = set(prior['fixtures']) | {
        'experiments/q2-iq2-whole640-draft.inc',
        'experiments/q2-iq2-whole640-lds-draft.inc', 'tests/q2_iq2_whole640.hip',
        'tests/q2_operator_fixture.hpp', 'tools/prepare-q2-iq2-whole640-draft.py',
        'tools/analyze-q2-iq2-whole640-static.py',
        'tools/freeze-q2-iq2-whole640-plan.py', 'tools/q2-iq2-whole640-window.py',
        'tools/q2-iq2-whole640-phase.py'}
    fixtures = {name: sha(ROOT / name) for name in sorted(names)}
    label = 'q2-iq2-whole640-host-r1'
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
    require(counts == [38, 38], 'Host gate differs')
    manifests = {name: sha(ROOT / name) for name in (
        'config/q2-iq2-whole640-static.json', 'config/q2-iq2-fixed-bounds-source.json',
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
    static = read(ROOT / 'config/q2-iq2-whole640-static.json')
    require(static['source_manifest_sha256'] == sha(ROOT / 'config/q2-iq2-fixed-bounds-source.json') and
            all(v['original_kernels_exact'] == 164 and sha(ROOT / v['draft']) == v['draft_sha256']
                for v in static['variants'].values()), 'Draft source binding differs')
    require(read(ROOT / 'evidence/q2-iq2-whole640-fixture-preparation/compile-v2-command.json')['exit_code'] == 0,
            'Fixture object did not compile')
    previous = 'config/q2-full-prefill128-final-window-release.json'
    require(sha(ROOT / previous) == '9fffc2e21fd0cf419efa196dce55d320f03732bf5aad73ea3f3450b69b685085',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-iq2-whole640-plan.v1',
        fixtures=fixtures, manifests=manifests, arms=[],
        components=[dict(label='q2-iq2-whole640-component-r1',
                         mode='iq2-whole640-check', variant='iq2-fixed-bounds')],
        host=label, host_result_sha256=sha(directory / 'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT / previous),
        window_helper='tools/q2-iq2-whole640-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-iq2-whole640-window.py'),
        admission_path='config/q2-iq2-whole640-window-admission.json',
        release_path='config/q2-iq2-whole640-window-release.json',
        **{key: prior[key] for key in ('core_closure_sha256', 'core_cpu_lease',
                                      'core_identities', 'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], edge_cases=32, replay_records=56,
        timed_buffer_replays=21, timing_records=63, timing_cases=3,
        timing_arms=['retained_gate_up_then_pack', 'whole640_register', 'whole640_lds'],
        retained_provider_files=1028, run_controls=False, controls_rebuilt_or_rerun=False,
        model_inference=False, GPU_admission=False,
        scope='One new synthetic whole640 gate/up+packing component on .157. '
              '32 guarded edge cases plus three 64-expert timing cases with '
              'three weight rotations, two warmups and five alternating repeats. '
              'Complete final timed buffers, parent F32 output and original dyadic packing '
              'are retained/checked outside timing; finite disagreement does not skip timing. '
              'Guard/unwritten/nonfinite/device failures stop subsequent device work. '
              'No down consumer, model, saved model-control rerun, curve, Q4 or cleanup. '
              'Collect all artifacts, retire and release before analysis. '
              'The exact2048/tg128 model reference and production provider remain unchanged.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts,
                         plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
