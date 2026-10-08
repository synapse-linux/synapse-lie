#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze only the new alternating-buffer SSM component and original model."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm_followup_contract', ROOT / 'tools/analyze-q2-ssm-followup.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous_path = 'config/q2-ssm-row-group-window-release.json'
    previous_sha = sha(ROOT / previous_path)
    assert previous_sha == '413de339b4bacb22e34cb5c0221535dca0831ada6a1b7e4c2b074d9b4d1e3d99'
    previous = json.loads((ROOT / previous_path).read_text())
    assert not previous['gpu_reserved'] and not previous['kfd'] and previous['model_stats_unchanged']
    original = json.loads((ROOT / 'config/q2-ssm-row-group-plan.json').read_text())
    fixtures = set(original['fixtures']) | {
        'tests/q2_ssm_compact_lds.hip', 'experiments/q2-ssm-compact-lds-oracle.inc',
    }
    applied = json.loads((ROOT / 'config/q2-ssm-followup-runtime-applied.json').read_text())
    assert applied['patch_applied']
    for name, digest in applied['files'].items():
        assert sha(ROOT / name) == digest, name
    # Only the three already checked launcher/build files change from the
    # completed campaign; all counting tester and numerical controls stay exact.
    for name, digest in original['fixtures'].items():
        assert sha(ROOT / name) == applied['files'].get(name, digest), name
    manifests = [
        'config/q2-ssm-pingpong-source.json', 'config/q2-ssm-pingpong-static.json',
        'config/q2-down-register-scatter-model-results.json', 'config/q2-fixed-prefill-reference.json',
        'config/q2-ssm-followup-runtime-source.json', 'config/q2-ssm-followup-runtime-applied.json',
        'tools/analyze-q2-ssm-followup.py', 'tools/analyze-q2-ssm-row-group-component.py',
        'tests/q2_ssm_followup_analysis_test.py', 'tools/freeze-q2-ssm-pingpong-plan.py',
    ]
    helper = 'tools/q2-ssm-pingpong-window.py'
    plan = dict(analysis.PROTOCOL,
        schema='synapse-lie.q2-ssm-followup-plan.v1',
        fixtures={name: sha(ROOT / name) for name in sorted(fixtures)},
        manifests={name: sha(ROOT / name) for name in manifests},
        source_variant_manifest=manifests[0],
        window_helper=helper, window_helper_sha256=sha(ROOT / helper),
        previous_release=previous_path, previous_release_sha256=previous_sha,
        release_path='config/q2-ssm-pingpong-window-release.json',
        host='q2-ssm-pingpong-host-r1', host_test_counts=dict(debug=27, asan_ubsan=27),
        components=[dict(label='q2-ssm-pingpong-component-r1', mode='ssm-pingpong-check', variant='ssm-pingpong')],
        arms=[dict(label='q2-ssm-pingpong-model-r1', mode='q2-counting-ssm-pingpong', variant='ssm-pingpong')],
        parent_measured_prefill=1580.226725, parent_measured_decode=25.10411864,
        component_resource_records=2,
        component_time_scope=(
            'Only M16384/N2048/K2560. Literal saved1580 SSM group1/BK2 versus '
            'compact BK1 with XOR transpose and alternating activation slots. '
            'Complete projection plus unchanged boundary convolution; three weight '
            'rotations, two warmups/five measured samples per arm in alternating order. '
            'Setup, copies and validation excluded. Resource API values are theoretical limits.'),
        protocol=(
            'One new SSM alternating-buffer candidate from saved1580.226725, '
            'not composed with the measured row-group trial or fixed-shape variants. '
            'Preserve original exact2048/tg128 model protocol and saved Q2/UD/1580 '
            'references; no old candidate/control rerun or recompile, Q4, full curve, '
            'dependency installation, tuning or cleanup. Safe numerical/timing '
            'rejection still retains model performance; unsafe writes/runtime failures stop.'),
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
                      core_nonuse_confirmed_after_release=previous_sha,
                      fresh_admission_required=True),
        runtime_patch_applied=True, gpu_run=False, model_inference=False,
        numerical_acceptance=False, goal_met=False)
    analysis.validate_scope(plan, 'ssm-pingpong')
    assert len(fixtures) == 90
    output = ROOT / 'config/q2-ssm-pingpong-plan.json'
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    analysis.bound_plan(output, 'ssm-pingpong')
    print(json.dumps(dict(fixtures=90, manifests=len(manifests), previous_release_sha256=previous_sha,
                          candidate='ssm-pingpong', original_protocol_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
