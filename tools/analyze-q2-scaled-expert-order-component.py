#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify complete retained arrays, including the physical row permutation."""
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


def permutation(case):
    buckets = [[] for _ in range(case['experts'])]
    for slot in range(case['rows']):
        buckets[(slot*73+3) % case['experts']].append(slot)
    state, result = 901, []
    for bucket in buckets:
        for j in range(len(bucket), 1, -1):
            state = (state*1664525+1013904223) & 0xffffffff
            k = state % j
            bucket[j-1], bucket[k] = bucket[k], bucket[j-1]
        result.extend(bucket)
        result.extend([-1]*(-len(bucket) % 16))
    result.extend([-1]*(case['capacity']-len(result)))
    require(len(result) == case['capacity'] and sorted(s for s in result if s >= 0) == list(range(case['rows'])),
            'Invalid reconstructed routing')
    return result


def main():
    output = ROOT/'config/q2-scaled-expert-order-component-results.json'
    require(not output.exists(), 'Refusing to overwrite evidence')
    plan_path = ROOT/'config/q2-scaled-expert-order-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen bytes changed: '+name)
    arm = plan['component']; path = ROOT/'evidence'/arm['label']
    receipt, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in receipt['commands']]
    require(exits in ([0,0,0], [0,0,1]) and receipt.get('finished_at') and
            receipt['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not receipt['model_access'] and receipt['binary_sha256'] == receipt['binary_sha256_after'],
            'Incomplete component or unsafe failure')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
            not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Ownership changed')
    source = read(ROOT/plan['source_variant_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    rows = [json.loads(s) for s in (path/'results/03.log').read_text().splitlines() if s.startswith('{"event"')]
    checks = [r for r in rows if r['event'] == 'expert_order_check']
    timings = [r for r in rows if r['event'] == 'expert_order_timing']
    complete = [r for r in rows if r['event'] == 'complete']
    require((len(checks),len(timings),len(complete)) == (36,28,1) and
            {r['case'] for r in checks} == set(plan['component_cases']), 'Incomplete coverage')
    expected, replay, zero_diagnosis = set(), [], []
    fields = ('parent_half_oracle_errors','candidate_half_oracle_errors',
              'parent_scale_oracle_errors','candidate_scale_oracle_errors')
    for row in checks:
        case = plan['component_cases'][row['case']]
        require(all(row[k] == v for k,v in case.items()), 'Case geometry changed')
        require(all(type(row[k]) is int and row[k] >= 0 for k in fields), 'Invalid oracle errors')
        order = permutation(case)
        sorted_rows = {slot:i for i,slot in enumerate(order) if slot >= 0}
        for field in ('half','scale','down'):
            if field == 'down' and not case['down_checked']: continue
            data, hashes = {}, {}
            for name in ('parent','candidate'):
                n = case['capacity'] if field == 'half' and name == 'candidate' else case['rows']
                size = n*(1280 if field == 'half' else 4 if field == 'scale' else case['width']*2)+128
                file = path/'results'/(row['case']+'-'+name+'-'+field+'.bin')
                expected.add(file.name)
                require(file.stat().st_size == size, 'Truncated output')
                raw = file.read_bytes()
                require(raw[:64] == raw[-64:] == bytes([0xa5])*64, 'Guard differs')
                data[name] = memoryview(raw)[64:-64]
                hashes[name+'_sha256'] = sha(file)
            if field == 'half':
                mismatch, padding = 0, 0
                for physical,slot in enumerate(order):
                    observed = data['candidate'][physical*1280:(physical+1)*1280]
                    if slot < 0: padding += observed != bytes(1280)
                    else: mismatch += observed != data['parent'][slot*1280:(slot+1)*1280]
                require(row['layout_errors'] == mismatch and row['padding_errors'] == padding,
                        'Layout verdict differs from full arrays')
                exact = mismatch == padding == 0
                if row['case'] == 'extreme':
                    # Independently account for strict signed-zero failures from saved bytes.
                    for name in ('parent','candidate'):
                        count = 0
                        for slot in range(0,case['rows'],4):
                            physical = slot if name == 'parent' else sorted_rows[slot]
                            for c in range(1,640,2):
                                bits = bytes(data[name][physical*1280+c*2:physical*1280+c*2+2])
                                require(bits in (b'\x00\x00',b'\x00\x80'), 'Unexpected zero-row value')
                                count += bits == b'\x00\x00'
                        zero_diagnosis.append(dict(arm=name, negative_zero_to_positive_zero=count,
                            total_reported_half_errors=row[name+'_half_oracle_errors'],
                            accounts_for_all_reported_errors=count == row[name+'_half_oracle_errors']))
            else:
                exact = data['parent'] == data['candidate']
                require(row[field+'_exact'] == exact, 'Differential verdict differs')
            replay.append(dict(case=row['case'], field=field, exact=exact, **hashes))
    require(len(expected) == 214 and expected == {p.name for p in (path/'results').glob('*.bin')},
            'Output inventory differs')
    exact = all(r['exact'] for r in replay)
    oracle_pass = all(not r[k] for r in checks for k in fields)
    require(complete[0]['pass'] == (exact and oracle_pass) and exits[-1] == (0 if exact and oracle_pass else 1),
            'Original failure status lost')
    summaries = []
    for scope in ('pack','pack_down'):
        arms = {}
        for candidate in (False,True):
            group = [r for r in timings if r['scope'] == scope and r['candidate'] == candidate]
            require([r['rep'] for r in group] == list(range(7)) and all(
                r['candidate'] == bool((r['rep']+r['order']) % 2) and r['warmup'] == (r['rep'] < 2) and
                r['iterations'] == (8 if scope == 'pack' else 3) and r['input_bytes'] == 20480*640*4 and
                r['weight_bytes'] == (0 if scope == 'pack' else 330301440) and
                math.isfinite(r['us_per_iteration']) and r['us_per_iteration'] > 0 for r in group),
                'Timing scope changed')
            samples = [r['us_per_iteration'] for r in group if not r['warmup']]
            arms['candidate' if candidate else 'reference'] = dict(samples=samples,
                median=statistics.median(samples), min=min(samples), max=max(samples))
        summaries.append(dict(scope=scope, **arms,
            candidate_time_change_percent=100*(arms['candidate']['median']/arms['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-scaled-expert-order-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(receipt['artifacts']),
        complete_output_array_count=214, binary_sha256=receipt['binary_sha256'],
        numerical_exact=exact, oracle_pass=oracle_pass, replay=replay, checks=checks,
        signed_zero_diagnosis=zero_diagnosis, timings=timings, summaries=summaries,
        safe_model_performance_admissible=True, model_inference=False,
        independent_model_quality=False, goal_met=False,
        limits='Whole packing and down outputs checked; layout reconstructed separately from device indexing. Independent scalar oracle covers packing only. No task-quality or context-curve acceptance.')
    with output.open('x') as out:
        json.dump(report,out,indent=2);out.write('\n')
    print(json.dumps(dict(exits=exits,complete_pairs=len(replay),numerical_exact=exact,
        oracle_pass=oracle_pass,signed_zero_diagnosis=zero_diagnosis,summaries=summaries)))


if __name__ == '__main__':
    main()
