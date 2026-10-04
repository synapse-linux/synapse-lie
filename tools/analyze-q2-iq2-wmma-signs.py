#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify complete paired IQ2 WMMA cycles; retain failure, no model-rate claim."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
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
SHAPES = ((2040, 512, 64, 512), (2048, 128, 128, 256))
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tests/q2_iq2_wmma_signs.cpp',
            'tests/q2_iq2_pair.cpp', 'tests/q2_operator_fixture.hpp', 'tests/q2_remote_test.py',
            'tools/q2-remote.py', 'tools/q2-runner.py', 'tools/q2_process.py', 'tools/q2_thermal.py')


def observations(log):
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    require(len(events) == 17, 'Incomplete cycle event inventory')
    weights = events[0]
    require(weights['event'] == 'iq2_wmma_weights' and weights['bytes'] == 432537600,
            'Wrong encoded weight inventory')
    for field in ('gate_sha256', 'up_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', weights[field]), 'Missing input identity')
    cases = {}
    for i, (tokens, active, tile, tiles) in enumerate(SHAPES):
        samples = events[1 + 8*i:8 + 8*i]
        geometry = events[8 + 8*i]
        for j, row in enumerate(samples):
            require(row['event'] == 'iq2_wmma_cycle' and row['sample'] == j and
                    row['warmup'] is (j < 2) and row['tokens'] == tokens and
                    row['active_experts'] == active and row['tile'] == tile and row['calls'] == 8,
                    'Wrong complete cycle timing scope')
            value = row['microseconds_per_call']
            require(type(value) in (int, float) and math.isfinite(value) and value > 0,
                    'Invalid complete cycle duration')
        require(geometry['event'] == 'iq2_wmma_geometry' and geometry['tokens'] == tokens and
                geometry['active_experts'] == active and geometry['tile'] == tile and
                geometry['tiles'] == tiles and geometry['output_values'] == tokens*10*640 and
                geometry['active_weight_bytes'] == active*640*10*66*2,
                'Wrong routing/working-set geometry')
        for field in ('input_sha256', 'ids_sha256'):
            require(re.fullmatch('[0-9a-f]{64}', geometry[field]), 'Missing operand identity')
        cases[str(tokens)] = dict(geometry=geometry, samples=samples,
            median_us=statistics.median(r['microseconds_per_call'] for r in samples[2:]))
    return dict(weights=weights, cases=cases)


def output_inventory():
    result = {}
    for tile in (16, 48, 64, 128):
        for kind in ('tiny', 'normal'):
            for n, m in ((17, 5), (65, 129)):
                result[f'operator-IQ2-pair-n{n}-m{m}-tile{tile}-{kind}.f32'] = n*2*m
    for kind in ('tiny', 'normal'):
        result[f'operator-IQ2-pair-n17-m640-tile64-{kind}.f32'] = 17*2*640
    for n, active, _, _ in SHAPES:
        result[f'iq2-wmma-n{n}-e{active}.f32'] = n*10*640
        result[f'operator-iq2-wmma-n{n}-e{active}.f32'] = 256
    return result


def arm(root, candidate, host):
    r = common.artifacts(root)
    transport = read(root/'transport.json')
    require(r['state'] == 'SYNTHETIC_IQ2_WMMA_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT' and
            r['mode'] == 'iq2-wmma-signs-check' and r['model_access'] is False and
            len(r['commands']) == 3, 'Incomplete component execution')
    require(transport['source_variant'] == ('iq2-wmma-signs' if candidate else 'iq2-wmma-reference')
            and not transport['rebuild_mmq'] and 'mmq_reuse' not in r and
            r['binary_sha256'] == r['binary_sha256_after'], 'Wrong component binary/source')
    require(r['locks'] == r['postflight_locks'] and
            [(x['device'], x['inode']) for x in r['locks']] ==
            [(52,3232146), (52,3206482), (52,3228451), (55,45067)] and
            not r['preflight_kfd'] and not r['postflight_kfd'], 'Ownership mismatch')
    expected = read(ROOT/'config'/('q2-iq2-wmma-signs-source.json' if candidate else
                                  'q2-iq2-signs-ordered-asm-source.json'))['files']
    with tarfile.open(root/'source.tar.gz') as source, tarfile.open(host/'source.tar.gz') as h:
        actual = {m.name[7:]: hashlib.sha256(source.extractfile(m).read()).hexdigest()
                  for m in source.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(actual == expected, 'Provider changed')
        for name in FIXTURES:
            require(source.extractfile(name).read() == h.extractfile(name).read(),
                    'Host/fixture mismatch: '+name)
    log = (root/'results/03.log').read_text()
    require(log.count('PASS synthetic IQ2 WMMA cycles; no model throughput') == 1,
            'Missing complete fixture marker')
    report = observations(log)
    checks = re.findall(r'^(\S+) rrms=(\S+) scaled_max=(\S+)$', log, re.M)
    expected_labels = {n.removeprefix('operator-').removesuffix('.f32')
                       for n in output_inventory() if n.startswith('operator-')}
    require(len(checks) == 20 and {r[0] for r in checks} == expected_labels,
            'Missing independent oracle checks')
    require(all(math.isfinite(float(v)) and 0 <= float(v) <= .002
                for row in checks for v in row[1:]), 'Independent tolerance failed')
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
    for n, _, _, _ in SHAPES:
        a, b = [reports[k]['cases'][str(n)] for k in ('reference', 'candidate')]
        require(a['geometry'] == b['geometry'], 'Different input/geometry')
        cells[str(n)] = dict(reference_us=a['median_us'], candidate_us=b['median_us'],
                            time_change_percent=100*(b['median_us']/a['median_us']-1))
    expected = output_inventory()
    for directory in (args.reference, args.candidate):
        require({p.name for p in (directory/'results').glob('*.f32')} == expected.keys(),
                'Different output inventory')
    pairs = {name:buffers.compare_buffer((args.reference/'results'/name).read_bytes(),
                    (args.candidate/'results'/name).read_bytes(), 'f', size)
             for name, size in expected.items()}
    exact = all(row['exact'] for row in pairs.values())
    result = dict(schema='synapse-lie.q2-iq2-wmma-signs-results.v1',
        scope='Synthetic narrowing/compaction/fused IQ2 gate-up-SwiGLU cycles; no model rates',
        arms=reports, cells=cells, pairs=pairs, exact=exact, promoted=False, goal_met=False,
        component_candidate=exact and all(c['time_change_percent'] < 0 for c in cells.values()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(exact=exact, cells=cells, output_pairs=len(pairs))))
    raise SystemExit(0 if exact else 1)


if __name__ == '__main__':
    main()
