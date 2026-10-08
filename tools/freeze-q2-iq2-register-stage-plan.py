#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one real-route register-stage candidate and the unchanged saved comparisons."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('component', ROOT/'tools/analyze-q2-iq2-register-stage-component.py')
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)
hc = component.hc
read, require, sha = hc.read, hc.require, hc.sha


def main():
    old = read(ROOT/'config/q2-iq2-tail16-plan.json')
    fixtures = {name:sha(ROOT/name) for name in old['fixtures']}
    for name in ('tests/q2_iq2_register_stage.hip', 'experiments/q2-iq2-register-stage-control.inc'):
        require(name not in fixtures, 'Fixture already present')
        fixtures[name] = sha(ROOT/name)
    require(len(fixtures) == 118, 'Fixture scope changed')
    host_path = ROOT/'evidence/q2-iq2-register-stage-host-r1'
    host, transport = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Host gate incomplete')
    for log in ('03.log','06.log'):
        require('100% tests passed out of 33' in (host_path/'results'/log).read_text(), 'Missing host checks')
    binding = hc.capsule(host_path, fixtures)
    hc.write(ROOT/'config/q2-iq2-register-stage-host-results.json', dict(binding,
        command_exits=[0]*6, artifacts_verified=len(host['artifacts']),
        result_sha256=sha(host_path/'results/result.json'), debug=33, asan_ubsan=33,
        gpu_run=False, model_inference=False))
    plan = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    for key in ('schema','window_helper','host','source_variant_manifest'):
        plan[key] = plan[key].replace('iq2-four-wave','iq2-register-stage')
    plan['source_variant_manifest'] = 'config/q2-iq2-register-stage-source-v2.json'
    for key in ('arms','components'):
        plan[key] = [{k:v.replace('iq2-four-wave','iq2-register-stage') for k,v in row.items()} for row in plan[key]]
    names = ['config/q2-iq2-register-stage-source-v2.json','config/q2-iq2-register-stage-static-v2.json',
        'config/q2-ssm-fixed-bounds-source.json','config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json','config/q2-iq2-register-stage-host-results.json',
        'config/q2-current-routing-v2-results.json','config/q2-route-opportunities.json',
        'config/q2-fixed-input-route-fixtures.json',
        'tools/analyze-q2-iq2-register-stage-component.py','tools/analyze-q2-iq2-register-stage-model.py',
        'tools/freeze-q2-iq2-register-stage-plan.py']
    plan.update(fixtures=fixtures, manifests={name:sha(ROOT/name) for name in names},
        window_helper_sha256=sha(ROOT/plan['window_helper']),
        previous_release='config/q2-iq2-tail16-window-release.json',
        previous_release_sha256='b7da267d9739b263a8ed46a5592246d143e3ea1ab127c99bcbfaae1c1e23a46f',
        host_binding=binding, host_result_sha256=sha(host_path/'results/result.json'),
        host_test_counts=dict(debug=33,asan_ubsan=33), provider_file_count=1028,
        component_expected_output_pairs=96, component_expected_timing_samples=70,
        component_weight_rotation_bytes={str(e):e*640*10*66*6 for e in (160,512)},
        component_shapes=['Edge n1/16/17/49/65/129/144/145/257 by m1/65/640, k256, one expert',
            'Full128 uniform160-expert affected control, n2048/m640/k2560/top10',
            'Uniform512-expert unchanged BN64 route timing control',
            'Captured fixed2048 counts for layers0/3/22, m640/k2560/top10,512 expert capacity'],
        protocol='One new IQ2 register-stage candidate from retained1585. '
            'Component plus original exact2048/tg128 model even after safe numerical/timing rejection. '
            'Only new candidate built/run; saved1585/fixedQ2/UD reused; no full curve/Q4/cleanup/tuning.',
        component_time_scope='Complete gate/up and SwiGLU, frozen literal parent versus production selector; '
            'identical128/64 maps, three rotated weight sets beyond32MiB, two warmups and five '
            'alternating measurements on five shapes. Input/map upload excluded from operator timers.',
        format_scope='Original IQ2 table/sign/scale and half-FMA/K16 WMMA order; '
            'only wave-private BN128 weight code/scale staging replaced by registers.',
        release_path='config/q2-iq2-register-stage-window-release.json')
    require(sha(ROOT/plan['previous_release']) == plan['previous_release_sha256'], 'Previous release changed')
    reference = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    require(all(plan[k] == reference[k] for k in ('input_sha256','context_capacity','chunk','prompt_tokens',
        'output_tokens','timed_decode_calls','warmups','repetitions','cooldown_seconds','mtp','run_controls')),
        'Fixed comparator changed')
    hc.write(ROOT/'config/q2-iq2-register-stage-plan.json',plan)
    print(json.dumps(dict(fixtures=len(fixtures),manifests=len(names),host_tests=66,
                          provider_files=1028,outputs=96,timings=70,gpu_run=False)))


if __name__ == '__main__':
    main()
