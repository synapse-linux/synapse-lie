#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify all scaled packing outputs, independent conversions and full cycles."""
import importlib.util
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def main():
    output = ROOT/'config/q2-scaled-wave-pack-component-results.json'
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT/'config/q2-scaled-wave-pack-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    arm = plan['component']
    path = ROOT/'evidence'/arm['label']
    receipt, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in receipt['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and receipt['finished_at'] and
        receipt['mode'] == transport['mode'] == arm['mode'] and
        transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
        not receipt['model_access'] and receipt['binary_sha256'] == receipt['binary_sha256_after'],
        'Incomplete or changed component')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
        not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Ownership changed')
    source = read(ROOT/plan['source_variant_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    rows = [json.loads(s) for s in (path/'results/03.log').read_text().splitlines()
            if s.startswith('{"event"')]
    packing = [r for r in rows if r['event'] == 'scaled_wave_pack_check']
    down = [r for r in rows if r['event'] == 'scaled_wave_down_check']
    timings = [r for r in rows if r['event'] == 'scaled_wave_pack_timing']
    complete = [r for r in rows if r['event'] == 'scaled_wave_pack_complete']
    require((len(packing), len(down), len(timings), len(complete)) == (25, 2, 28, 1),
            'Missing complete component coverage')
    require({r['case'] for r in packing} == set(plan['component_cases']) and
            {r['case'] for r in down} == {'before-timing', 'after-timing'}, 'Case scope changed')
    replay = []
    oracle_fields = ['parent_oracle_half_errors', 'candidate_oracle_half_errors',
                     'parent_oracle_scale_errors', 'candidate_oracle_scale_errors']
    expected_files = set()
    for row in packing:
        case = plan['component_cases'][row['case']]
        require(all(row[k] == case[k] for k in ('rows', 'input_prefix', 'output_prefix')),
                'Case geometry changed')
        require(all(type(row[k]) is int and row[k] >= 0 for k in oracle_fields), 'Invalid oracle errors')
        for field in ('half', 'scale'):
            size = case['rows'] * (640*2 if field == 'half' else 4)
            size += case['output_prefix'] + 64 if field == 'half' else 128
            hashes = {}
            for name in ('parent', 'candidate'):
                file = path/'results'/(row['case']+'-'+name+'-'+field+'.bin')
                expected_files.add(file.name)
                require(file.stat().st_size == size and sha(file) == row[name+'_'+field+'_sha256'],
                        'Complete packing array changed')
                hashes[name+'_sha256'] = sha(file)
            exact = hashes['parent_sha256'] == hashes['candidate_sha256']
            require(row[field+'_exact'] == exact, 'Differential verdict changed')
            replay.append(dict(case=row['case'], field=field, bytes=size, exact=exact, **hashes))
    for row in down:
        size = 20480*2560*2+128
        hashes = {}
        for name in ('parent', 'candidate'):
            file = path/'results'/(row['case']+'-'+name+'-down.bin')
            expected_files.add(file.name)
            require(file.stat().st_size == size and sha(file) == row[name+'_sha256'], 'Down array changed')
            hashes[name+'_sha256'] = sha(file)
        exact = hashes['parent_sha256'] == hashes['candidate_sha256']
        require(row['exact'] == exact, 'Down verdict changed')
        replay.append(dict(case=row['case'], field='down', bytes=size, exact=exact, **hashes))
    require(len(expected_files) == 104 and {p.name for p in (path/'results').glob('*.bin')} == expected_files,
            'Complete output inventory changed')
    exact = all(r['exact'] for r in replay)
    oracle_pass = all(not r[k] for r in packing for k in oracle_fields)
    numeric_pass = exact and oracle_pass
    require(complete[0]['numerical_pass'] == numeric_pass and complete[0]['timings_retained'] and
            not complete[0]['model_inference'] and exits[-1] == (0 if numeric_pass else 1),
            'Runtime/numerical failure lost')
    summaries = []
    for scope in ('pack', 'pack_down'):
        arms = {}
        for candidate in (False, True):
            group = [r for r in timings if r['scope'] == scope and r['candidate'] == candidate]
            require([r['rep'] for r in group] == list(range(7)) and
                    all(r['candidate'] == bool((r['rep']+r['order']) % 2) and
                        r['warmup'] == (r['rep'] < 2) and r['iterations'] == (8 if scope == 'pack' else 3) and
                        r['input_bytes'] == 20480*640*4 > 32*1024**2 and
                        r['weight_bytes'] == (0 if scope == 'pack' else plan['component_weight_bytes']) and
                        math.isfinite(r['us_per_iteration']) and r['us_per_iteration'] > 0 for r in group),
                    'Timing geometry/samples/order changed')
            samples = [r['us_per_iteration'] for r in group if not r['warmup']]
            arms['candidate' if candidate else 'reference'] = dict(samples=samples,
                median=statistics.median(samples), min=min(samples), max=max(samples))
        summaries.append(dict(scope=scope, **arms,
            candidate_time_change_percent=100*(arms['candidate']['median']/arms['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-scaled-wave-pack-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(receipt['artifacts']),
        complete_output_array_count=104, binary_sha256=receipt['binary_sha256'],
        numerical_exact=exact, oracle_pass=oracle_pass, replay=replay, packing=packing,
        down=down, timings=timings, summaries=summaries, completion=complete[0],
        safe_model_performance_admissible=True, model_inference=False,
        independent_model_quality=False, goal_met=False,
        limits='Full scalar oracle checks only the changed activation packing operator; unchanged down is differentially checked. No independent task-quality or full-curve acceptance.')
    with output.open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print(json.dumps(dict(exits=exits, complete_pairs=len(replay), oracle_cases=len(packing),
                         numerical_exact=exact, oracle_pass=oracle_pass, summaries=summaries)))


if __name__ == '__main__':
    main()
