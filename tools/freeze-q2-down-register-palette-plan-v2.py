#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one real-route register-stage candidate and the unchanged saved comparisons."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('component', ROOT/'tools/analyze-q2-down-register-palette-component.py')
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)
hc = component.hc
read, require, sha = hc.read, hc.require, hc.sha


def main():
    old = read(ROOT/'config/q2-down-register-palette-plan.json')
    fixtures = {name:sha(ROOT/name) for name in old['fixtures']}
    for name in ('tests/q2_down_register_palette_phase_test.py', 'tools/q2-down-register-palette-phase.py'):
        require(name not in fixtures, 'Fixture already present')
        fixtures[name] = sha(ROOT/name)
    require(len(fixtures) == 122, 'Fixture scope changed')
    host_path = ROOT/'evidence/q2-down-register-palette-host-r2'
    host, transport = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Host gate incomplete')
    for log in ('03.log','06.log'):
        require('100% tests passed out of 34' in (host_path/'results'/log).read_text(), 'Missing host checks')
    binding = hc.capsule(host_path, fixtures)
    hc.write(ROOT/'config/q2-down-register-palette-host-v2-results.json', dict(binding,
        command_exits=[0]*6, artifacts_verified=len(host['artifacts']),
        result_sha256=sha(host_path/'results/result.json'), debug=34, asan_ubsan=34,
        gpu_run=False, model_inference=False))
    plan = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    for key in ('schema','window_helper','host','source_variant_manifest'):
        plan[key] = plan[key].replace('iq2-four-wave','down-register-palette')
    plan['source_variant_manifest'] = 'config/q2-down-register-palette-source.json'
    for key in ('arms','components'):
        plan[key] = [{k:v.replace('iq2-four-wave','down-register-palette') for k,v in row.items()} for row in plan[key]]
    plan['host']='q2-down-register-palette-host-r2'
    plan['window_helper']='tools/q2-down-register-palette-window-v2.py'
    for row in plan['arms']+plan['components']:row['label']=row['label'].replace('-r1','-r2')
    names = ['config/q2-down-register-palette-source.json','config/q2-down-register-palette-static.json',
        'config/q2-ssm-fixed-bounds-source.json','config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json','config/q2-down-register-palette-host-v2-results.json',
        'config/q2-current-routing-v2-results.json','config/q2-route-opportunities.json',
        'config/q2-fixed-input-route-fixtures.json',
        'tools/analyze-q2-down-register-palette-component.py','tools/analyze-q2-down-register-palette-model.py',
        'tools/freeze-q2-down-register-palette-plan-v2.py','tools/q2-down-register-palette-phase.py']
    plan.update(fixtures=fixtures, manifests={name:sha(ROOT/name) for name in names},
        window_helper_sha256=sha(ROOT/plan['window_helper']),
        previous_release='config/q2-iq2-register-stage-window-release.json',
        previous_release_sha256='57b67078e073f09c2aeb73b2ed2f6c288781131029c8267b840d6bcc77b2f04b',
        host_binding=binding, host_result_sha256=sha(host_path/'results/result.json'),
        host_test_counts=dict(debug=34,asan_ubsan=34), provider_file_count=1028,
        component_expected_output_pairs=123, component_expected_timing_samples=70,
        component_weight_rotation_bytes={str(e):e*2560*3*84*3 for e in (160,512)},
        component_shapes=['Edge n1/16/17/49/65/129/144/145/257 by m1/65/2560,k640,BN48,one expert',
            'Unaffected BN16/64 edges n65/145,m65/2560',
            'Uniform160-expert BN48 affected and512-expert BN64 unchanged timing controls',
            'Uniform512 BN48 replay and captured fixed2048 counts for layers0/3/22,m2560/k640/top10'],
        protocol='One new active BN48 Q2 down register-palette candidate from saved1585. '
            'Component and original exact2048/tg128 model even after safe numerical/timing rejection. '
            'Only new candidate built/run; saved1585/fixedQ2/UD reused; no full curve/Q4/cleanup/tuning.',
        component_time_scope='Complete scaled-half Q2 down and inverse-scale half-output restore; '
            'frozen literal parent versus production selector, identical down maps; three rotated weight '
            'sets beyond32MiB, two warmups/five alternating measured samples on five shapes. Setup excluded.',
        format_scope='Original F32 affine and exact four-value rounded half palette, ordered K16 WMMA, '
            'F32 inverse product, half output and padded transpose; only wave-private weight staging replaced.',
        release_path='config/q2-down-register-palette-v2-window-release.json')
    routes=read(ROOT/'config/q2-fixed-input-route-fixtures.json')
    plan['captured_counts']={str(row['layer']):row['counts'] for row in routes['layers']}
    require(sha(ROOT/plan['previous_release']) == plan['previous_release_sha256'], 'Previous release changed')
    reference = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    require(all(plan[k] == reference[k] for k in ('input_sha256','context_capacity','chunk','prompt_tokens',
        'output_tokens','timed_decode_calls','warmups','repetitions','cooldown_seconds','mtp','run_controls')),
        'Fixed comparator changed')
    hc.write(ROOT/'config/q2-down-register-palette-plan-v2.json',plan)
    print(json.dumps(dict(fixtures=len(fixtures),manifests=len(names),host_tests=68,
                          provider_files=1028,outputs=123,timings=70,gpu_run=False)))


if __name__ == '__main__':
    main()
