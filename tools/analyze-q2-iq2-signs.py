#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify isolated IQ2 packed-sign pairs; never infer model throughput."""
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


curve = module('analyze-q2-curve.py')
buffers = module('analyze-q2-hc-up.py')
require, read, sha = curve.require, curve.read, curve.sha
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tests/q2_iq2_signs.hip',
            'tests/q2_operators.cpp', 'tests/q2_operator_fixture.hpp',
            'tests/q2_remote_test.py', 'tools/q2-remote.py', 'tools/q2-runner.py',
            'tools/q2_process.py', 'tools/q2_thermal.py')


def arm(root, key, host):
    r = curve.artifacts(root)
    transport = read(root/'transport.json')
    require(r['state'] == 'SYNTHETIC_IQ2_SIGN_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
            and r['mode'] == 'iq2-signs-check' and not r['model_access'], 'Wrong/incomplete scope')
    require(len(r['commands']) == 4 and transport['source_variant'] == 'iq2-signs-'+key
            and transport['rebuild_mmq'], 'Wrong source/build selection')
    require('mmq_reuse' not in r and r['binary_sha256'] == r['binary_sha256_after'], 'Binary changed/reused')
    require(r['locks'] == r['postflight_locks'] and
            [(x['device'], x['inode']) for x in r['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)] and
            not r['preflight_kfd'] and not r['postflight_kfd'], 'Ownership mismatch')
    for row in [r, *r['commands']]:
        require(not any(row.get(k) for k in ('thermal_stop','postflight_error','timeout',
                    'foreign_kfd','lingering_descendants')), 'Runtime guard failure')
    expected = (read(ROOT/'config/q2-curve-source.json')['variants']['q2']['files']
                if key == 'reference' else read(ROOT/'config'/
                    ('q2-iq2-signs-ordered-asm-source.json' if key == 'ordered'
                     else 'q2-iq2-signs-source.json'))['files'])
    with tarfile.open(root/'source.tar.gz') as source, tarfile.open(host/'source.tar.gz') as h:
        actual = {m.name[7:]: hashlib.sha256(source.extractfile(m).read()).hexdigest()
                  for m in source.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(actual == expected, 'Provider inventory changed')
        for name in FIXTURES:
            require(source.extractfile(name).read() == h.extractfile(name).read(), 'Host/fixture mismatch: '+name)
    original = (root/'results/03.log').read_text()
    require(original.count('PASS Q2 independent synthetic operators; no model inference') == 1,
            'Missing original operators')
    log = (root/'results/04.log').read_text()
    require(log.count('PASS IQ2 sign operators and synthetic complete cycle; no model throughput') == 1,
            'Missing fixture completion')
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    require(events[0] == dict(event='iq2_signs_exhaustive',codebook_entries=256,
            sign_indices=128,lane_outputs=1048576,exact=True), 'Incomplete exhaustive coverage')
    samples = events[1:]
    require(len(samples) == 7, 'Missing timing samples')
    for index, row in enumerate(samples):
        require(row['event'] == 'iq2_signs_cycle' and row['sample'] == index and
                row['warmup'] is (index < 2) and row['rotated_experts'] == 512 and
                row['calls'] == 64 and row['weight_bytes'] == 432537600,
                'Changed timing/rotation scope')
        require(math.isfinite(row['microseconds_per_call']) and row['microseconds_per_call'] > 0,
                'Invalid cycle duration')
    checks = re.findall(r'^iq2-signs-cycle-(\d+) rrms=(\S+) scaled_max=(\S+)$',log,re.M)
    require([int(row[0]) for row in checks] == list(range(64)), 'Missing FP64 checks')
    require(all(math.isfinite(float(v)) and 0 <= float(v) <= .002 for row in checks for v in row[1:]),
            'Independent tolerance failed')
    measured = [row['microseconds_per_call'] for row in samples if not row['warmup']]
    return dict(directory=str(root), source_files=len(actual), artifacts=len(r['artifacts']),
                command_exits=[c['exit_code'] for c in r['commands']], samples=samples,
                independent_samples=[dict(step=int(i),relative_rms=float(rms),
                    error_over_peak=float(peak),values=10) for i,rms,peak in checks],
                median_us=statistics.median(measured), min_us=min(measured), max_us=max(measured),
                collection_sha256=read(root/'collection.json')['sha256'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('host',type=Path)
    p.add_argument('reference',type=Path)
    p.add_argument('candidate',type=Path)
    p.add_argument('--ordered',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    host = curve.artifacts(args.host)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and len(host['commands']) == 6,
            'Incomplete host qualification')
    for name in ('03.log','06.log'):
        require('100% tests passed out of 19' in (args.host/'results'/name).read_text(), 'Host coverage changed')
    arms = {key:arm(getattr(args,key),'ordered' if key == 'candidate' and args.ordered else key,
                   args.host) for key in ('reference','candidate')}
    a, b = args.reference/'results', args.candidate/'results'
    names = {p.name for p in a.glob('*.f32')}
    require(len(names) == 110 and names == {p.name for p in b.glob('*.f32')}, 'Different output inventories')
    expected = {'iq2-signs-exhaustive.f32','iq2-signs-cycle.f32'} | {
        f'operator-iq2-signs-cycle-{i}.f32' for i in range(64)}
    require(expected <= names, 'Missing cycle outputs')
    pairs = {}
    for name in sorted(names):
        size = (a/name).stat().st_size
        count = 1048578 if name == 'iq2-signs-exhaustive.f32' else 409600 if name == 'iq2-signs-cycle.f32' else 10 if name.startswith('operator-iq2-signs-cycle-') else size//4
        pairs[name] = buffers.compare_buffer((a/name).read_bytes(),(b/name).read_bytes(),'f',count)
    exact = all(row['exact'] for row in pairs.values())
    delta = 100*(arms['candidate']['median_us']/arms['reference']['median_us']-1)
    report = dict(schema='synapse-lie.q2-iq2-signs-results.v1',
        scope='Synthetic C1 IQ2 gate/up complete cycle, 512 rotating experts; no original model throughput',
        arms=arms, pairs=pairs, exact=exact, median_time_change_percent=delta,
        component_candidate=exact and delta < 0, promoted=False, goal_met=False,
        limits='Two sequential process arms; five samples each are not independent model runs. Requires canonical full-grid PP/TG and quality qualification.')
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(exact=exact,output_pairs=len(pairs),median_us={k:v['median_us'] for k,v in arms.items()},median_time_change_percent=delta)))
    raise SystemExit(0 if exact else 1)


if __name__ == '__main__':
    main()
