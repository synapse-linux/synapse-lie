#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the host-qualified capture and the retained executable; no GPU build."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
read, sha, require = hc.read, hc.sha, hc.require


def main():
    previous = read(ROOT/'config/q2-iq2-four-wave-plan.json')
    fixtures = {name:sha(ROOT/name) for name in previous['fixtures']}
    for name in ('tools/q2_capture_routes.py', 'tests/q2_capture_routes.c', 'tests/q2_capture_routes_test.py'):
        fixtures[name] = sha(ROOT/name)
    host_path = ROOT/'evidence/q2-current-routing-host-r1'
    host, transport = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            transport['exit_code'] == 0 and len(host['commands']) == 6 and
            all(c['exit_code'] == 0 for c in host['commands']), 'Host gate failed')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 32' in (host_path/'results'/name).read_text(), 'Host tests incomplete')
    binding = hc.capsule(host_path, fixtures)
    hc.write(ROOT/'config/q2-current-routing-host-results.json', dict(binding,
        result_sha256=sha(host_path/'results/result.json'), artifacts=len(host['artifacts']),
        debug=32, asan_ubsan=32, gdb_cases_per_build=7, gpu_run=False,
        ptrace_fixture_leak_detection=False, other_fixture_leak_detection=True))
    names = ['config/q2-current-routing-binary.json', 'config/q2-current-routing-host-results.json',
        'config/q2-ssm-fixed-bounds-source.json', 'config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-current-best-profile-results.json', 'config/q2-fixed-prefill-reference.json',
        'tools/analyze-q2-current-routing.py', 'tools/freeze-q2-current-routing-plan.py']
    binary = read(ROOT/names[0])['controls']['q2-ssm-fixed-bounds-model-r1']['binary_sha256']
    plan = dict(schema='synapse-lie.q2-current-routing-plan.v1', fixtures=fixtures,
        manifests={name:sha(ROOT/name) for name in names}, host='q2-current-routing-host-r1',
        host_result_sha256=sha(host_path/'results/result.json'), host_binding=binding,
        source_variant='ssm-fixed-bounds', source_variant_manifest='config/q2-ssm-fixed-bounds-source.json',
        window_helper='tools/q2-current-routing-window.py',
        window_helper_sha256=sha(ROOT/'tools/q2-current-routing-window.py'),
        previous_release='config/q2-iq2-four-wave-window-release.json',
        previous_release_sha256='cf9f3b99ded9b5012145a111dad5722347cead379fc7f675c89b62276b05835c',
        arms=[dict(label='q2-current-routing-r1',mode='q2-current-routing',variant='ssm-fixed-bounds')],
        binary_sha256=binary, input_sha256=previous['input_sha256'], context_capacity=9216,
        chunk=2048, prompt_tokens=2048, diagnostic_output_tokens=16, diagnostic_decode_calls=15,
        captures=96, layers=48, experts=512, experts_used=10,
        headline_eligible=False, build_commands=0, run_controls=False,
        saved_performance_prefill=1585.308983, saved_performance_decode=25.16079073,
        collection_scope='Two original builtin profile forwards; GDB host function-entry breakpoint reads '
            'existing synchronized counts. Model/kernel/source unchanged. Discard every diagnostic timing '
            'as performance evidence. Compare full prefill logits and first16 tokens with saved1585.',
        full_curve=False, gpu_run=False, goal_met=False)
    require(sha(ROOT/plan['previous_release']) == plan['previous_release_sha256'], 'Previous release changed')
    hc.write(ROOT/'config/q2-current-routing-plan.json', plan)
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(names), host_tests=64,
                          captures=96, gpu_builds=0, headline_eligible=False)))


if __name__ == '__main__':
    main()
