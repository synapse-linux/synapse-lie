#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the paired mixed-tile component, without claiming model rates."""
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
spec = importlib.util.spec_from_file_location('epilogue', Path(__file__).with_name('analyze-q2-iq2-live-epilogue.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
require, read, sha = base.require, base.read, base.sha
SCOPES = ('resident-map-cycle', 'map-upload-cycle')
FIXTURES = (*base.FIXTURES, 'experiments/iq2_mixed_tiles.c', 'experiments/iq2_mixed_tiles.h',
            'tests/iq2_mixed_tiles.c', 'tests/q2_iq2_mixed_tiles.cpp',
            'config/q2-iq2-mixed-plan.json', 'tools/analyze-q2-iq2-mixed.py')


def geometry(mixed):
    counts = [r['counts'] for r in read(base.PLAN_PATH)['representative_routing']]
    counts.append([128]*160 + [0]*352)
    result = {}
    for (name, original), buckets in zip(base.cases().items(), counts):
        row = dict(original)
        width = row.pop('tile')
        row.pop('tiles')
        if mixed:
            wide = [e | (j << 16) for e, c in enumerate(buckets) for j in range(((c+63)//64)//2)]
            tail = [e | ((((c+63)//64)-1) << 16) for e, c in enumerate(buckets) if ((c+63)//64) % 2]
        else:
            tiles = [e | (j << 16) for e, c in enumerate(buckets) for j in range((c+width-1)//width)]
            wide, tail = (tiles, []) if width == 128 else ([], tiles)
        row.update(original_tile=width, wide_tiles=len(wide), tail_tiles=len(tail),
                   reserved_fragments=len(wide)*8+len(tail)*4,
                   map_sha256=hashlib.sha256(struct.pack('<'+str(len(wide)+len(tail))+'i', *(wide+tail))).hexdigest())
        result[name] = row
    return result


def observations(log, mixed):
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    targets = geometry(mixed)
    require(len(events) == 2 + 15*len(targets), 'Incomplete mixed cycle events')
    weights = events[0]
    require(weights['event'] == 'iq2_mixed_weights' and weights['bytes'] == 432537600,
            'Wrong weight inventory')
    require(all(re.fullmatch('[0-9a-f]{64}', weights[k]) for k in ('gate_sha256','up_sha256')),
            'Missing weight identity')
    cases = {}
    for i, (name, target) in enumerate(targets.items()):
        samples = events[1+15*i:15+15*i]
        observed = events[15+15*i]
        require(observed['event'] == 'iq2_mixed_geometry' and
                all(observed[k] == v for k,v in target.items()) and
                re.fullmatch('[0-9a-f]{64}', observed['input_sha256']), 'Wrong mixed geometry')
        scopes = {}
        for offset, scope in enumerate(SCOPES):
            series = samples[offset*7:(offset+1)*7]
            for j, row in enumerate(series):
                require(row['event'] == 'iq2_mixed_cycle' and row['case'] == name and
                        row['sample'] == j and row['warmup'] is (j < 2) and
                        row['scope'] == scope and row['policy'] == ('mixed' if mixed else 'reference')
                        and row['calls'] == 8, 'Wrong timed work or policy')
                require(all(type(row[k]) in (int,float) and math.isfinite(row[k]) and row[k] > 0
                            for k in ('microseconds_per_call','wall_microseconds_per_call')),
                        'Invalid mixed timing')
            scopes[scope] = dict(samples=series,
                median_us=statistics.median(r['microseconds_per_call'] for r in series[2:]),
                median_wall_us=statistics.median(r['wall_microseconds_per_call'] for r in series[2:]))
        cases[name] = dict(geometry=observed, scopes=scopes)
    done = events[-1]
    require(done['event'] == 'iq2_mixed_complete' and type(done['numerical_pass']) is bool and
            done['independent_checks'] == len(targets) and type(done['failures']) is int and
            0 <= done['failures'] <= len(targets) and
            done['numerical_pass'] is (done['failures'] == 0) and done['model_inference'] is False,
            'Incomplete mixed numerical verdict')
    return dict(weights=weights, cases=cases, completion=done)


def output_inventory():
    return {name: size for case, row in base.cases().items()
            for name, size in ((f'iq2-mixed-{case}.f32', row['output_values']),
                               (f'operator-iq2-mixed-{case}.f32', 256))}


def arm(root, mixed, host):
    r, transport = base.common.artifact_integrity(root)
    exits = [c['exit_code'] for c in r['commands']]
    mode = 'iq2-mixed-check' if mixed else 'iq2-mixed-reference-check'
    state = 'SYNTHETIC_IQ2_MIXED_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
    require(exits in ([0,0,0], [0,0,1]) and transport['exit_code'] == exits[-1] and
            transport['mode'] == mode and transport['source_variant'] == 'iq2-mixed' and
            not transport['detached'] and not transport['rebuild_mmq'], 'Wrong mixed invocation')
    require(r['mode'] == mode and r['model_access'] is False and 'finished_at' in r and
            r['state'] in (state, 'FAILED'), 'Incomplete mixed arm')
    # Guard the actual executed policy, not just the transport's label.
    argv = r['commands'][-1]['argv']
    require(len(argv) == 2 and Path(argv[0]).name == 'q2_iq2_mixed_tiles' and
            argv[1] == ('mixed' if mixed else 'reference'), 'Wrong executed mixed policy')
    for row in [r, *r['commands']]:
        require(not any(row.get(k) for k in ('thermal_stop','postflight_error','timeout',
                    'foreign_kfd','lingering_descendants')), 'Runtime/retirement failure')
    require('mmq_reuse' not in r and r['binary_sha256'] == r['binary_sha256_after'],
            'Wrong component binary/source')
    require(r['locks'] == r['postflight_locks'] and
            [(x['device'],x['inode']) for x in r['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)] and
            not r['preflight_kfd'] and not r['postflight_kfd'], 'Ownership mismatch')
    expected = read(ROOT/'config/q2-iq2-signs-ordered-asm-source.json')['files']
    with tarfile.open(root/'source.tar.gz') as source, tarfile.open(host/'source.tar.gz') as h:
        actual = {m.name[7:]: hashlib.sha256(source.extractfile(m).read()).hexdigest()
                  for m in source.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(actual == expected, 'Provider changed')
        for name in FIXTURES:
            payload = source.extractfile(name).read()
            require(payload == h.extractfile(name).read() == (ROOT/name).read_bytes(),
                    'Host/executed/analyzed fixture mismatch: '+name)
    log = (root/'results/03.log').read_text()
    marker = ('PASS' if exits[-1] == 0 else 'FAIL') + ' synthetic IQ2 mixed cycles; no model throughput'
    require(log.splitlines().count(marker) == 1, 'Missing complete mixed fixture marker')
    report = observations(log, mixed)
    checks = re.findall(r'^(\S+) rrms=(\S+) scaled_max=(\S+)$', log, re.M)
    labels = {'iq2-mixed-'+name for name in base.cases()}
    require(len(checks) == len(labels) and {r[0] for r in checks} == labels,
            'Missing independent oracle checks')
    require(all(math.isfinite(float(v)) and float(v) >= 0 for row in checks for v in row[1:]),
            'Invalid independent errors')
    failed = sum(any(float(v) > .002 for v in row[1:]) for row in checks)
    require(report['completion']['failures'] == failed and exits[-1] == bool(failed) and
            r['state'] == ('FAILED' if failed else state), 'Numerical failure was not retained')
    report.update(directory=str(root), source_files=len(actual), artifacts=len(r['artifacts']),
                  checks=checks, command_exits=exits, binary_sha256=r['binary_sha256'])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('host','reference','candidate'): p.add_argument(key, type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite retained evidence')
    plan = read(ROOT/'config/q2-iq2-mixed-plan.json')
    require(sha(ROOT/plan['provider_manifest']) == plan['provider_manifest_sha256'] and
            sha(ROOT/plan['routing_plan']) == plan['routing_plan_sha256'], 'Mixed plan parent changed')
    provenance = base.verify_routing_provenance()
    host = base.common.artifacts(args.host)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and len(host['commands']) == 6
            and host['model_access'] is False, 'Missing host qualification')
    for name in ('03.log','06.log'):
        log = (args.host/'results'/name).read_text()
        require('100% tests passed out of 22' in log and 'iq2_mixed_tiles' in log,
                'Missing complete Debug/ASan mixed map suite')
    reports = {key: arm(getattr(args,key), key == 'candidate', args.host) for key in ('reference','candidate')}
    require(reports['reference']['weights'] == reports['candidate']['weights'], 'Different weights')
    cells = {}
    for name in base.cases():
        a,b = [reports[k]['cases'][name] for k in ('reference','candidate')]
        require(all(a['geometry'][k] == b['geometry'][k] for k in
                    ('input_sha256','ids_sha256','counts_sha256','output_values','live_fragments')),
                'Different input or live work')
        cells[name] = {scope: dict(reference_us=a['scopes'][scope]['median_us'],
            candidate_us=b['scopes'][scope]['median_us'],
            time_change_percent=100*(b['scopes'][scope]['median_us']/a['scopes'][scope]['median_us']-1),
            reference_wall_us=a['scopes'][scope]['median_wall_us'],
            candidate_wall_us=b['scopes'][scope]['median_wall_us'],
            wall_change_percent=100*(b['scopes'][scope]['median_wall_us']/a['scopes'][scope]['median_wall_us']-1))
            for scope in SCOPES}
    inventory = output_inventory()
    for root in (args.reference,args.candidate):
        require({p.name for p in (root/'results').glob('*.f32')} == inventory.keys(), 'Wrong output inventory')
    pairs = {name: base.buffers.compare_buffer((args.reference/'results'/name).read_bytes(),
                (args.candidate/'results'/name).read_bytes(), 'f', size) for name,size in inventory.items()}
    exact = all(row['exact'] for row in pairs.values())
    numerical = all(row['completion']['numerical_pass'] for row in reports.values())
    result = dict(schema='synapse-lie.q2-iq2-mixed-results.v1',
        scope='Complete synthetic IQ2 component with measured routing counts; no model rates',
        routing_provenance=provenance, arms=reports, cells=cells, pairs=pairs,
        exact=exact, numerical_pass=numerical, promoted=False, goal_met=False)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(exact=exact, numerical_pass=numerical, cells=cells, output_pairs=len(pairs))))
    raise SystemExit(0 if exact and numerical else 1)


if __name__ == '__main__':
    main()
