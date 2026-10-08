#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Summarize diagnostic PLE counters without treating parallel times as stalls."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median


def read(root):
    root = Path(root)
    receipt = json.loads((root / 'results/result.json').read_text())
    if receipt['state'] != 'PLE_DIAGNOSTIC_COMPLETE_NOT_PERFORMANCE_VERDICT':
        raise ValueError('Incomplete diagnostic: ' + str(root))
    if any(c['exit_code'] for c in receipt['commands']):
        raise ValueError('Failed diagnostic command')
    for name, meta in receipt['artifacts'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe artifact name')
        payload = (root / 'results' / path).read_bytes()
        if len(payload) != meta['bytes'] or hashlib.sha256(payload).hexdigest() != meta['sha256']:
            raise ValueError('Changed artifact: ' + name)
    events = []
    for log in sorted((root / 'results').glob('*.log')):
        for line in log.read_text().splitlines():
            if line.startswith('{'):
                events.append(json.loads(line))
    if sum(e.get('event') == 'complete' for e in events) != 1:
        raise ValueError('No unique completion')
    return events, receipt


def summary(events):
    # Each event's host call sum can overlap GPU work. Pread/decode counters
    # sum concurrent worker wall durations and cannot be added to elapsed time.
    stats = [e['ple'] for e in events]
    io_rows = sum(s['io_rows'] for s in stats)
    hits = sum(s['cache_hits'] for s in stats)
    unique = sum(s['unique_rows'] for s in stats)
    if hits + io_rows != unique:
        raise ValueError('Unaccounted unique rows')
    return dict(samples=len(events),
                elapsed_ms_median=median(e['seconds'] * 1000 for e in events),
                host_call_ms_median=median(sum(s[k] for k in ('hash_ns', 'start_ns', 'wait_ns')) / 1e6 for s in stats),
                hash_ms_median=median(s['hash_ns'] / 1e6 for s in stats),
                start_ms_median=median(s['start_ns'] / 1e6 for s in stats),
                wait_ms_median=median(s['wait_ns'] / 1e6 for s in stats),
                blocked_ms_median=median(s['blocked_ns'] / 1e6 for s in stats),
                copies_ms_median=median(s['copies_ns'] / 1e6 for s in stats),
                row_requests=sum(s['rows'] for s in stats), unique_rows=unique,
                cache_hits=hits, cache_hit_percent=100 * hits / unique if unique else 0,
                io_rows=io_rows, pread_calls=sum(s['pread_calls'] for s in stats),
                returned_mib_per_sample=sum(s['returned_bytes'] for s in stats) / len(stats) / 2**20,
                parallel_pread_ms_sum=sum(s['pread_ns'] for s in stats) / 1e6,
                parallel_decode_ms_sum=sum(s['decode_ns'] for s in stats) / 1e6)


def arm(root):
    events, receipt = read(root)
    output = dict(path=str(root), state=receipt['state'],
                  commands=[c['exit_code'] for c in receipt['commands']],
                  binary_sha256=receipt['binary_sha256'],
                  verified_artifacts=len(receipt['artifacts']),
                  tables=[e for e in events if e['event'] == 'table'],
                  model={}, gathers={}, repeated_frontiers_exact=True)
    for case in ('padding', 'varied'):
        model = [e for e in events if e['event'] == 'forward' and e['case'] == case]
        if len(model) != 4 * 33:
            raise ValueError('Missing full-model observations')
        # Exact repeats are a diagnostic integrity check, not an independent teacher.
        for step in range(-1, 32):
            values = [e for e in model if e['step'] == step]
            if sorted(e['rep'] for e in values) != list(range(4)):
                raise ValueError('Missing or duplicate model replicate')
            if len({e['frontier_sha256'] for e in values}) != 1:
                output['repeated_frontiers_exact'] = False
        output['model'][case] = {}
        for phase in ('prefill', 'decode'):
            selected = [e for e in model if e['phase'] == phase]
            output['model'][case][phase] = {
                'first_owned_cache': summary([e for e in selected if e['rep'] == 0]),
                'repeated_owned_cache': summary([e for e in selected if e['rep'] > 0])}
        output['gathers'][case] = {}
        for length in (2048, 8192):
            rows = [e for e in events if e['event'] == 'gather' and e['case'] == case and e['tokens'] == length]
            if sorted(e['rep'] for e in rows) != list(range(4)) or len({e['embedding_sha256'] for e in rows}) != 1:
                raise ValueError('Gather replicate mismatch')
            output['gathers'][case][str(length)] = {
                'first_owned_cache': summary([e for e in rows if e['rep'] == 0]),
                'repeated_owned_cache': summary([e for e in rows if e['rep'] > 0])}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--q2', type=Path, required=True)
    parser.add_argument('--ud', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = {}
    for case in ('padding', 'varied'):
        name = case + '-input.i32'
        payloads = [(root / 'results' / name).read_bytes() for root in (args.q2, args.ud)]
        if payloads[0] != payloads[1]:
            raise ValueError('Unmatched physical prompt IDs')
        inputs[name] = hashlib.sha256(payloads[0]).hexdigest()
    report = dict(scope='Instrumented diagnostic, not a throughput acceptance result',
                  limits=['Two noninterleaved original-weight model arms; synthetic varied IDs are not natural-language quality evidence.',
                          'Host hash/start/wait durations may overlap GPU work; their sum is not a measured GPU stall.',
                          'Pread/decode counters sum parallel worker wall time; do not add them to forward latency.',
                          'First repetition also includes model/graph warmup. No global cache flush; direct-I/O status is recorded.',
                          'H2D and GPU PLE projections are outside these host counters.'],
                  input_sha256=inputs, q2=arm(args.q2), ud=arm(args.ud))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for name in ('q2', 'ud'):
        for case, phases in report[name]['model'].items():
            for phase, data in phases.items():
                print(name, case, phase, json.dumps(data['repeated_owned_cache']))


if __name__ == '__main__':
    main()
