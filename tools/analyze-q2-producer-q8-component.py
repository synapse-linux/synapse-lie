#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit full Q8-chain arrays and timings without suppressing numerical failures."""
import importlib.util
import json
import math
from pathlib import Path
import statistics
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/analyze-q2-compact-expert-chain-component.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
hc = prior.hc
require, sha, read = hc.require, hc.sha, hc.read


def main():
    output = ROOT/'config/q2-producer-q8-component-results.json'
    require(not output.exists(), 'Refusing to overwrite evidence')
    plan_path = ROOT/'config/q2-producer-q8-plan-v2.json'
    plan = read(plan_path)
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen bytes changed: '+name)
    arm = plan['component']
    path = ROOT/'evidence'/arm['label']
    receipt, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in receipt['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and receipt.get('finished_at') and
        receipt['mode'] == transport['mode'] == arm['mode'] and
        transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
        not receipt['model_access'] and receipt['binary_sha256'] == receipt['binary_sha256_after'],
        'Incomplete component or unsafe failure')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
        not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Ownership changed')
    source = read(ROOT/plan['source_variant_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    rows = [json.loads(s) for s in (path/'results/03.log').read_text().splitlines() if s.startswith('{"event"')]
    checks = [r for r in rows if r['event'] == 'producer_q8_check']
    timings = [r for r in rows if r['event'] == 'producer_q8_timing']
    complete = [r for r in rows if r['event'] == 'complete']
    require((len(checks), len(timings), len(complete)) == (64, 56, 1) and
        {r['case'] for r in checks} == set(plan['component_cases']), 'Incomplete coverage')
    expected, replay = set(), []
    for row in checks:
        case = plan['component_cases'][row['case']]
        require(all(row[k] == v for k, v in case.items()) and row['safety_pass'], 'Case geometry/safety changed')
        ids, counts, _, padded = prior.identities(case)
        slots, ne, cap, m = len(ids), case['experts'], case['capacity'], case['out_width']
        hashes = {}
        def load(field, count, dtype, guarded=True):
            file = path/'results'/(row['case']+'-'+field+'.bin')
            expected.add(file.name)
            raw = file.read_bytes()
            require(len(raw) == count*np.dtype(dtype).itemsize+(128 if guarded else 0), 'Array size differs: '+file.name)
            if guarded:
                require(raw[:64] == raw[-64:] == bytes([0xa5])*64, 'Guard differs: '+file.name)
            hashes[field] = sha(file)
            return np.frombuffer(raw, dtype=dtype, count=count, offset=64 if guarded else 0)
        physical = np.empty(slots, dtype=np.int64)
        dead = None
        for name in ('parent', 'candidate'):
            d = {field: load(name+'-'+field, size, '<i4') for field, size in
                 (('bounds',ne+1),('cursor',ne),('tokens',cap),('slots',cap))}
            require(np.array_equal(d['bounds'],padded) and np.array_equal(d['cursor'],counts), 'Routing prefix/count differs')
            seen = []
            for e in range(ne):
                live = slice(padded[e],padded[e]+counts[e])
                holes = slice(padded[e]+counts[e],padded[e+1])
                actual = d['slots'][live]
                require(np.all((actual >= 0) & (actual < slots)), 'Invalid route slot')
                require(np.all(ids[actual] == e) and np.array_equal(d['tokens'][live],actual//case['used']), 'Route identity differs')
                require(np.all(d['slots'][holes] == -1) and np.all(d['tokens'][holes] == -1), 'Routing hole changed')
                if name == 'candidate': physical[actual] = np.arange(padded[e],padded[e]+counts[e])
                seen.extend(actual)
            require(np.all(d['slots'][padded[-1]:] == -1) and np.all(d['tokens'][padded[-1]:] == -1), 'Routing tail changed')
            require(np.array_equal(np.sort(seen),np.arange(slots)), 'Routing permutation differs')
            if name == 'candidate': dead = d['slots'] < 0
        gate = load('parent-gate',slots*640,'<f4')
        parent = load('parent-down',slots*m,'<u2')
        candidate = load('candidate-down',slots*m,'<u2')
        half = load('parent-half',slots*640,'<f2')
        inverse = load('parent-inverse',slots,'<f4')
        packed = load('candidate-q8',6*cap*144,'u1').reshape(6,cap,144)
        ref_q8 = load('reference-q8',6*slots*144,'u1').reshape(6,slots,144)
        ref_down = load('reference-down',slots*m,'<f4')
        for a in (gate,parent.view('<f2'),candidate.view('<f2'),half,inverse,ref_down):
            require(np.isfinite(a).all(), 'Nonfinite output')
        actual = packed[:,physical,:]
        require(np.all(actual[5] == 0), 'Stored K tail changed')
        require(np.all(packed[:,dead,:].copy().view('<u4') == 0x7fc0beef), 'Inactive Q8 rows changed')
        format_errors = int(np.count_nonzero(actual != ref_q8))
        reference_errors = int(np.count_nonzero(candidate != ref_down.astype('<f2').view('<u2')))
        parent_changes = int(np.count_nonzero(candidate != parent))
        require((format_errors,reference_errors,parent_changes) ==
            (row['format_byte_errors'],row['reference_half_errors'],row['parent_half_changes']), 'Full-array counters differ')
        oracle = load('fp64-oracle',96*3,'<f8',False).reshape(96,3)
        require(np.isfinite(oracle).all() and row['oracle_samples'] == 96, 'Invalid FP64 samples')
        indices = np.arange(96,dtype=np.uint64)*(slots*m-1)//95
        require(np.array_equal(oracle[:,0],indices), 'Oracle sample indices differ')
        require(np.array_equal(oracle[:,2],candidate.view('<f2')[indices].astype(np.float64)), 'Oracle observations differ')
        error = oracle[:,1]-oracle[:,2]
        rms = math.sqrt(float(np.sum(error*error))/max(float(np.sum(oracle[:,1]**2)),1e-30))
        scaled = float(np.max(np.abs(error)))/max(float(np.max(np.abs(oracle[:,1]))),1e-15)
        require(math.isclose(rms,row['relative_rms'],rel_tol=1e-9,abs_tol=1e-15) and
            math.isclose(scaled,row['scaled_error'],rel_tol=1e-9,abs_tol=1e-15), 'Saved oracle errors differ')
        oracle_pass = rms <= 0.002 and scaled <= 0.002
        require(row['oracle_pass'] == oracle_pass, 'Oracle verdict differs')
        replay.append(dict(case=row['case'], hashes=hashes, format_byte_errors=format_errors,
            reference_half_errors=reference_errors, parent_half_changes=parent_changes,
            oracle_relative_rms=rms, oracle_scaled_error=scaled, oracle_pass=oracle_pass))
    require(len(expected) == 1088 and expected == {p.name for p in (path/'results').glob('*.bin')}, 'Output inventory differs')
    strict = all(not r['format_byte_errors'] and not r['reference_half_errors'] and r['oracle_pass'] for r in replay)
    require(complete[0]['pass'] == strict and exits[-1] == (0 if strict else 1), 'Original numeric failure status lost')
    summaries = []
    for case_name in ('balanced','skew'):
        active = int(np.count_nonzero(prior.identities(plan['component_cases'][case_name+'-before'])[1]))
        weight_bytes = active*(640*10*66*2+2560*3*84)
        require(weight_bytes > 32*1024**2, 'Weights fit MALL')
        for scope in ('gate_up','expert_chain'):
            arms = {}
            for candidate in (False,True):
                group = [r for r in timings if r['case'] == case_name and r['scope'] == scope and r['candidate'] == candidate]
                require([r['rep'] for r in group] == list(range(7)) and all(
                    r['candidate'] == bool((r['rep']+r['order']) % 2) and r['warmup'] == (r['rep'] < 2) and
                    r['iterations'] == 3 and r['active_experts'] == active and r['active_weight_bytes'] == weight_bytes and
                    math.isfinite(r['us_per_iteration']) and r['us_per_iteration'] > 0 for r in group), 'Timing scope changed')
                samples = [r['us_per_iteration'] for r in group if not r['warmup']]
                arms['candidate' if candidate else 'reference'] = dict(samples=samples,
                    median=statistics.median(samples),min=min(samples),max=max(samples))
            summaries.append(dict(case=case_name,scope=scope,**arms,
                candidate_time_change_percent=100*(arms['candidate']['median']/arms['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-producer-q8-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(receipt['artifacts']),
        complete_output_array_count=1088, binary_sha256=receipt['binary_sha256'],
        strict_numerical_pass=strict, replay=replay, checks=checks,timings=timings,summaries=summaries,
        safe_model_performance_admissible=True, model_inference=False, independent_model_quality=False,goal_met=False,
        limits='Full routing reconstructed; full Q8/raw-MMQ differential comparisons;96 saved FP64 affine samples per case. Synthetic inputs, not original-model quality or throughput.')
    with output.open('x') as f:
        json.dump(report,f,indent=2)
        f.write('\n')
    print(json.dumps(dict(strict_numerical_pass=strict, command_exits=exits,
        complete_arrays=1088, summaries=summaries,safe_model_performance_admissible=True)))

if __name__ == '__main__':
    main()
