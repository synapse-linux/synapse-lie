#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one new IQ2 candidate, its host gate and saved performance controls."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('component', ROOT/'tools/analyze-q2-iq2-four-wave-component.py')
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)
hc = component.hc
read, require, sha = hc.read, hc.require, hc.sha


def main():
    prior = read(ROOT/'config/q2-ssm-channel-bounds-plan.json')
    fixtures = {name: sha(ROOT/name) for name in prior['fixtures']}
    for name in ('tests/q2_iq2_four_wave.hip','experiments/q2-iq2-four-wave-control.inc'):
        require(name not in fixtures, 'Fixture already present')
        fixtures[name] = sha(ROOT/name)
    require(len(fixtures) == 107, 'Fixture scope changed')
    host_label = 'q2-iq2-four-wave-host-r1'
    host_path = ROOT/'evidence'/host_label
    host, transport = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']) and
            transport['exit_code'] == 0, 'Host gate incomplete')
    for log in ('03.log','06.log'):
        require('100% tests passed out of 31' in (host_path/'results'/log).read_text(), 'Missing host checks')
    host_binding = hc.capsule(host_path, fixtures)
    hc.write(ROOT/'config/q2-iq2-four-wave-host-results.json', dict(host_binding,
        command_exits=[0]*6, artifacts_verified=len(host['artifacts']),
        result_sha256=sha(host_path/'results/result.json'), debug=31, asan_ubsan=31,
        gpu_run=False, model_inference=False))
    previous = 'config/q2-ssm-channel-bounds-window-release.json'
    previous_sha = '8ffd9efb36cf38885a4e9a49a1daa4dafadfd15e8892e591e66c92675ed54f11'
    require(sha(ROOT/previous) == previous_sha and not read(ROOT/previous)['gpu_reserved'], 'Prior release changed')
    plan = read(ROOT/'config/q2-iq2-wide-pair-plan.json')
    for key in ('schema','window_helper','host','source_variant_manifest'):
        plan[key] = plan[key].replace('iq2-wide-pair','iq2-four-wave')
    for key in ('arms','components'):
        plan[key] = [{k:v.replace('iq2-wide-pair','iq2-four-wave') for k,v in row.items()} for row in plan[key]]
    names = ['config/q2-iq2-four-wave-source.json','config/q2-iq2-four-wave-static.json',
        'config/q2-ssm-fixed-bounds-source.json','config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json','config/q2-iq2-four-wave-host-results.json',
        'tools/analyze-q2-iq2-four-wave-component.py','tools/analyze-q2-iq2-four-wave-model.py',
        'tools/freeze-q2-iq2-four-wave-plan.py']
    plan.update(fixtures=fixtures, manifests={name:sha(ROOT/name) for name in names},
        window_helper_sha256=sha(ROOT/plan['window_helper']),
        previous_release=previous, previous_release_sha256=previous_sha,
        host_binding=host_binding, host_result_sha256=sha(host_path/'results/result.json'),
        host_test_counts=dict(debug=31, asan_ubsan=31), provider_file_count=1027,
        component_expected_output_pairs=96, component_expected_timing_samples=42,
        safety_or_runtime_failure_exit=2, safe_numeric_failure_exit=1,
        parent_measured_prefill=1585.308983, parent_measured_decode=25.16079073,
        construction_parent='ssm-fixed-bounds',
        protocol='One IQ2 four-wave BN64 candidate from retained1585; same logical output tile and LDS. '
            'Component and original exact2048/tg128 model even after safe numerical/timing rejection. '
            'Only the new candidate is built and run. Saved fixedQ2/UD and retained1585 reused. '
            'No full curve,Q4,cleanup,tuning,dependencies or deployment.',
        component_time_scope='Complete IQ2 gate/up and F32 SwiGLU with original mixed128/64 descriptors, '
            'same64 logical rows per block: retained eight waves versus four waves only for nonpackedBN64. '
            'Three rotated weight sets beyond32MiB, two warmups/five measured alternating pairs, '
            'setup outside component timing. Model charges all inference work.',
        component_shapes=plan['component_shapes']+['Unchanged BN16/48/128 and packedBN64 controls, three rotations'],
        format_scope='Original compressed IQ2 bytes/scales/half arithmetic and ordered WMMA. '
            'New gate/up ownership in four waves;161 other instruction/operand/resource bodies exact.',
        release_path='config/q2-iq2-four-wave-window-release.json',
        handover=dict(core_thread='01a0f71e-b42a-7f80-b04b-780e3c4bd45c',core_nonuse_persistent=True),
        gpu_run=False, model_inference=False)
    require(plan['input_sha256'] == prior['input_sha256'] and
            all(plan[k] == prior[k] for k in ('context_capacity','chunk','prompt_tokens','output_tokens',
                'timed_decode_calls','warmups','repetitions','cooldown_seconds','mtp','run_controls')),
            'Historical measurement protocol changed')
    hc.write(ROOT/'config/q2-iq2-four-wave-plan.json', plan)
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(names), host_tests=62,
                          provider_files=1027, gpu_run=False)))


if __name__ == '__main__':
    main()
