#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one new attention component after actual .157 host qualification."""
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
    output = ROOT/'config/q2-attention-capacity-plan.json'
    require(not output.exists(), 'Preserve existing plan')
    prior = read(ROOT/'config/q2-curve256-v3-plan.json')
    names = set(prior['fixtures']) | {
        'experiments/q2_attention_capacity.h', 'tests/q2_attention_capacity.c',
        'tests/q2_attention_capacity_gpu.hip', 'tools/prepare-q2-attention-capacity.py',
        'tools/analyze-q2-attention-capacity-static.py',
        'tools/freeze-q2-attention-capacity-plan.py', 'tools/q2-attention-capacity-window.py',
        'tools/q2-attention-capacity-phase.py', 'experiments/q2-attention-capacity-q2.patch',
        'experiments/q2-attention-capacity-ud.patch'}
    fixtures = {name: sha(ROOT/name) for name in sorted(names)}
    label = 'q2-attention-capacity-host-r1'
    path = ROOT/'evidence'/label
    host, transport = curve.artifact_integrity(path)
    require(host['mode'] == transport['mode'] == 'cpu' and host.get('finished_at') and
        host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
        len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
        transport['exit_code'] == 0, 'Actual .157 host gate incomplete')
    counts = []
    for name in ('03.log', '06.log'):
        text = (path/'results'/name).read_text()
        m = re.search(r'100% tests passed[^\n]*?out of ([0-9]+)', text)
        require(m and 'q2_attention_capacity' in text, 'Host capacity gate missing')
        counts.append(int(m[1]))
    require(counts[0] == counts[1] and counts[0] >= 38, 'Host gate differs')
    manifests = {name: sha(ROOT/name) for name in (
        'config/q2-attention-capacity-source.json', 'config/q2-attention-capacity-static.json',
        'config/q2-curve256-headroom-source.json', 'config/q2-iq2-fixed-bounds-source.json',
        'config/q2-iq2-fixed-bounds-model-results.json', 'config/q2-fixed-prefill-reference.json')}
    with tarfile.open(path/'source.tar.gz') as archive:
        for name, digest in {**fixtures, **manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Host capsule differs: ' + name)
    source = read(ROOT/'config/q2-attention-capacity-source.json')
    for variant in source['variants'].values():
        base = ROOT/variant['source']
        require({p.relative_to(base).as_posix(): sha(p) for p in base.rglob('*')
                 if p.is_file()} == variant['files'], 'Provider inventory differs')
    static = read(ROOT/'config/q2-attention-capacity-static.json')
    require(static['source_manifest_sha256'] == sha(ROOT/'config/q2-attention-capacity-source.json')
            and static['original_kernels_instruction_operand_resource_exact'] == 162
            and len(static['changed_sparse_bodies']) == 2, 'Numerical source binding differs')
    for name in ('assembly', 'static-formatted', 'fixture-host', 'fixture-device'):
        require(read(ROOT/('evidence/q2-attention-capacity-preparation/'+name+'-command.json'))['exit_code'] == 0,
                'Preparation command did not pass')
    previous = 'config/q2-curve256-v3-window-release.json'
    require(sha(ROOT/previous) == '3e59f4175fec424ff6695121becf3c2f66228da89136ab5bd05ada39920cd664',
            'Latest release differs')
    plan = dict(schema='synapse-lie.q2-attention-capacity-plan.v1',
        fixtures=fixtures, manifests=manifests, arms=[],
        components=[dict(label='q2-attention-capacity-component-r1',
                         mode='attention-capacity-check', variant='attention-capacity-q2')],
        host=label, host_result_sha256=sha(path/'results/result.json'),
        host_test_counts=dict(debug=counts[0], asan_ubsan=counts[1]),
        previous_release=previous, previous_release_sha256=sha(ROOT/previous),
        window_helper='tools/q2-attention-capacity-window.py',
        window_helper_sha256=sha(ROOT/'tools/q2-attention-capacity-window.py'),
        admission_path='config/q2-attention-capacity-window-admission.json',
        release_path='config/q2-attention-capacity-window-release.json',
        **{k: prior[k] for k in ('core_closure_sha256', 'core_cpu_lease', 'core_identities',
                                'core_groups', 'supplemental_cpu')},
        retired_cpu_cohorts=[], correctness_cases=8, timing_cases=2, timing_samples=28,
        source_variant='q2', maximum_visible_tokens=266240,
        controls_rebuilt_or_rerun=False, model_inference=False, GPU_admission=False,
        scope='One new guarded sparse-attention component. Eight FP64 cases cover short '
              'visible spans with oversized allocation pitch, native boundary, headroom, '
              'compact/bitset union, replay, last-only output and immutable inputs. '
              'Two production-shaped 128-row timing cases compare WMMA to the unchanged '
              'GPU fallback at16K/256K with two warmups/five alternating repeats. '
              'Finite numerical rejection is retained and does not skip timing; unsafe '
              'device work stops. No model, full curve, Q4, conversion or cleanup. '
              'Collect all artifacts, retire and release before analysis. Fixed target unchanged.')
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), host_test_counts=counts,
                         plan_sha256=sha(output), GPU_admission=False)))


if __name__ == '__main__':
    main()
