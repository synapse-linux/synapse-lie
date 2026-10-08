#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one new Q8-chain component and original fixed-point model campaign."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    prior = json.loads((ROOT / 'config/q2-compact-expert-chain-plan.json').read_text())
    fixture_names = set(prior['fixtures']) | {
        'tests/q2_producer_q8.hip', 'tests/q2_producer_q8_reference.hip'}
    manifests = ['config/q2-producer-q8-source-v2.json',
        'config/q2-producer-q8-bounded-static.json',
        'config/q2-fixed-prefill-reference.json',
        'config/q2-scaled-wave-pack-model-results.json']
    plan = {k: v for k, v in prior.items() if k not in (
        'fixtures', 'manifests', 'component_cases', 'component_expected_output_pairs')}
    previous = 'config/q2-compact-expert-chain-window-release.json'
    previous_sha = sha(ROOT / previous)
    assert previous_sha == '88dcb8d8d4ef79e78ec412f4e346a63ae125b179d6c5e7cc2a538a0faddf9e5a'
    plan.update(schema='synapse-lie.q2-producer-q8-plan.v1',
        manifests={p: sha(ROOT / p) for p in manifests},
        fixtures={p: sha(ROOT / p) for p in sorted(fixture_names)},
        window_helper='tools/q2-producer-q8-window.py',
        window_helper_sha256=sha(ROOT / 'tools/q2-producer-q8-window.py'),
        previous_release=previous, previous_release_sha256=previous_sha,
        host='q2-producer-q8-host-r1',
        component=dict(mode='producer-q8-check', label='q2-producer-q8-component-r1', variant='producer-q8'),
        arms=[dict(mode='q2-counting-producer-q8', label='q2-producer-q8-model-r1', variant='producer-q8')],
        source_variant_manifest=manifests[0], provider_file_count=1029,
        component_expected_checks=64, component_expected_timing_samples=56,
        component_saved_arrays_per_case=17,
        component_time_scope='Parent F16 and new Q8 gate/up, then full routing+gate/up+packing(if parent)+down. 2048/top10/512 experts, balanced/skew,762839040 active weight bytes. Two warmups/five alternating pairs,three iterations; allocation/upload/checking excluded.',
        protocol='Only new producer-Q8/integer-down candidate based on saved1574, then original2048/tg128 despite safe numerical or timing rejection. Saved original Q2/UD/parent references; no reference rebuild/rerun, Q4, curve, cleanup, tuning or dependencies.',
        format_scope='Full original quantizer D2S6 comparison canonicalized through actual slot maps; independent CPU routing checks, poisoned inactive rows, zero640..767 tails, allocation-end inputs. Down compared to existing raw MMQ plus96 independent FP64 samples per case. F16 parent changes are expected and recorded separately.',
        parent_measured_prefill=1574.505432,
        arithmetic_change='Row-scaled F16 activations/F16-WMMA down replaced with64-value Q8 groups/integer-MMQ Q2 down; gate/up and F32 SwiGLU retained.',
        initial_spilling_source_retained='config/q2-producer-q8-source.json',
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
            after_release_sha256=previous_sha, fresh_nonuse_before_admission_required=True,
            root_cpu_client_must_be_closed_before_numerical_admission=True,
            admission_still_required=True))
    cases = {}
    for n in (1, 9, 17, 33, 97):
        for gate in (16, 48, 64, 128):
            for down in (16, 48, 64):
                cases[f'tokens-{n}-gate-{gate}-down-{down}'] = dict(tokens=n,
                    used=3, experts=7, inner=256, out_width=129, gate_width=gate,
                    down_width=down, capacity=n*3+7*15, skew=False)
    for skew in (False, True):
        for suffix in ('before', 'after'):
            cases[('skew' if skew else 'balanced')+'-'+suffix] = dict(tokens=2048,
                used=10, experts=512, inner=2560, out_width=2560, gate_width=0,
                down_width=48, capacity=28160, skew=skew)
    plan['component_cases'] = cases
    assert len(cases) == 64
    with (ROOT / 'config/q2-producer-q8-plan.json').open('x') as f:
        json.dump(plan, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(fixtures=len(fixture_names), manifests=len(manifests),
        component_cases=len(cases), gpu_run=False)))

if __name__ == '__main__':
    main()
