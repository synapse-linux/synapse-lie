#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain Q2 down differential verdict and rotated-weight timings separately."""
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def raw_timing_stats(values):
    require(len(values)==5 and all(math.isfinite(v) and v>=0 for v in values), 'Invalid raw timing coverage')
    return dict(samples=values,min=min(values),median=statistics.median(values),max=max(values))


def analyze(plan_path=None):
    variant = 'down-register-palette'
    output = ROOT/('config/q2-'+variant+'-component-results.json')
    plan_path = plan_path or ROOT/'config/q2-down-register-palette-plan.json'
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
    source = read(ROOT/'config/q2-down-register-palette-source.json')['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    log = (path/'results/03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{"event"')]
    replay = [e for e in events if e['event'] == 'down_register_palette_replay']
    timings = [e for e in events if e['event'] == 'down_register_palette_timing']
    complete = [e for e in events if e['event'] == 'down_register_palette_complete']
    require(len(replay) == 123 and len(timings) == 70 and len(complete) == 1 and
            complete[0]['timing_retained'] and not complete[0]['model_inference'],
            'Missing complete outputs or independent timing retention')
    require(all(e['exact'] == (e['changed_values'] == 0 and e['nonfinite_values'] == 0 and
                e['unwritten_values'] == 0 and e['guards_exact']) and
                (e['changed_values'] == 0) == (e['reference_sha256'] == e['candidate_sha256'])
                for e in replay), 'Replay flags differ')
    require(len({(e['case'], e['rotation']) for e in replay}) == 123 and
            all(e['guards_exact'] and e['unwritten_values'] == 0 and e['rotation'] in (0,1,2) for e in replay),
            'Incomplete replay coverage or unsafe guards')
    numerical = all(e['exact'] for e in replay)
    require(complete[0]['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Numerical rejection or command exit lost')
    maps = [e for e in events if e['event'] == 'down_register_palette_map']
    require(len(maps) == 41 and len({e['case'] for e in maps}) == 41,
            'Missing mixed-map geometry coverage')
    actual_maps = {e['case']:e for e in maps}
    expected_cases = {'edge-n'+str(n)+'-m'+str(m) for n in (1,16,17,49,65,129,144,145,257)
                      for m in (1,65,2560)} | {'control-w'+str(w)+'-n'+str(n)+'-m'+str(m)
                      for w in (16,64) for n in (65,145) for m in (65,2560)} | {
                      'uniform-e160-w48','control-e512-w64','uniform-e512-w48','real-layer0','real-layer3','real-layer22'}
    require(set(actual_maps) == expected_cases and
            {(e['case'],e['rotation']) for e in replay} ==
            {(name,r) for name in expected_cases for r in range(3)}, 'Wrong replay cases')
    require(all(e['maps_exact'] and e['tile_rows'] in (16,48,64) and
                e['tile_count'] > 0 and e['padded_rows'] > 0 for e in maps), 'Original down map changed')
    routes = read(ROOT/'config/q2-fixed-input-route-fixtures.json')
    # Geometry is re-derived from immutable recorded expert counts below.
    expected_geometry = {'uniform-e160-w48':(480,20480), 'control-e512-w64':(512,24576),
                         'uniform-e512-w48':(512,24576)}
    for layer in (0,3,22):
        counts = plan['captured_counts'][str(layer)]
        padded = [(c+15)//16*16 for c in counts]
        expected_geometry['real-layer'+str(layer)] = (sum((c+47)//48 for c in padded),sum(padded))
    for name, geometry in expected_geometry.items():
        e=actual_maps[name]
        require((e['tile_count'],e['padded_rows'])==geometry,'Captured/control geometry changed')
    groups=[]
    for shape,capacity,width in (('uniform-e160-w48',160,48),('control-e512-w64',512,64),
                                ('real-layer0',512,48),('real-layer3',512,48),('real-layer22',512,48)):
        pair={}
        for candidate in (False,True):
            rows=[t for t in timings if t['case']==shape and t['candidate']==candidate]
            require([r['rep'] for r in rows]==list(range(7)) and
                [r['warmup'] for r in rows]==[True,True]+[False]*5 and
                all(r['candidate']==(((r['rep']+r['order'])%2)!=0) and r['tokens']==2048 and
                    r['output_rows']==2560 and r['inner']==640 and r['tile_rows']==width and
                    r['expert_capacity']==capacity and r['iterations']==3 and
                    r['weight_bytes']==plan['component_weight_rotation_bytes'][str(capacity)] and
                    r['weight_bytes']>32*1024*1024 and r['us_per_iteration']>=0 for r in rows),
                'Changed component shape/order/rotation')
            pair['candidate' if candidate else 'reference']=raw_timing_stats(
                [r['us_per_iteration'] for r in rows if not r['warmup']])
        groups.append(dict(case=shape,**pair,candidate_time_change_percent=
            (100*(pair['candidate']['median']/pair['reference']['median']-1) if pair['reference']['median']>0 and pair['candidate']['median']>0 else None)))
    timing_valid = all(t['us_per_iteration']>0 for t in timings)
    report = dict(schema='synapse-lie.q2-down-register-palette-component.v1', **capsule,
        plan_sha256=sha(plan_path), source_variant=variant, device_work_safe=True, command_exits=exits, artifact_count=len(result['artifacts']),
        binary_sha256=result['binary_sha256'], numerical_exact=numerical,
        replay=replay, maps=maps, timings=timings, summaries=groups, model_inference=False,
        component_timing_valid=timing_valid,
        timing_rejection_reason=None if timing_valid else 'HIP elapsed times include zero; no component speed inference',
        analysis_correction_manifest_sha256=sha(ROOT/'config/q2-down-register-palette-analysis-correction-v2.json'),
        original_inputs_immutable_at_fixture_completion=True,
        control_scope='Frozen literal retained1585 half-output parent versus production register-palette selector; identical down maps; no qualified model/cohort rerun',
        independent_model_quality_qualification=False, full_model_speedup=False, goal_met=False,
        timing_scope=plan['component_time_scope'])
    return report


def main():
    plan_path = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'config/q2-down-register-palette-plan-v2.json'
    report = analyze(plan_path)
    hc.write(ROOT/'config/q2-down-register-palette-component-results.json', report)
    print(json.dumps({k:report[k] for k in ('command_exits','numerical_exact','summaries')}))


if __name__ == '__main__':
    main()
