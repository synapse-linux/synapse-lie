#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify new shared-pair complete outputs, sampled oracle and cycle times."""
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
    output = ROOT/'config/q2-shared-q8-pair-component-results.json'
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT/'config/q2-shared-q8-pair-plan.json'
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
            if s.startswith('{"type"')]
    replay = [r for r in rows if r['type'] == 'comparison']
    oracles = [r for r in rows if r['type'] == 'oracle']
    timings = [r for r in rows if r['type'] == 'timing']
    complete = [r for r in rows if r['type'] == 'complete']
    require((len(replay), len(oracles), len(timings), len(complete)) == (43, 24, 28, 1),
            'Missing complete component coverage')
    expected = {}
    for name, case in plan['component_cases'].items():
        for field in case['fields']:
            expected[name+'-'+field] = (case['n'] * (case['m'] * 2 if field == 'half' else 2560 * 4), field == 'half')
    expected.update({'timing-final-half': (2048*640*2, True), 'timing-final-down': (2048*2560*4, False)})
    require(len({r['id'] for r in replay}) == 43 and {r['id'] for r in replay} == set(expected),
            'Repeated or missing output')
    collection = read(path/'output-collection.json')
    require(collection['plan_sha256'] == sha(plan_path) and
            collection['receipt_sha256'] == sha(path/'results/result.json') and
            collection['comparison_log_sha256'] == sha(path/'results/03.log') and
            collection['archive_sha256'] == sha(path/'output-arrays.tar.gz') and
            collection['output_arrays'] == 86 and collection['exit_code'] == 0,
            'Complete arrays not collected')
    for row in replay:
        require((row['bytes'], row['half']) == expected[row['id']], 'Output shape changed')
        for arm_name in ('parent', 'candidate'):
            name = row['id']+'-'+arm_name+'.bin'
            file = path/'output-arrays'/name
            require(file.stat().st_size == row['bytes'] and sha(file) == row[arm_name+'_sha256'], 'Output array changed')
        require(row['exact'] == (row['parent_sha256'] == row['candidate_sha256']), 'Differential verdict changed')
    require(len({r['id'] for r in oracles}) == 24 and
            {r['id'] for r in oracles} == set(plan['component_cases']), 'Oracle shape coverage changed')
    for row in oracles:
        require(row['samples'] == 64 and row['limit'] == 0.002 and
                all(math.isfinite(row[k]) for k in ('relative_rms', 'scaled_error')) and
                row['pass'] == (row['relative_rms'] <= 0.002 and row['scaled_error'] <= 0.002),
                'Independent operator verdict changed')
    final = complete[0]
    numerical_exact = all(r['exact'] for r in replay)
    oracle_pass = all(r['pass'] for r in oracles)
    numeric_pass = numerical_exact and oracle_pass
    require(final['cases'] == 24 and final['guards_pass'] and final['required_outputs_finite_written'] and
            final['numeric_pass'] == numeric_pass and exits[-1] == (0 if numeric_pass else 1),
            'Runtime/numerical failure lost')
    require(final['rotated_pair_weight_bytes'] == plan['component_weight_rotation_bytes']['pair'] > 32*1024**2 and
            final['rotated_weight_bytes'] == plan['component_weight_rotation_bytes']['cycle'] > 32*1024**2,
            'Timing weights fit cache or changed')
    summaries = []
    for cycle in (False, True):
        arms = {}
        for candidate in (False, True):
            group = [r for r in timings if r['cycle'] == cycle and r['candidate'] == candidate]
            require([r['sample'] for r in group] == list(range(-2, 5)) and
                    all(r['rotations'] == 11 and r['candidate'] == bool((r['sample']+2+r['order']) % 2) and
                        math.isfinite(r['microseconds']) and r['microseconds'] > 0 for r in group),
                    'Timing samples/order changed')
            samples = [r['microseconds'] for r in group if r['sample'] >= 0]
            arms['candidate' if candidate else 'reference'] = dict(samples=samples, median=statistics.median(samples), min=min(samples), max=max(samples))
        summaries.append(dict(scope='complete_shared_cycle' if cycle else 'gate_up_swiglu', **arms,
            candidate_time_change_percent=100*(arms['candidate']['median']/arms['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-shared-q8-pair-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(receipt['artifacts']),
        complete_output_array_count=86, output_collection_sha256=sha(path/'output-collection.json'),
        binary_sha256=receipt['binary_sha256'], numerical_exact=numerical_exact,
        oracle_pass=oracle_pass, replay=replay, oracles=oracles, timings=timings,
        summaries=summaries, completion=final, safe_model_performance_admissible=True,
        model_inference=False, independent_model_quality=False, goal_met=False,
        limits='FP64 sampled projection/SwiGLU uses independently summed captured quantized inputs; it does not qualify the quantizer, original model tasks or inherited F16 lineage quality.')
    with output.open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print(json.dumps(dict(exits=exits, complete_pairs=len(replay), oracles=len(oracles),
        numerical_exact=numerical_exact, oracle_pass=oracle_pass, summaries=summaries)))


if __name__ == '__main__':
    main()
