#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replay complete routed outputs using saved device maps and independent packing."""
import importlib.util
import json
import math
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def identities(case):
    n, used, ne = (case[k] for k in ('tokens', 'used', 'experts'))
    ids = []
    for t in range(n):
        base = (t*73) % (64 if case['skew'] and t % 4 else ne)
        ids.extend((base+s) % ne for s in range(used))
    ids = np.asarray(ids, dtype=np.int32)
    counts = np.bincount(ids, minlength=ne)
    logical = np.concatenate(([0], counts.cumsum()))
    padded = np.concatenate(([0], ((counts+15)//16*16).cumsum()))
    return ids, counts, logical, padded


def main():
    output = ROOT/'config/q2-compact-expert-chain-component-results.json'
    require(not output.exists(), 'Refusing to overwrite evidence')
    plan_path = ROOT/'config/q2-compact-expert-chain-plan.json'
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
    checks = [r for r in rows if r['event'] == 'compact_chain_check']
    timings = [r for r in rows if r['event'] == 'compact_chain_timing']
    complete = [r for r in rows if r['event'] == 'complete']
    require((len(checks),len(timings),len(complete)) == (24,56,1) and
            {r['case'] for r in checks} == set(plan['component_cases']), 'Incomplete coverage')
    expected, replay, oracle, routing = set(), [], [], []
    for row in checks:
        case = plan['component_cases'][row['case']]
        require(all(row[k] == v for k,v in case.items()), 'Case geometry changed')
        ids, counts, logical, padded = identities(case)
        slots, ne = len(ids), case['experts']
        data, hashes, orders = {}, {}, {}
        sizes = dict(bounds=ne+1, logical=ne+1, cursor=ne, tokens=case['capacity'],
                     slots=case['capacity'], gate=slots*640, half=slots*640,
                     scale=slots, down=slots*case['out_width'])
        for name in ('parent','candidate'):
            data[name], hashes[name] = {}, {}
            for field, size in sizes.items():
                dtype = '<u2' if field in ('half','down') else '<f4' if field in ('gate','scale') else '<i4'
                file = path/'results'/(row['case']+'-'+name+'-'+field+'.bin')
                expected.add(file.name)
                require(file.stat().st_size == size*np.dtype(dtype).itemsize+128, 'Truncated array')
                raw = file.read_bytes()
                require(raw[:64] == raw[-64:] == bytes([0xa5])*64, 'Guard differs')
                data[name][field] = np.frombuffer(raw, dtype=dtype, count=size, offset=64)
                hashes[name][field] = sha(file)
            d = data[name]
            for field, want in (('bounds',padded),('logical',logical),('cursor',counts)):
                require(np.array_equal(d[field],want), 'Independent routing prefix/count differs')
            order = []
            for e in range(ne):
                live = slice(padded[e],padded[e]+counts[e])
                dead = slice(padded[e]+counts[e],padded[e+1])
                actual = d['slots'][live]
                require(np.all((actual >= 0) & (actual < slots)), 'Invalid route slot')
                require(np.all(ids[actual] == e) and np.array_equal(d['tokens'][live],actual//case['used']),
                        'Independent route identity differs')
                require(np.all(d['slots'][dead] == -1) and np.all(d['tokens'][dead] == -1), 'Routing holes changed')
                order.extend(actual)
            require(np.all(d['slots'][padded[-1]:] == -1) and np.all(d['tokens'][padded[-1]:] == -1),
                    'Routing tail changed')
            order = np.asarray(order, dtype=np.int32)
            require(np.array_equal(np.sort(order),np.arange(slots)), 'Route is not a complete permutation')
            orders[name] = order
            routing.append(dict(case=row['case'], arm=name, slots=slots, complete_permutation=True,
                                map_hashes={k:hashes[name][k] for k in ('bounds','logical','cursor','tokens','slots')}))
            gate = d['gate'].reshape(slots,640)
            require(np.isfinite(gate).all() and np.isfinite(d['scale']).all() and
                    np.isfinite(d['half'].view('<f2')).all() and np.isfinite(d['down'].view('<f2')).all(),
                    'Nonfinite numerical output')
            peak = np.max(np.abs(gate.astype(np.float64)),axis=1)
            _, exponent = np.frexp(peak)
            shift = np.where(peak == 0,0,np.clip(14-exponent,-120,120))
            want_scale = np.ldexp(np.ones(slots,dtype=np.float64),-shift).astype('<f4')
            scale_errors = int(np.count_nonzero(want_scale.view('<u4') != d['scale'].view('<u4')))
            half_errors = signed_zero = 0
            # Bounded chunks retain the full independent conversion without a second giant array.
            for start in range(0,slots,256):
                stop = min(slots,start+256)
                scaled = np.ldexp(gate[start:stop].astype(np.float64),shift[start:stop,None]).astype('<f4')
                want = scaled.astype('<f2').view('<u2').reshape(-1)
                observed = d['half'][start*640:stop*640]
                half_errors += int(np.count_nonzero(want != observed))
                signed_zero += int(np.count_nonzero((want == 0x8000) & (observed == 0)))
            require(row[name+'_half_oracle_errors'] == half_errors and row[name+'_scale_oracle_errors'] == scale_errors,
                    'Independent full-array oracle disagrees with fixture counters')
            oracle.append(dict(case=row['case'],arm=name,half_errors=half_errors,scale_errors=scale_errors,
                               negative_zero_to_positive_zero=signed_zero))
        for field,width in (('gate',640),('half',640),('scale',1),('down',case['out_width'])):
            before = data['parent'][field].reshape(slots,width)
            after = data['candidate'][field].reshape(slots,width)
            if field != 'down': before = before[orders['candidate']]
            # Compare bits, retaining signed zero and every output byte.
            exact = bool(np.array_equal(before.view(np.uint8),after.view(np.uint8)))
            require(row[field+'_exact'] == exact, 'Fixture verdict differs from complete output arrays')
            replay.append(dict(case=row['case'],field=field,exact=exact,
                               parent_sha256=hashes['parent'][field],candidate_sha256=hashes['candidate'][field]))
    require(len(expected) == 432 and expected == {p.name for p in (path/'results').glob('*.bin')},
            'Output inventory differs')
    exact = all(r['exact'] for r in replay)
    oracle_pass = all(not r['half_errors'] and not r['scale_errors'] for r in oracle)
    require(complete[0]['pass'] == (exact and oracle_pass) and exits[-1] == (0 if exact and oracle_pass else 1),
            'Original numerical failure status lost')
    summaries = []
    for case_name in ('balanced','skew'):
        c = plan['component_cases'][case_name+'-before']
        active = int(np.count_nonzero(identities(c)[1]))
        weight_bytes = active*(640*(2560//256)*66*2+2560*3*84)
        require(weight_bytes > 32*1024**2, 'Production weights fit cache')
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
    report = dict(schema='synapse-lie.q2-compact-expert-chain-component.v1',**capsule,
        plan_sha256=sha(plan_path),command_exits=exits,artifact_count=len(receipt['artifacts']),
        complete_output_array_count=432,binary_sha256=receipt['binary_sha256'],
        numerical_exact=exact,oracle_pass=oracle_pass,replay=replay,checks=checks,
        routing=routing,independent_packing=oracle,timings=timings,summaries=summaries,
        safe_model_performance_admissible=True,model_inference=False,independent_model_quality=False,goal_met=False,
        limits='Complete routing and packing independently reconstructed; matrix outputs differential to retained production arithmetic. Synthetic balanced/skew traffic does not establish full-model quality or performance.')
    hc.write(output,report)
    print(json.dumps(dict(exits=exits,complete_pairs=len(replay),numerical_exact=exact,oracle_pass=oracle_pass,summaries=summaries)))


if __name__ == '__main__':
    main()
