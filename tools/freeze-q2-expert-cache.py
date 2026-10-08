#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze one bounded cache candidate, fresh host gates and saved comparisons."""
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cache_analysis',ROOT/'tools/analyze-q2-expert-cache.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def main():
    old=a.read(ROOT/'config/q2-shared-down-n64-component-plan.json')
    names=[*old['fixtures'],'experiments/q2_expert_cache_policy.h','experiments/q2_expert_cache_iq2_grid.inc',
           'tests/q2_expert_cache.hip','tests/q2_expert_cache_common.inc','tests/q2_expert_cache_inputs.inc',
           'tests/q2_expert_cache_policy.c']
    fixtures={name:a.sha(ROOT/name) for name in names}
    host='q2-expert-cache-host-r1';hpath=ROOT/'evidence'/host
    receipt,_=a.hc.curve.artifact_integrity(hpath)
    a.require(receipt['state']=='CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
        len(receipt['commands'])==6 and all(c['exit_code']==0 for c in receipt['commands']),'Host failed')
    for log in ('03.log','06.log'):
        a.require('100% tests passed out of 28' in (hpath/'results'/log).read_text(),'Wrong host test count')
    binding=a.hc.capsule(hpath,fixtures)
    previous='config/q2-shared-down-n64-component-window-release.json'
    previous_sha='973388223cae971705e3027fd281af760ee38bce247c2468848b89a88055a6e9'
    a.require(a.sha(ROOT/previous)==previous_sha,'Previous release changed')
    manifests=['config/q2-expert-cache-source-v3.json','config/q2-expert-cache-static.json',
        'config/q2-ssm-fixed-bounds-model-results.json','config/q2-fixed-prefill-reference.json',
        'tools/analyze-q2-expert-cache.py','tools/freeze-q2-expert-cache.py',
        'tools/prepare-q2-expert-cache.py','experiments/q2_expert_cache_convert.inc',
        'experiments/q2_expert_cache_upload.inc']
    helper='tools/q2-expert-cache-window.py'
    plan=dict(schema='synapse-lie.q2-expert-cache-plan.v1',fixtures=fixtures,
        manifests={n:a.sha(ROOT/n) for n in manifests},source_manifest=manifests[0],
        window_helper=helper,window_helper_sha256=a.sha(ROOT/helper),previous_release=previous,
        previous_release_sha256=previous_sha,release_path='config/q2-expert-cache-window-release.json',
        host=host,host_test_counts=dict(debug=28,asan_ubsan=28),host_binding=binding,
        host_result_sha256=a.sha(hpath/'results/result.json'),host_reused=False,
        component='q2-expert-cache-component-r1',model='q2-expert-cache-model-r1',
        references=dict(
            fixed_q2=dict(label='q2-counting-regression-mixed-r1',variant='curve-iq2-mixed-q2',
                report='config/q2-fixed-prefill-reference.json',reference_key='mixed'),
            best_parent=dict(label='q2-ssm-fixed-bounds-model-r1',variant='ssm-fixed-bounds',
                report='config/q2-ssm-fixed-bounds-model-results.json'),
            fixed_ud=dict(label='q2-counting-regression-ud-r1',variant='qualified',
                report='config/q2-fixed-prefill-reference.json',reference_key='ud')),
        input_sha256='75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35',
        context_capacity=9216,chunk=2048,prompt_tokens=2048,output_tokens=128,timed_decode_calls=127,
        warmups=1,repetitions=3,cooldown_seconds=15,mtp=False,greedy=True,concurrency=1,
        component_expected_format_events=117,component_expected_replay_pairs=216,
        component_expected_timing_events=56,component_safe_numeric_exit=1,component_unsafe_exit=2,
        safe_numeric_or_timing_failure_still_runs_model=True,expected_cache_layers=[0,8,16,24,32,40],
        expected_cache_bytes=30199062528,expected_resident_bytes=73355075072,
        provider_files=1029,controls_rerun=False,full_curve=False,q4=False,cleanup=False,
        tuning=False,dependencies=False,gpu_run=False,goal_met=False)
    with a.PLAN.open('x') as f:json.dump(plan,f,indent=2);f.write('\n')
    a.bound()
    print(json.dumps(dict(fixtures=len(fixtures),manifests=len(manifests),host_checks='28+28',
        cache_bytes=plan['expected_cache_bytes'],previous_release_sha256=previous_sha)))
if __name__=='__main__':main()
