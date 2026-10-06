#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one real-route tail16 candidate and the unchanged saved comparisons."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('component', ROOT/'tools/analyze-q2-iq2-tail16-component.py')
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)
hc = component.hc
read, require, sha = hc.read, hc.require, hc.sha


def main():
    old = read(ROOT/'config/q2-current-routing-v2-plan.json')
    fixtures = {name:sha(ROOT/name) for name in old['fixtures']}
    for name in ('experiments/q2_iq2_tail16.c', 'experiments/q2_iq2_tail16.h',
                 'experiments/q2_iq2_tail16_routes.inc', 'tests/q2_iq2_tail16.c', 'tests/q2_iq2_tail16.hip'):
        require(name not in fixtures, 'Fixture already present')
        fixtures[name] = sha(ROOT/name)
    require(len(fixtures) == 116, 'Fixture scope changed')
    host_path = ROOT/'evidence/q2-iq2-tail16-host-r1'
    host, transport = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Host gate incomplete')
    for log in ('03.log','06.log'):
        require('100% tests passed out of 33' in (host_path/'results'/log).read_text(), 'Missing host checks')
    binding = hc.capsule(host_path, fixtures)
    hc.write(ROOT/'config/q2-iq2-tail16-host-results.json', dict(binding,
        command_exits=[0]*6, artifacts_verified=len(host['artifacts']),
        result_sha256=sha(host_path/'results/result.json'), debug=33, asan_ubsan=33,
        gpu_run=False, model_inference=False))
    plan = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    for key in ('schema','window_helper','host','source_variant_manifest'):
        plan[key] = plan[key].replace('iq2-four-wave','iq2-tail16')
    plan['source_variant_manifest'] = 'config/q2-iq2-tail16-source-v2.json'
    for key in ('arms','components'):
        plan[key] = [{k:v.replace('iq2-four-wave','iq2-tail16') for k,v in row.items()} for row in plan[key]]
    names = ['config/q2-iq2-tail16-source-v2.json','config/q2-iq2-tail16-static.json',
        'config/q2-ssm-fixed-bounds-source.json','config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json','config/q2-iq2-tail16-host-results.json',
        'config/q2-current-routing-v2-results.json','config/q2-route-opportunities.json',
        'config/q2-fixed-input-route-fixtures.json',
        'tools/analyze-q2-iq2-tail16-component.py','tools/analyze-q2-iq2-tail16-model.py',
        'tools/freeze-q2-iq2-tail16-plan.py']
    plan.update(fixtures=fixtures, manifests={name:sha(ROOT/name) for name in names},
        window_helper_sha256=sha(ROOT/plan['window_helper']),
        previous_release='config/q2-current-routing-v2-window-release.json',
        previous_release_sha256='5f4d8c1374b0b462c353afa708e27cbc0176083536920047b376b2df52574f3c',
        host_binding=binding, host_result_sha256=sha(host_path/'results/result.json'),
        host_test_counts=dict(debug=33,asan_ubsan=33), provider_file_count=1029,
        component_expected_output_pairs=96, component_expected_timing_samples=56,
        component_weight_rotation_bytes={str(e):e*640*10*66*6 for e in (64,512)},
        component_shapes=['Edge n1/16/17/49/65/129/144/145/257 by m1/65/640, k256, one expert',
            'Full uniform64-expert control, n2048/m640/k2560/top10',
            'Uniform512-expert unchanged-route replay',
            'Captured fixed2048 counts for layers0/3/22, m640/k2560/top10,512 expert capacity'],
        protocol='One new tail16 dispatch from retained1585; numerical source unchanged. '
            'Component plus original exact2048/tg128 model even after safe numerical/timing rejection. '
            'Only new candidate built/run; saved1585/fixedQ2/UD reused; no full curve/Q4/cleanup/tuning.',
        component_time_scope='Complete gate/up and SwiGLU under original128/64 versus128/64/16 maps; '
            'same production arithmetic, three rotated weight sets beyond32MiB; two warmups and five '
            'alternating measurements. Map creation/upload excluded here and charged in full-model run.',
        format_scope='Original IQ2 bytes, scales, half arithmetic and WMMA order. '
            'Only1..16-row tails use existing BN16; width-relative offsets corrected after wide tiles.',
        release_path='config/q2-iq2-tail16-window-release.json')
    require(sha(ROOT/plan['previous_release']) == plan['previous_release_sha256'], 'Previous release changed')
    reference = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    require(all(plan[k] == reference[k] for k in ('input_sha256','context_capacity','chunk','prompt_tokens',
        'output_tokens','timed_decode_calls','warmups','repetitions','cooldown_seconds','mtp','run_controls')),
        'Fixed comparator changed')
    hc.write(ROOT/'config/q2-iq2-tail16-plan.json',plan)
    print(json.dumps(dict(fixtures=len(fixtures),manifests=len(names),host_tests=66,
                          provider_files=1029,outputs=96,timings=56,gpu_run=False)))


if __name__ == '__main__':
    main()
