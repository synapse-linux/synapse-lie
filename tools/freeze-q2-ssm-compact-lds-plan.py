#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the unmeasured compact-LDS source and byte-identical host qualification."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm_analysis', ROOT / 'tools/analyze-q2-ssm-followup.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
sha, require, read = analysis.sha, analysis.require, analysis.read


def main():
    prior_path = ROOT / 'config/q2-compressed-cache-plan.json'
    prior = read(prior_path)
    previous_path = 'config/q2-compressed-cache-window-release.json'
    previous_sha = 'a94c8b81e150641423391f00620a68caa635575cf454245389fd39a866ec0df5'
    require(sha(ROOT / previous_path) == previous_sha, 'Previous release changed')
    previous = read(ROOT / previous_path)
    require(not previous['gpu_reserved'] and not previous['kfd'] and previous['model_stats_unchanged'],
            'Previous GPU campaign not closed')
    fixtures = prior['fixtures']
    for name, digest in fixtures.items():
        require(sha(ROOT / name) == digest, 'Qualified fixture changed: ' + name)
    host_path = ROOT / 'evidence' / prior['host']
    host, _ = analysis.hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            sha(host_path / 'results/result.json') == prior['host_result_sha256'],
            'Saved host gate incomplete or changed')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 30' in (host_path / 'results' / name).read_text(),
                'Saved host test count changed')
    binding = analysis.hc.capsule(host_path, fixtures)
    require(binding['source_files_verified'] == 1020, 'Saved host source scope changed')
    static = read(ROOT / 'config/q2-ssm-compact-lds-static.json')
    for arm in ('parent', 'candidate'):
        require(sha(ROOT / static[arm + '_assembly_path']) == static[arm + '_assembly_sha256'],
                'Previously compiled assembly changed')
    manifests = [
        'config/q2-ssm-compact-lds-source.json', 'config/q2-ssm-compact-lds-static.json',
        'config/q2-down-register-scatter-model-results.json', 'config/q2-fixed-prefill-reference.json',
        'config/q2-ssm-followup-runtime-source.json', 'config/q2-ssm-followup-runtime-applied.json',
        'tools/analyze-q2-ssm-followup.py', 'tools/analyze-q2-ssm-row-group-component.py',
        'tests/q2_ssm_followup_analysis_test.py', 'tools/freeze-q2-ssm-compact-lds-plan.py',
        'config/q2-compressed-cache-plan.json', 'config/q2-compressed-cache-final-audit.json',
        'config/q2-ssm-fixed-bounds-model-results.json', 'config/q2-ssm-fixed-bounds-plan.json',
        'tools/analyze-q2-ssm-compact-lds.py',
    ]
    helper = 'tools/q2-ssm-compact-lds-window.py'
    best_report = 'config/q2-ssm-fixed-bounds-model-results.json'
    best_source = 'config/q2-ssm-fixed-bounds-source.json'
    best_plan = 'config/q2-ssm-fixed-bounds-plan.json'
    plan = dict(analysis.PROTOCOL,
        schema='synapse-lie.q2-ssm-followup-plan.v1', fixtures=fixtures,
        manifests={name: sha(ROOT / name) for name in manifests},
        source_variant_manifest=manifests[0], window_helper=helper,
        window_helper_sha256=sha(ROOT / helper), previous_release=previous_path,
        previous_release_sha256=previous_sha, release_path='config/q2-ssm-compact-lds-window-release.json',
        host=prior['host'], host_test_counts=prior['host_test_counts'],
        host_reuse=dict(qualified_plan_sha256=sha(prior_path),
                       result_sha256=sha(host_path / 'results/result.json'),
                       **binding, fixtures_byte_identical=True, rerun=False),
        components=[dict(label='q2-ssm-compact-lds-component-r1', mode='ssm-compact-lds-check', variant='ssm-compact-lds')],
        arms=[dict(label='q2-ssm-compact-lds-model-r1', mode='q2-counting-ssm-compact-lds', variant='ssm-compact-lds')],
        parent_measured_prefill=1580.226725, parent_measured_decode=25.10411864,
        component_resource_records=2,
        retained_best=dict(report=best_report, sha256=sha(ROOT / best_report),
            variant='ssm-fixed-bounds', label='q2-ssm-fixed-bounds-model-r1',
            source_manifest=best_source, source_manifest_sha256=sha(ROOT / best_source),
            qualified_plan=best_plan, qualified_plan_sha256=sha(ROOT / best_plan)),
        component_time_scope='Only M16384/N2048/K2560. Literal saved1580 versus prepared BK1/XOR compact LDS. '
            'Complete projection and boundary convolution, three weight rotations beyond32MiB, '
            'two warmups/five measured samples per arm in alternating order; setup/copies/validation excluded.',
        protocol='One new prepared compact-LDS SSM from construction parent1580, compared also with retained1585 '
            'and unchanged fixed Q2/UD. No fixed-shape/bounds composition. Reuse byte-identical host30+30. '
            'Original exact2048/tg128; no saved controls rerun/recompile,Q4,curve,dependencies,tuning or cleanup. '
            'Safe numerical/timing rejection retains model performance; unsafe writes/runtime failures stop.',
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
                      core_nonuse_persistent=True, fresh_admission_required=True),
        runtime_patch_applied=True, gpu_run=False, model_inference=False,
        numerical_acceptance=False, goal_met=False)
    analysis.validate_scope(plan, 'ssm-compact-lds')
    output = ROOT / 'config/q2-ssm-compact-lds-plan.json'
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    analysis.bound_plan(output, 'ssm-compact-lds')
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifests),
        candidate='ssm-compact-lds', host_reused=prior['host'], host_rerun=False,
        previous_release_sha256=previous_sha, original_protocol_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
