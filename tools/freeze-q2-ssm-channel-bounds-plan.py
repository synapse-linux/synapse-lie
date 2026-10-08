#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one channel-predicate candidate and its freshly qualified launcher."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('channels', ROOT / 'tools/analyze-q2-ssm-channel-bounds.py')
channels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(channels)
analysis = channels.base
sha, require, read = analysis.sha, analysis.require, analysis.read


def main():
    prior = read(ROOT / 'config/q2-counter-calibration-v2-plan.json')
    previous = 'config/q2-counter-calibration-v2-window-release.json'
    previous_sha = '7a3722f3ee8aa1b318131a33087f6d504974880e8dca5c9a5e9ed54d8b77f7a5'
    require(sha(ROOT / previous) == previous_sha, 'Prior release changed')
    require(not read(ROOT / previous)['gpu_reserved'], 'Prior GPU reservation remains')
    fixtures = {name: sha(ROOT / name) for name in prior['fixtures']}
    require(len(fixtures) == 105, 'Fixture inventory changed')
    host_label = 'q2-ssm-channel-bounds-host-r1'
    host_path = ROOT / 'evidence' / host_label
    host, _ = analysis.hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']),
            'Fresh host gate incomplete')
    for log in ('03.log', '06.log'):
        require('100% tests passed out of 31' in (host_path / 'results' / log).read_text(),
                'Fresh host test count differs')
    host_binding = analysis.hc.capsule(host_path, fixtures)
    require(host_binding['source_files_verified'] == 1020, 'CPU source count changed')
    manifests = [
        'config/q2-ssm-channel-bounds-source.json',
        'config/q2-ssm-channel-bounds-static.json', analysis.REGISTRY,
        'config/q2-down-register-scatter-model-results.json',
        'config/q2-fixed-prefill-reference.json',
        'config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-ssm-fixed-bounds-source.json',
        'config/q2-ssm-fixed-bounds-plan.json',
        'tools/analyze-q2-ssm-followup.py',
        'tools/analyze-q2-ssm-row-group-component.py',
        'tools/analyze-q2-ssm-channel-bounds.py',
        'tools/analyze-q2-ssm-compact-lds.py',
        'tools/freeze-q2-ssm-channel-bounds-plan.py',
    ]
    helper = 'tools/q2-ssm-channel-bounds-window.py'
    best_report, best_source, best_plan = manifests[5:8]
    plan = dict(analysis.PROTOCOL,
        schema='synapse-lie.q2-ssm-followup-plan.v1', fixtures=fixtures,
        manifests={name: sha(ROOT / name) for name in manifests},
        source_variant_manifest=manifests[0], window_helper=helper,
        window_helper_sha256=sha(ROOT / helper), previous_release=previous,
        previous_release_sha256=previous_sha,
        release_path='config/q2-ssm-channel-bounds-window-release.json',
        host=host_label, host_test_counts=dict(debug=31, asan_ubsan=31),
        host_result_sha256=sha(host_path / 'results/result.json'),
        host_binding=host_binding, host_rerun_for_changed_launcher=True,
        components=[dict(label='q2-ssm-channel-bounds-component-r1',
                         mode='ssm-channel-bounds-check', variant='ssm-channel-bounds')],
        arms=[dict(label='q2-ssm-channel-bounds-model-r1',
                   mode='q2-counting-ssm-channel-bounds', variant='ssm-channel-bounds')],
        component_control='Literal saved1580; historical model1580 is an additional reference, not the construction parent.',
        construction_parent='ssm-fixed-bounds',
        parent_measured_prefill=1585.308983, parent_measured_decode=25.16079073,
        component_resource_records=0,
        retained_best=dict(report=best_report, sha256=sha(ROOT / best_report),
            variant='ssm-fixed-bounds', label='q2-ssm-fixed-bounds-model-r1',
            source_manifest=best_source, source_manifest_sha256=sha(ROOT / best_source),
            qualified_plan=best_plan, qualified_plan_sha256=sha(ROOT / best_plan)),
        component_time_scope='M16384/N2048/K2560. Literal saved1580 versus new equivalent '
            'block-uniform channel predicates from retained1585. Full projection and boundary '
            'convolution, three weight rotations beyond32MiB, two warmups/five measured pairs '
            'in alternating order; setup/copies/validation excluded.',
        protocol='One new source from retained1585. Original exact2048/tg128 with saved fixedQ2/UD '
            'and retained1585 comparisons. No qualified control rerun/rebuild,Q4,full curve,cleanup, '
            'tuning or dependencies. Safe component numerical/timing rejection still permits model performance.',
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',
                      core_nonuse_persistent=True, fresh_admission_required=True),
        runtime_patch_applied=True, gpu_run=False, model_inference=False,
        numerical_acceptance=False, goal_met=False)
    analysis.validate_scope(plan, 'ssm-channel-bounds')
    output = ROOT / 'config/q2-ssm-channel-bounds-plan.json'
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    analysis.bound_plan(output, 'ssm-channel-bounds')
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifests),
                         host=host_label, host_tests=62, gpu_run=False)))


if __name__ == '__main__':
    main()
