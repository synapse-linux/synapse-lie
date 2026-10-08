#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one SSM traversal candidate on the retained 1580 Q2 provider."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior = json.loads((ROOT / 'config/q2-down-register-scatter-plan.json').read_text())
    fixtures = set(prior['fixtures']) | {
        'tests/q2_ssm_row_group.hip',
        'experiments/q2-ssm-row-group-control.inc',
        'experiments/q2-ssm-row-group-oracle.inc',
    }
    manifests = [
        'config/q2-ssm-row-group-compose-source.json',
        'config/q2-ssm-row-group-compose-static.json',
        'config/q2-down-register-scatter-model-results.json',
        'config/q2-fixed-prefill-reference.json',
        'config/q2-ssm-row-group-fixture.json',
    ]
    previous = 'config/q2-down-register-scatter-window-release.json'
    previous_sha = sha(ROOT / previous)
    assert previous_sha == 'b9e05fd2abb1736794dccca78250187522e9a5a3fe467bfdc3c3f3a0f49f422e'
    helper = 'tools/q2-ssm-row-group-window.py'
    fixed_keys = ('model_performance_test_despite_numeric_or_timing_rejection',
                  'run_controls', 'input_sha256', 'context_capacity', 'chunk',
                  'prompt_tokens', 'output_tokens', 'timed_decode_calls',
                  'warmups', 'repetitions', 'cooldown_seconds', 'mtp',
                  'component_guard_failure_stops_device_work',
                  'component_unwritten_failure_stops_device_work',
                  'full_curve', 'dependencies', 'tuning', 'cleanup')
    plan = {key: prior[key] for key in fixed_keys}
    plan.update(
        schema='synapse-lie.q2-ssm-row-group-plan.v1',
        fixtures={p: sha(ROOT / p) for p in sorted(fixtures)},
        manifests={p: sha(ROOT / p) for p in manifests},
        window_helper=helper, window_helper_sha256=sha(ROOT / helper),
        previous_release=previous, previous_release_sha256=previous_sha,
        host='q2-ssm-row-group-host-r1',
        components=[dict(label='q2-ssm-row-group-component-r1',
                         mode='ssm-row-group-check', variant='ssm-row-group')],
        arms=[dict(label='q2-ssm-row-group-model-r1',
                   mode='q2-counting-ssm-row-group', variant='ssm-row-group')],
        source_variant_manifest=manifests[0], provider_file_count=1027,
        parent_measured_prefill=1580.226725, parent_measured_decode=25.10411864,
        component_expected_output_pairs=30, component_expected_oracle_checks=60,
        component_expected_timing_samples=14,
        component_shapes=[1024, 1025, 1057, 2048, 2049],
        component_output_rows=16384, component_inner=2560,
        component_convolution_channels=10240, component_convolution_taps=4,
        component_rotations=3, component_weight_rotation_bytes=133693440,
        component_time_scope=(
            'Only M16384/N2048/K2560. Literal saved1580 SSM group1 versus group4, '
            'including the unchanged convolution-boundary kernel. Three rotated '
            'weight sets per sample; two warmups and five measurements per arm, '
            'alternating order. Input setup, copies and validation excluded.'),
        protocol=(
            'One new candidate composed with saved1580.226725. Change only SSM '
            'grid traversal from row-group1 to4; preserve geometry, arithmetic, '
            'convolution boundaries, allocations, streams and launch count. '
            'Run original2048/tg128 despite safe numerical or timing rejection. '
            'Use saved original Q2, UD and parent model results. No qualified '
            'control rebuild/rerun, Q4, full curve, cleanup, dependencies or tuning.'),
        format_scope=(
            'Thirty complete projection/convolution pairs with the literal '
            'parent, sixty sampled independent FP64 operator checks of24 '
            'outputs each, original0.002 limits. Cover ragged rows, initial '
            'history,32-token convolution boundaries, intentionally unused raw '
            'rows, guards, required writes and immutable inputs. CPU symbolic '
            'mapping checks do not establish GPU numerics or model quality.'),
        host_test_counts=dict(debug=27, asan_ubsan=27),
        safety_or_runtime_failure_exit=2, safe_numeric_failure_exit=1,
        allocation_capacity_unchanged=True,
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
                      after_release_sha256=previous_sha,
                      fresh_nonuse_before_admission_required=True,
                      root_cpu_client_must_be_closed_before_numerical_admission=True,
                      admission_still_required=True),
        numerical_acceptance=False, gpu_run=False, goal_met=False)
    assert len(fixtures) == 88
    assert not plan['run_controls'] and not plan['full_curve']
    with (ROOT / 'config/q2-ssm-row-group-plan.json').open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifests),
                          parent_prefill=plan['parent_measured_prefill'], gpu_run=False)))


if __name__ == '__main__':
    main()
