#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify complete scalar HC reduction pairs and keep independent failures visible."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import struct


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


buffers = load_module('analyze-q2-hc-up.py')
END = ' synthetic HC decode reduction; no model inference'


def require(good, message):
    if not good:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory / 'results'
    receipt = json.loads((root / 'result.json').read_text())
    transport = json.loads((args.directory / 'transport.json').read_text())
    collection = json.loads((args.directory / 'collection.json').read_text())
    require(receipt['mode'] == 'hc-decode-reduce-bench' and not receipt['model_access'], 'Wrong component scope')
    exits = [r['exit_code'] for r in receipt['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]), 'Incomplete/failed build or command')
    require(transport['exit_code'] == exits[-1] and transport['source_variant'] == 'hc-decode-reduce', 'Source/transport mismatch')
    require(receipt['binary_sha256'] == receipt['binary_sha256_after'], 'Binary changed')
    require(receipt['locks'] == receipt['postflight_locks'] and
            [(r['device'], r['inode']) for r in receipt['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)], 'Lease mismatch')
    require(not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Unresolved KFD')
    for row in [receipt, *receipt['commands']]:
        require(not any(row.get(k) for k in ('thermal_stop', 'postflight_error', 'timeout',
                    'foreign_kfd', 'lingering_descendants')), 'Process/thermal failure')
    for name, witness in receipt['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
        raw = (root / name).read_bytes()
        require(len(raw) == witness['bytes'] and hashlib.sha256(raw).hexdigest() == witness['sha256'], 'Artifact changed')
    require(collection['verified_artifacts'] == len(receipt['artifacts']), 'Collection mismatch')
    require(hashlib.sha256((args.directory/'results.tar.gz').read_bytes()).hexdigest() == collection['sha256'], 'Archive changed')
    require(hashlib.sha256((args.directory/'source.tar.gz').read_bytes()).hexdigest() == transport['capsule_sha256'], 'Source archive changed')
    log = '\n'.join(p.read_text() for p in sorted(root.glob('*.log')))
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    expected = {(320,10240,1,p) for p in range(3)} | {(320,10240,t,0) for t in (2,3,8,9)} | {
                (319,10240,1,0),(320,10239,1,0),(10240,320,1,0),(512,2560,1,0)}
    independent = [e for e in events if e.get('event') == 'operator']
    require(len(independent) == len(expected), 'Missing independent case')
    independent_ok, names, cases = True, set(), []
    for e in independent:
        match = re.fullmatch(r'(\d+)x(\d+)-t(\d+)-p(\d+)', e['label'])
        require(bool(match), 'Bad case label')
        shape = tuple(map(int, match.groups()))
        require(shape in expected, 'Unknown/duplicate case')
        expected.remove(shape)
        metrics = [e[k] for k in ('relative_rms','error_over_peak','max_abs_error')]
        require(all(math.isfinite(v) and v >= 0 for v in metrics), 'Invalid independent metric')
        passed = metrics[0] <= .00002 and metrics[1] <= .00002
        independent_ok = independent_ok and passed
        cases.append(dict(e, independent_pass=passed))
        name = 'hc-'+e['label']+'.f32'; names.add(name)
        raw = (root/name).read_bytes()
        require(len(raw) == shape[0]*shape[2]*4 and all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',raw)), 'Incomplete independent output')
    comparisons = []
    timing = []
    for event, count, index, prefix in [('reduce_exact',6,'pattern','reduce-p'),
            ('reduce_rotation',16,'matrix','reduce-rotation-'),('reduce_bench',5,'rep','reduce-bench-')]:
        rows = [e for e in events if e.get('event') == event]
        require([e[index] for e in rows] == list(range(count)), 'Missing/duplicate paired case')
        for e in rows:
            stem = prefix+str(e[index])
            pair = [stem+'-'+arm+'.f32' for arm in ('reference','candidate')]
            names.update(pair)
            comparison = buffers.compare_buffer(*[(root/n).read_bytes() for n in pair], 'f', 320)
            require(type(e['exact']) is bool and comparison['exact'] == e['exact'], 'Pair verdict mismatch')
            comparisons.append(dict(event=event, index=e[index], **comparison))
            if event == 'reduce_bench':
                require(e['matrices'] == 16 and e['weight_bytes'] == 104857600 and e['launches'] == 128 and
                        type(e['candidate_first']) is bool and e['candidate_first'] == bool(e['rep'] & 1), 'Timing scope changed')
                require(all(math.isfinite(e[k]) and e[k] > 0 for k in ('reference_us','candidate_us')), 'Invalid timing')
                timing.append(e)
            else:
                require(e['values'] == 320, 'Incomplete paired output')
    require({p.name for p in root.glob('*.f32')} == names and len(names) == 65, 'Unexpected output inventory')
    passed = independent_ok and all(r['exact'] for r in comparisons)
    marker = ('PASS' if passed else 'FAIL') + END
    require([line for line in log.splitlines() if line.endswith(END)] == [marker], 'Fixture completion mismatch')
    require(exits[-1] == (0 if passed else 1) and receipt['state'] ==
            ('SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT' if passed else 'FAILED'), 'Numerical/process verdict mismatch')
    medians = {arm:statistics.median(e[arm+'_us'] for e in timing) for arm in ('reference','candidate')}
    report = dict(scope='Synthetic same-process original/control HC F16 down n1/m320/k10240, no model inference',
        source_capsule_sha256=transport['capsule_sha256'], artifacts_verified=len(receipt['artifacts']),
        command_exits=exits, independent_cases=cases, full_buffer_pairs=comparisons,
        samples=timing, median_us=medians, median_time_change_percent=100*(medians['candidate']/medians['reference']-1),
        numerical_pass=passed, promoted=False, goal_met=False,
        limits='Component timing does not establish complete-model decode speedup, prefill non-regression, or original-Q2 quality.')
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(numerical_pass=passed,full_pairs=len(comparisons),median_us=medians,
                         median_time_change_percent=report['median_time_change_percent'])))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
