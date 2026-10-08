#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind one new register-scatter candidate to the original fixed Q2 benchmark."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous_plan = json.loads((ROOT/'config/q2-down-half-vector-plan.json').read_text())
    recent = json.loads((ROOT/'config/q2-producer-q8-plan-v2.json').read_text())
    plan = {k:v for k,v in previous_plan.items() if k not in ('fixtures','manifests')}
    fixtures = set(recent['fixtures']) | {
        'tests/q2_down_register_scatter.hip',
        'experiments/q2-down-register-scatter-pair-control.inc',
        'experiments/q2-down-register-scatter-pair-epilogue.inc'}
    manifests = ['config/q2-down-register-scatter-pair-source.json',
                 'config/q2-down-register-scatter-static.json',
                 'config/q2-scaled-wave-pack-model-results.json',
                 'config/q2-fixed-prefill-reference.json']
    previous = 'config/q2-producer-q8-window-release.json'
    previous_sha = sha(ROOT/previous)
    assert previous_sha == 'b52d7308325786da5373cd32095fddc99048403ed07511364c4a4171c19c0de6'
    helper = 'tools/q2-down-register-scatter-window.py'
    plan.update(schema='synapse-lie.q2-down-register-scatter-plan.v2',
        supersedes_plan='config/q2-down-register-scatter-plan-initial.json',
        supersedes_plan_sha256=sha(ROOT/'config/q2-down-register-scatter-plan-initial.json'),
        revision_reason='Correct copied window state names before any remote execution; fixtures,source and numerical scope unchanged.',
        manifests={p:sha(ROOT/p) for p in manifests},
        fixtures={p:sha(ROOT/p) for p in sorted(fixtures)},
        window_helper=helper, window_helper_sha256=sha(ROOT/helper),
        previous_release=previous, previous_release_sha256=previous_sha,
        host='q2-down-register-scatter-host-r1',
        components=[dict(label='q2-down-register-scatter-component-r1',
            mode='down-register-scatter-check',variant='down-register-scatter')],
        arms=[dict(label='q2-down-register-scatter-model-r1',
            mode='q2-counting-down-register-scatter',variant='down-register-scatter')],
        source_variant_manifest=manifests[0], provider_file_count=1027,
        parent_measured_prefill=1574.505432, parent_measured_decode=25.17589001,
        component_expected_output_pairs=705, component_expected_consumer_pairs=93,
        component_expected_timing_samples=28,
        component_shapes=[
            'BN16/48/64: n1/15/16/17/47/48/49/63/64/65/129 by m1/2/8/24/128/129/2560, logicalK640/stored768,e1; three rotations',
            'BN16/48/64: n17/m2560,e1,output base offset68 exercises original unaligned fallback; three rotations',
            'One timed production distribution: n2048,m2560,used10,experts512,BN48; three rotated weight sets'],
        component_weight_rotation_bytes={'512':512*2560*3*84*3},
        component_time_scope='One actual BN48/512-expert distribution. Literal saved1574 down and candidate down, then each plus unchanged ordered MoE/HC consumer. Three rotated weight sets per sample, two warmups/five measurements, alternating arms. Packing, routing setup, copies and checks excluded.',
        protocol='One new register-scatter candidate derived from retained1574.505432. Two half-wave word exchanges replace aligned epilogue LDS transpose. Preserve F32 multiplication,half rounding,WMMA,consumer and buffers. Original2048/tg128 despite safe numerical/timing rejection. Saved originalQ2/UD/parent references; no qualified control rebuild/rerun,Q4,fullcurve,cleanup,dependencies or tuning.',
        format_scope='Complete byte comparisons with literal1574 down and unchanged consumer plus independent integer RN-even conversion of unchangedF32 down. Misaligned base,ragged rows,padded slots,guards,missing writes and input immutability. CPU symbolic routing is not GPU rounding or task-quality evidence.',
        host_test_counts=dict(debug=27,asan_ubsan=27),
        safety_or_runtime_failure_exit=2, safe_numeric_failure_exit=1,
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
            after_release_sha256=previous_sha,fresh_nonuse_before_admission_required=True,
            root_cpu_client_must_be_closed_before_numerical_admission=True,
            admission_still_required=True),
        numerical_acceptance=False,gpu_run=False,goal_met=False)
    assert plan['run_controls'] is False and plan['full_curve'] is False
    with (ROOT/'config/q2-down-register-scatter-plan.json').open('x') as f:
        json.dump(plan,f,indent=2);f.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures),manifests=len(manifests),
        component_pairs=705,consumer_pairs=93,timing_samples=28,gpu_run=False)))


if __name__ == '__main__':
    main()
