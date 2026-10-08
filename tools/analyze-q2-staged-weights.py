#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify staged-Q2 operators and matched original-shape synthetic timings."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


def read(directory):
    root = directory / 'results'
    receipt = json.loads((root / 'result.json').read_text())
    if not receipt.get('finished_at') or any(c.get('exit_code') != 0 for c in receipt['commands']):
        raise ValueError('Unfinished or failed arm: ' + str(directory))
    if receipt.get('postflight_kfd') != [] or receipt.get('model_access'):
        raise ValueError('Unexpected component scope or live GPU client')
    if receipt.get('binary_sha256') != receipt.get('binary_sha256_after'):
        raise ValueError('Binary identity changed')
    for name, meta in receipt['artifacts'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe artifact path')
        payload = (root / name).read_bytes()
        if len(payload) != meta['bytes'] or hashlib.sha256(payload).hexdigest() != meta['sha256']:
            raise ValueError('Artifact identity changed')
    log = '\n'.join(p.read_text() for p in sorted(root.glob('*.log')))
    return root, receipt, log


def micro(directory):
    root, receipt, log = read(directory)
    if receipt['state'] != 'SYNTHETIC_Q2_PACKED_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT':
        raise ValueError('Incorrect component state')
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{"event":')]
    geometry = [e for e in events if e['event'] == 'geometry']
    replay = [e for e in events if e['event'] == 'replay']
    samples = [e for e in events if e['event'] == 'microbench']
    if len(geometry) != 1 or len(replay) != 1 or len(samples) != 10:
        raise ValueError('Incomplete benchmark events')
    geometry, replay = geometry[0], replay[0]
    expected = dict(tokens=2048, experts=512, used=10, rows=2560,
                    logical_k=640, stored_k=768, tile=48, tiles=512,
                    weight_bytes=330301440)
    if any(geometry[k] != v for k, v in expected.items()):
        raise ValueError('Unexpected matrix geometry')
    if (replay['values'] != 52428800 or not replay['exact'] or
            replay['raw_sha256'] != replay['packed_sha256'] or
            replay['independent_samples'] != 1024):
        raise ValueError('Complete output replay failed')
    rows = [json.loads(line) for line in (root / 'packed-bench-samples.jsonl').read_text().splitlines()]
    if len(rows) != 1024:
        raise ValueError('Incomplete independent dot products')
    error2 = norm2 = peak = maximum = 0.0
    for row in rows:
        value, reference = row['value'], row['reference']
        if not math.isfinite(value) or not math.isfinite(reference):
            raise ValueError('Non-finite dot product')
        delta = value - reference
        error2 += delta * delta
        norm2 += reference * reference
        maximum = max(maximum, abs(delta))
        peak = max(peak, abs(reference))
    metrics = dict(relative_rms=math.sqrt(error2 / max(norm2, 1e-30)),
                   error_over_peak=maximum / max(peak, 1e-20))
    if any(v > .002 or not math.isclose(v, replay[k], rel_tol=1e-9, abs_tol=1e-15)
           for k, v in metrics.items()):
        raise ValueError('Independent error metric failed')
    if {(s['rep'], s['packed']) for s in samples} != {(i, p) for i in range(5) for p in (False, True)}:
        raise ValueError('Incomplete alternating timing coverage')
    for sample in samples:
        if (sample['launches'] != 8 or sample['position'] != (int(sample['packed']) ^ (sample['rep'] & 1)) or
                not math.isfinite(sample['us_per_launch']) or sample['us_per_launch'] <= 0):
            raise ValueError('Unexpected timing scope')
    medians = {('packed' if p else 'raw'): statistics.median(
        s['us_per_launch'] for s in samples if s['packed'] == p) for p in (False, True)}
    return dict(path=str(directory), geometry=geometry, replay=replay,
                independently_recomputed_metrics=metrics, samples=samples,
                median_us=medians, command_exits=[c['exit_code'] for c in receipt['commands']],
                verified_artifacts=len(receipt['artifacts']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operators', type=Path, required=True)
    parser.add_argument('--retained-operators', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    current, receipt, log = read(args.operators)
    retained, _, _ = read(args.retained_operators)
    names = sorted(p.name for p in current.iterdir() if p.suffix in ('.f32', '.u32'))
    if len(names) != 62 or names != sorted(p.name for p in retained.iterdir() if p.suffix in ('.f32', '.u32')):
        raise ValueError('Unexpected operator buffer inventory')
    comparisons = [dict(name=n, bytes=(current / n).stat().st_size,
                         exact=(current / n).read_bytes() == (retained / n).read_bytes()) for n in names]
    metrics = re.findall(r'^((?:Q2 routed|IQ2-pair-).*?) rrms=([\deE.+-]+) scaled_max=([\deE.+-]+)$', log, re.M)
    if len(metrics) != 30 or any(not (0 <= float(a) <= .002 and 0 <= float(b) <= .002) for _, a, b in metrics):
        raise ValueError('Independent operator checks incomplete or failed')
    reference, candidate = micro(args.reference), micro(args.candidate)
    if reference['geometry'] != candidate['geometry']:
        raise ValueError('Different benchmark inputs')
    exact = all(r['exact'] for r in comparisons) and reference['replay'] == candidate['replay']
    change = {key: 100 * (candidate['median_us'][key] / reference['median_us'][key] - 1)
              for key in ('raw', 'packed')}
    report = dict(scope='Original-shape synthetic Q2 down operator on .157; not complete model throughput or UD parity',
                  promotion=False, exact=exact, reference=reference, candidate=candidate,
                  time_change_percent=change,
                  operators=dict(independent_cases=len(metrics), comparisons=comparisons,
                                 max_rrms=max(float(a) for _, a, _ in metrics),
                                 max_scaled_error=max(float(b) for _, _, b in metrics),
                                 command_exits=[c['exit_code'] for c in receipt['commands']],
                                 verified_artifacts=len(receipt['artifacts'])))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('exact', 'time_change_percent')}, indent=2))
    return not exact


if __name__ == '__main__':
    raise SystemExit(main())
