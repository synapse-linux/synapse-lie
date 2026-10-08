#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind one new SSM specialization and reuse byte-identical qualified host gates."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm_analysis', ROOT / 'tools/analyze-q2-ssm-followup.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
sha, require = analysis.sha, analysis.require


def main():
    prior_plan_path = ROOT / 'config/q2-ssm-pingpong-plan.json'
    prior = analysis.read(prior_plan_path)
    previous_path = 'config/q2-ssm-fixed-shape-window-release.json'
    previous_sha = '81d7fcbbe2aea754bbd4bc8acdc044a03275406f15099e2d057695a1333d805a'
    require(sha(ROOT / previous_path) == previous_sha, 'Previous release changed')
    previous = analysis.read(ROOT / previous_path)
    require(not previous['gpu_reserved'] and not previous['kfd'] and previous['model_stats_unchanged'],
            'Previous GPU campaign not closed')
    fixtures = prior['fixtures']
    for name, digest in fixtures.items():
        require(sha(ROOT / name) == digest, 'Qualified fixture changed: ' + name)
    host_path = ROOT / 'evidence' / prior['host']
    host, _ = analysis.hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']),
            'Saved host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 27' in (host_path / 'results' / name).read_text(),
                'Saved host test count changed')
    binding = analysis.hc.capsule(host_path, fixtures)
    require(binding['source_files_verified'] == 1020, 'Saved host source scope changed')
    manifests = [
        'config/q2-ssm-fixed-bounds-source.json', 'config/q2-ssm-fixed-bounds-static.json',
        'config/q2-down-register-scatter-model-results.json', 'config/q2-fixed-prefill-reference.json',
        'config/q2-ssm-followup-runtime-source.json', 'config/q2-ssm-followup-runtime-applied.json',
        'tools/analyze-q2-ssm-followup.py', 'tools/analyze-q2-ssm-row-group-component.py',
        'tests/q2_ssm_followup_analysis_test.py', 'tools/freeze-q2-ssm-fixed-bounds-plan.py',
        'config/q2-ssm-pingpong-plan.json', 'config/q2-ssm-pingpong-host-results.json',
        'config/q2-ssm-fixed-shape-model-results.json', 'tools/analyze-q2-ssm-fixed-bounds.py',
    ]
    helper = 'tools/q2-ssm-fixed-bounds-window.py'
    plan = dict(analysis.PROTOCOL,
        schema='synapse-lie.q2-ssm-followup-plan.v1', fixtures=fixtures,
        manifests={name: sha(ROOT / name) for name in manifests},
        source_variant_manifest=manifests[0], window_helper=helper,
        window_helper_sha256=sha(ROOT / helper), previous_release=previous_path,
        previous_release_sha256=previous_sha, release_path='config/q2-ssm-fixed-bounds-window-release.json',
        host=prior['host'], host_test_counts=prior['host_test_counts'],
        host_reuse=dict(qualified_plan_sha256=sha(prior_plan_path),
                       result_sha256=sha(host_path / 'results/result.json'),
                       **binding, fixtures_byte_identical=True, rerun=False),
        components=[dict(label='q2-ssm-fixed-bounds-component-r1', mode='ssm-fixed-bounds-check', variant='ssm-fixed-bounds')],
        arms=[dict(label='q2-ssm-fixed-bounds-model-r1', mode='q2-counting-ssm-fixed-bounds', variant='ssm-fixed-bounds')],
        parent_measured_prefill=1580.226725, parent_measured_decode=25.10411864,
        component_resource_records=0,
        retained_best=dict(report='config/q2-ssm-fixed-shape-model-results.json',
            sha256='4c76417549a0b208f2e34a8b92456e35f84fbbba11c87045b49e8fa84b08366b',
            variant='ssm-fixed-shape', label='q2-ssm-fixed-shape-model-r1',
            source_manifest='config/q2-ssm-fixed-shape-source.json',
            source_manifest_sha256='9f8e5e96477abc97152fecd647134ef4661b3e09c9a864e436225e60e365872c'),
        component_time_scope='Only M16384/N2048/K2560. Literal saved1580 versus fixed M/K with proven row/K checks removed, '
            'with original geometry, staging and arithmetic order. Complete projection and boundary '
            'convolution, three weight rotations beyond32MiB, two warmups/five measured samples per '
            'arm in alternating order; setup/copies/validation excluded.',
        protocol='One new fixed-M/K and proven-bounds SSM from saved1580; compare also saved1582; no row-group, compact-LDS or pingpong composition. '
            'Reuse qualified byte-identical host gates and all saved model comparisons. Original exact2048/tg128, '
            'no controls rerun/recompile, Q4, curve sweep, dependency installation, tuning or cleanup. '
            'Safe numerical/timing rejection retains model performance; unsafe writes/runtime failures stop.',
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
                      core_nonuse_persistent=True, fresh_admission_required=True),
        runtime_patch_applied=True, gpu_run=False, model_inference=False,
        numerical_acceptance=False, goal_met=False)
    analysis.validate_scope(plan, 'ssm-fixed-bounds')
    output = ROOT / 'config/q2-ssm-fixed-bounds-plan.json'
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    analysis.bound_plan(output, 'ssm-fixed-bounds')
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifests),
                          candidate='ssm-fixed-bounds', host_reused=prior['host'], host_rerun=False,
                          previous_release_sha256=previous_sha, original_protocol_unchanged=True,
                          gpu_run=False)))


if __name__ == '__main__':
    main()
