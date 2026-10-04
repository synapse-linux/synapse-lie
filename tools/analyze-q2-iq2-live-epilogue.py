#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify IQ2 empty-epilogue cycles with measured routing; no model-rate claim."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


common = module('analyze-q2-curve.py')
buffers = module('analyze-q2-hc-up.py')
require, read, sha = common.require, common.read, common.sha
PLAN_PATH = ROOT/'config/q2-iq2-live-epilogue-plan.json'
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tests/q2_iq2_wmma_signs.cpp',
            'tests/q2_iq2_live_epilogue.cpp', 'tests/q2_iq2_routes.hpp',
            'tests/q2_iq2_routes.cpp', 'tests/q2_iq2_pair.cpp', 'tests/q2_packed_fixture.hpp',
            'tests/q2_operator_fixture.hpp', 'tests/q2_remote_test.py',
            'config/q2-iq2-live-epilogue-plan.json', 'tools/analyze-q2-iq2-live-epilogue.py',
            'tools/q2-remote.py', 'tools/q2-runner.py', 'tools/q2_process.py', 'tools/q2_thermal.py')


def cases(plan=None):
    plan = read(PLAN_PATH) if plan is None else plan
    require(plan['schema'] == 'synapse-lie.q2-iq2-live-epilogue-plan.v1', 'Wrong route plan')
    rows = plan['representative_routing']
    require(len(rows) == 4, 'Incomplete route plan')
    expected = ((0,6,2040,128), (0,0,2040,64), (131072,16,2046,128), (131072,6,2046,64))
    data = []
    for row, shape in zip(rows, expected):
        require(tuple(row[k] for k in ('depth','layer','tokens','gate_rows')) == shape and
                row['used'] == 10 and row['experts'] == 512, 'Wrong canonical route case')
        data.append((f"depth{row['depth']}-layer{row['layer']}", row['tokens'],
                     row['gate_rows'], row['counts']))
    data.append(('full-tiles', 2048, 128, [128]*160 + [0]*352))
    result = {}
    for name, n, tile, counts in data:
        require(len(counts) == 512 and all(type(c) is int and 0 <= c <= n for c in counts)
                and sum(counts) == n*10, 'Invalid per-expert count distribution')
        ids, cursor = [-1]*(n*10), 0
        for e, count in enumerate(counts):
            for i in range(cursor, cursor + count):
                ids[(i % n)*10 + i//n] = e
            cursor += count
        require(all(len(set(ids[t*10:(t+1)*10])) == 10 for t in range(n)),
                'Duplicate expert within a token')
        observed = [0]*512
        for expert in ids:
            observed[expert] += 1
        require(observed == counts, 'Different reconstructed histogram')
        active = sum(c > 0 for c in counts)
        tiles = sum((c+tile-1)//tile for c in counts)
        result[name] = dict(case=name, tokens=n, active_experts=active, tile=tile,
            tiles=tiles, output_values=n*10*640, active_weight_bytes=active*640*10*66*2,
            live_fragments=sum((c+15)//16 for c in counts),
            reserved_fragments=tiles*(tile//16),
            counts_sha256=hashlib.sha256(struct.pack('<512I', *counts)).hexdigest(),
            ids_sha256=hashlib.sha256(struct.pack('<'+str(n*10)+'i', *ids)).hexdigest())
    return result


def verify_routing_provenance():
    plan = read(PLAN_PATH)
    log = ROOT/'evidence/q2-route-profile-model-r1/results/curve-server.log'
    require(sha(log) == plan['routing_log_sha256'], 'Routing evidence changed')
    events = [json.loads(line) for line in log.read_text().splitlines()
              if '"event":"q2_route_counts"' in line]
    profile = read(ROOT/plan['routing_evidence'])
    for row in plan['representative_routing']:
        matches = [e for e in events if e['forward_id'] == row['forward_id'] and
                   e['layer'] == row['layer']]
        require(len(matches) == 1 and all(matches[0][k] == row[k]
                for k in ('counts','tokens','used','experts','gate_rows')),
                'Component counts differ from observed canonical routing')
        accepted = [e for r in profile['rows'] if r['depth'] == row['depth']
                    for e in r['layers'] if e['forward_id'] == row['forward_id'] and
                    e['layer'] == row['layer']]
        require(len(accepted) == 1 and accepted[0]['tokens'] == row['tokens'],
                'Routing counts do not belong to an accepted continuation')
    return dict(log_sha256=sha(log), plan_sha256=sha(PLAN_PATH),
                accepted_canonical_distributions=4, synthetic_full_tile_controls=1)


def oracle_cases():
    for tile in (16,48,64,128):
        for n in sorted({15,16,17,tile-1,tile,tile+1}):
            for kind in ('normal','tiny'):
                yield n, 5, tile, kind
        yield 65, 129, tile, 'normal'


def output_inventory():
    result = {}
    for n, m, tile, kind in oracle_cases():
        result[f'operator-IQ2-pair-n{n}-m{m}-tile{tile}-{kind}.f32'] = n*2*m
        result[f'packed-iq2-n{n}-m{m}-tile{tile}-{kind}.u32'] = n*2*m
    for name, row in cases().items():
        result[f'iq2-epilogue-{name}.f32'] = row['output_values']
        result[f'operator-iq2-epilogue-{name}.f32'] = 256
    return result


def observations(log):
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    expected = cases()
    require(len(events) == 2 + 8*len(expected), 'Incomplete cycle event inventory')
    weights = events[0]
    require(weights['event'] == 'iq2_epilogue_weights' and weights['bytes'] == 432537600,
            'Wrong encoded weight inventory')
    for field in ('gate_sha256', 'up_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', weights[field]), 'Missing input identity')
    result = {}
    for i, (name, target) in enumerate(expected.items()):
        samples = events[1+8*i:8+8*i]
        geometry = events[8+8*i]
        for j, row in enumerate(samples):
            require(row['event'] == 'iq2_epilogue_cycle' and row['sample'] == j and
                    row['warmup'] is (j < 2) and row['calls'] == 8 and
                    all(row[k] == target[k] for k in ('case','tokens','active_experts','tile')),
                    'Wrong complete cycle timing scope')
            value = row['microseconds_per_call']
            require(type(value) in (int,float) and math.isfinite(value) and value > 0,
                    'Invalid complete cycle duration')
        require(geometry['event'] == 'iq2_epilogue_geometry' and
                all(geometry[k] == v for k, v in target.items()),
                'Wrong routing/working-set geometry')
        require(re.fullmatch('[0-9a-f]{64}', geometry['input_sha256']), 'Missing operand identity')
        result[name] = dict(geometry=geometry, samples=samples,
            median_us=statistics.median(r['microseconds_per_call'] for r in samples[2:]))
    completion = events[-1]
    count = len(list(oracle_cases())) + len(expected)
    require(completion['event'] == 'iq2_epilogue_complete' and
            type(completion['numerical_pass']) is bool and completion['independent_checks'] == count
            and type(completion['failures']) is int and 0 <= completion['failures'] <= count
            and completion['numerical_pass'] is (completion['failures'] == 0)
            and completion['model_inference'] is False, 'Incomplete numerical verdict')
    return dict(weights=weights, cases=result, completion=completion)


def arm(root, candidate, host):
    r, transport = common.artifact_integrity(root)
    exits = [c['exit_code'] for c in r['commands']]
    require(exits in ([0,0,0], [0,0,1]) and transport['exit_code'] == exits[-1],
            'Incomplete or interrupted component execution')
    require(r['state'] in ('SYNTHETIC_IQ2_EPILOGUE_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT', 'FAILED') and
            r['mode'] == 'iq2-live-epilogue-check' and r['model_access'] is False and
            'finished_at' in r, 'Incomplete component execution')
    for row in [r, *r['commands']]:
        require(not any(row.get(k) for k in ('thermal_stop', 'postflight_error', 'timeout',
                    'foreign_kfd', 'lingering_descendants')), 'Runtime/retirement failure')
    require(transport['source_variant'] == ('iq2-live-epilogue' if candidate else 'iq2-epilogue-reference')
            and not transport['rebuild_mmq'] and 'mmq_reuse' not in r and
            r['binary_sha256'] == r['binary_sha256_after'], 'Wrong component binary/source')
    require(r['locks'] == r['postflight_locks'] and
            [(x['device'], x['inode']) for x in r['locks']] ==
            [(52,3232146), (52,3206482), (52,3228451), (55,45067)] and
            not r['preflight_kfd'] and not r['postflight_kfd'], 'Ownership mismatch')
    expected = read(ROOT/'config'/('q2-iq2-live-epilogue-source.json' if candidate else
                                  'q2-iq2-signs-ordered-asm-source.json'))['files']
    with tarfile.open(root/'source.tar.gz') as source, tarfile.open(host/'source.tar.gz') as h:
        actual = {m.name[7:]: hashlib.sha256(source.extractfile(m).read()).hexdigest()
                  for m in source.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(actual == expected, 'Provider changed')
        for name in FIXTURES:
            require(source.extractfile(name).read() == h.extractfile(name).read(),
                    'Host/fixture mismatch: '+name)
        require(source.extractfile(str(PLAN_PATH.relative_to(ROOT))).read() == PLAN_PATH.read_bytes(),
                'Analyzed route plan differs from executed route plan')
    log = (root/'results/03.log').read_text()
    marker = ('PASS' if exits[-1] == 0 else 'FAIL') + ' synthetic IQ2 epilogue cycles; no model throughput'
    require(log.splitlines().count(marker) == 1,
            'Missing complete fixture marker')
    report = observations(log)
    checks = re.findall(r'^(\S+) rrms=(\S+) scaled_max=(\S+)$', log, re.M)
    expected_labels = {n.removeprefix('operator-').removesuffix('.f32')
                       for n in output_inventory() if n.startswith('operator-')}
    require(len(checks) == len(expected_labels) and {r[0] for r in checks} == expected_labels,
            'Missing independent oracle checks')
    require(all(math.isfinite(float(v)) and float(v) >= 0
                for row in checks for v in row[1:]), 'Invalid independent error metric')
    failed = sum(any(float(v) > .002 for v in row[1:]) for row in checks)
    require(report['completion']['failures'] == failed and exits[-1] == bool(failed) and
            r['state'] == ('FAILED' if failed else
                'SYNTHETIC_IQ2_EPILOGUE_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'),
            'Numerical failure or command exit was not retained')
    report.update(directory=str(root), source_files=len(actual), artifacts=len(r['artifacts']),
                  checks=checks, command_exits=[c['exit_code'] for c in r['commands']])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'reference', 'candidate'):
        p.add_argument(name, type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite retained evidence')
    provenance = verify_routing_provenance()
    host = common.artifacts(args.host)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and host['model_access'] is False,
            'Missing successful host qualification')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 21' in (args.host/'results'/name).read_text(),
                'Missing complete Debug/ASan suite')
    reports = {k:arm(getattr(args, k), k == 'candidate', args.host) for k in ('reference', 'candidate')}
    require(reports['reference']['weights'] == reports['candidate']['weights'], 'Different weight bytes')
    cells = {}
    for n in cases():
        a, b = [reports[k]['cases'][str(n)] for k in ('reference', 'candidate')]
        require(a['geometry'] == b['geometry'], 'Different input/geometry')
        cells[str(n)] = dict(reference_us=a['median_us'], candidate_us=b['median_us'],
                            time_change_percent=100*(b['median_us']/a['median_us']-1))
    expected = output_inventory()
    for directory in (args.reference, args.candidate):
        require({p.name for p in (directory/'results').iterdir() if p.suffix in ('.f32','.u32')} == expected.keys(),
                'Different output inventory')
    pairs = {name:buffers.compare_buffer((args.reference/'results'/name).read_bytes(),
                    (args.candidate/'results'/name).read_bytes(), 'I' if name.endswith('.u32') else 'f', size)
             for name, size in expected.items()}
    exact = all(row['exact'] for row in pairs.values())
    numerical_pass = all(r['completion']['numerical_pass'] for r in reports.values())
    result = dict(schema='synapse-lie.q2-iq2-live-epilogue-results.v1',
        scope='Measured route counts, synthetic narrowing/compaction/fused IQ2 gate-up-SwiGLU cycles; no model rates',
        routing_provenance=provenance, arms=reports, cells=cells, pairs=pairs,
        exact=exact, numerical_pass=numerical_pass,
        promoted=False, goal_met=False,
        component_candidate=exact and numerical_pass and
                            all(c['time_change_percent'] < 0 for c in cells.values()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(exact=exact, numerical_pass=numerical_pass, cells=cells, output_pairs=len(pairs))))
    raise SystemExit(0 if exact and numerical_pass else 1)


if __name__ == '__main__':
    main()
