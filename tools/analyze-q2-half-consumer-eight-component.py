#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain Q2 down differential verdict and actual rotated-weight timings separately."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def main():
    output = ROOT/'config/q2-half-consumer-eight-component-results.json'
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT/'config/q2-half-consumer-eight-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    arm = plan['components'][0]
    path = ROOT/'evidence'/arm['label']
    result, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0,0,0], [0,0,1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete or changed component')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Component ownership changed')
    source = read(ROOT/'config/q2-half-consumer-eight-source.json')['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    log = (path/'results/03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{"event"')]
    replay = [e for e in events if e['event'] == 'half_consumer_eight_replay']
    timings = [e for e in events if e['event'] == 'half_consumer_eight_timing']
    immutable = [e for e in events if e['event'] == 'half_consumer_eight_immutable']
    complete = [e for e in events if e['event'] == 'half_consumer_eight_complete']
    require(len(replay) == 105 and len(timings) == 42 and len(immutable) == 35 and
            len(complete) == 1 and complete[0]['timing_retained'] and
            not complete[0]['model_inference'], 'Incomplete consumer/timing evidence')
    cases = {(n,u,p) for n in (16,17,33,129) for u in (1,2,10,32) for p in (64,68)} | {
        (2048,u,64) for u in (2,10,32)}
    names = {'n'+str(n)+'-u'+str(u)+'-p'+str(p) for n,u,p in cases}
    require({(e['n'],e['used'],e['prefix'],e['rotation']) for e in replay} ==
            {(n,u,p,r) for n,u,p in cases for r in range(3)}, 'Consumer coverage changed')
    require({e['case'] for e in immutable} == names and all(e['inputs_exact'] for e in immutable),
            'Input immutability incomplete')
    require(all(e['guards_exact'] and e['all_written'] and len(e['output_sha256']) == 3 and
                e['gate_stride'] == (1 if e['prefix'] == 64 else 5) and
                e['inject_parts'] == (1 if e['n'] == 16 else 3 if e['n'] == 17 else 10)
                for e in replay), 'Consumer safety or input shape changed')
    for e in replay:
        require(e['parent_exact'] == all(h['parent'] == h['candidate'] for h in e['output_sha256']) and
                e['expanded_half_exact'] == all(h['expanded'] == h['candidate'] for h in e['output_sha256']),
                'Numerical verdict/hash disagreement')
    numerical = all(e['parent_exact'] and e['expanded_half_exact'] and e['nonfinite_values'] == 0 for e in replay)
    require(complete[0]['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Numerical failure or command exit lost')
    groups = []
    for used in (2,10,32):
        case = 'n2048-u'+str(used)+'-p64'
        pair = {}
        for candidate in (False, True):
            rows = [t for t in timings if t['case'] == case and t['candidate'] == candidate]
            require([r['rep'] for r in rows] == list(range(7)) and
                    [r['warmup'] for r in rows] == [True,True]+[False]*5 and
                    all(r['candidate'] == bool((r['rep']+r['order'])%2) and r['iterations'] == 3 and
                        r['input_rotation_bytes'] == plan['component_input_rotation_bytes'][str(used)] and
                        r['input_rotation_bytes'] > 32*1024*1024 and r['us_per_iteration'] > 0 for r in rows),
                    'Timing/rotation scope changed')
            pair['candidate' if candidate else 'reference'] = hc.shared.common.stats(
                [r['us_per_iteration'] for r in rows if not r['warmup']])
        groups.append(dict(case=case,scope='complete-consumer',used=used,**pair,
            candidate_time_change_percent=100*(pair['candidate']['median']/pair['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-half-consumer-eight-component.v1', **capsule,
        plan_sha256=sha(plan_path),source_variant=arm['variant'],device_work_safe=True,
        command_exits=exits,artifact_count=len(result['artifacts']),binary_sha256=result['binary_sha256'],
        numerical_pass=numerical,parent_exact=all(e['parent_exact'] for e in replay),
        replay=replay,immutable=immutable,timings=timings,summaries=groups,model_inference=False,
        original_inputs_immutable_at_fixture_completion=True,
        control_scope='Literal1570 half consumer; additional unchanged F32 consumer on exactly expanded half inputs. No independent model/task oracle.',
        independent_model_quality_qualification=False,full_model_speedup=False,goal_met=False,
        timing_scope=plan['component_time_scope'])
    with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(command_exits=exits,numerical_pass=numerical,complete_outputs=len(replay),
                         timings=len(timings),summaries=groups)))


if __name__ == '__main__':
    main()
