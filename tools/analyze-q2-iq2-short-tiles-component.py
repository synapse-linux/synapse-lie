#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain IQ2 differential verdict and actual rotated-weight timings separately."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def main():
    variant = 'iq2-short-tiles'
    output = ROOT/('config/q2-'+variant+'-component-results.json')
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT/'config/q2-iq2-short-tiles-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    arm = next(a for a in plan['components'] if a['variant'] == variant)
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
    source = read(ROOT/'config/q2-iq2-short-tiles-source-v2.json')['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    log = (path/'results/03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{"event"')]
    replay = [e for e in events if e['event'] == 'iq2_short_tiles_replay']
    timings = [e for e in events if e['event'] == 'iq2_short_tiles_timing']
    complete = [e for e in events if e['event'] == 'iq2_short_tiles_complete']
    require(len(replay) == 39 and len(timings) == 42 and len(complete) == 1 and
            complete[0]['timing_retained'] and not complete[0]['model_inference'],
            'Missing complete outputs or independent timing retention')
    require(all(e['exact'] == (e['changed_values'] == 0 and e['nonfinite_values'] == 0 and
                e['unwritten_values'] == 0 and e['guards_exact']) and
                (e['changed_values'] == 0) == (e['reference_sha256'] == e['candidate_sha256'])
                for e in replay), 'Replay flags differ')
    require(len({(e['case'], e['rotation']) for e in replay}) == 39 and
            all(e['guards_exact'] and e['unwritten_values'] == 0 and e['rotation'] in (0,1,2) for e in replay),
            'Incomplete replay coverage or unsafe guards')
    numerical = all(e['exact'] for e in replay)
    require(complete[0]['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Numerical rejection or command exit lost')
    maps = [e for e in events if e['event'] == 'iq2_short_tiles_map']
    require(len(maps) == 13 and len({e['case'] for e in maps}) == 13,
            'Missing mixed-map geometry coverage')
    actual_maps = {e['case']:e for e in maps}
    expected_cases = {'edge-n'+str(n) for n in (1,15,17,33,48,49,65,128,129)} | {
        'empty-experts','uniform-e64','uniform-e512','skew-e512'}
    require(set(actual_maps) == expected_cases and
            {(e['case'],e['rotation']) for e in replay} ==
            {(name,r) for name in expected_cases for r in range(3)}, 'Wrong replay cases')
    for name,e in actual_maps.items():
        require(e['descriptor_count_unchanged'] and
                e['reference_wide128'] == e['candidate_wide128'] and
                e['reference_tail64'] == e['candidate_tail64'] + e['candidate_short48'],
                'Map counts changed beyond whole-short replacement')
    for name, geometry in {'uniform-e64':(128,64,0), 'uniform-e512':(0,0,512),
                           'skew-e512':(128,0,504)}.items():
        e=actual_maps[name]
        require((e['candidate_wide128'],e['candidate_tail64'],e['candidate_short48']) == geometry,
                'Large distribution changed')
    groups = []
    for shape, active, skew in (('uniform-e64',64,False), ('uniform-e512',512,False), ('skew-e512',512,True)):
        m, k = 640, 2560
        pair = {}
        for candidate in (False, True):
            rows = [t for t in timings if t['case'] == shape and t['candidate'] == candidate]
            require([r['rep'] for r in rows] == list(range(7)) and
                    [r['warmup'] for r in rows] == [True,True]+[False]*5 and
                    all(r['candidate'] == (((r['rep']+r['order'])%2) != 0) and
                        r['tokens'] == 2048 and r['output_rows'] == m and r['inner'] == k and
                        r['iterations'] == 3 and r['weight_bytes'] == plan['component_weight_rotation_bytes'][str(active)]
                        and r['active_experts'] == active and r['skew'] == skew
                        and r['weight_bytes'] > 32*1024*1024 and r['us_per_iteration'] > 0 for r in rows),
                    'Changed component shape/order/rotation')
            pair['candidate' if candidate else 'reference'] = hc.shared.common.stats(
                [r['us_per_iteration'] for r in rows if not r['warmup']])
        groups.append(dict(case=shape, **pair, candidate_time_change_percent=
            100*(pair['candidate']['median']/pair['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-iq2-short-tiles-component.v1', **capsule,
        plan_sha256=sha(plan_path), source_variant=variant, device_work_safe=True, command_exits=exits, artifact_count=len(result['artifacts']),
        binary_sha256=result['binary_sha256'], numerical_exact=numerical,
        replay=replay, maps=maps, timings=timings, summaries=groups, model_inference=False,
        original_inputs_immutable_at_fixture_completion=True,
        control_scope='Identical parent production kernels with original128/64 maps inside new fixture; no qualified model/cohort rerun',
        independent_model_quality_qualification=False, full_model_speedup=False, goal_met=False,
        timing_scope=plan['component_time_scope'])
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(command_exits=exits, numerical_exact=numerical,
                         timings=len(timings), complete_outputs=len(replay), summaries=groups)))


if __name__ == '__main__':
    main()
