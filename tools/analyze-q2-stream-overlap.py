#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure distinct-stream concurrency from saved rocprof dispatch intervals."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3


def report(path):
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT ks.display_name, kd.stream_id, kd.start, kd.end
            FROM rocpd_kernel_dispatch kd
            JOIN rocpd_info_kernel_symbol ks ON ks.id=kd.kernel_id
            ORDER BY kd.start''').fetchall()
    result = dict(scope='Diagnostic dispatch overlap; not wall benchmark, occupancy or hardware counters',
                  database=str(path), phases={})
    for phase in ('Prefill', 'Decode'):
        begin = [r for r in rows if 'Q2Profile' + phase + 'Begin' in r[0]]
        end = [r for r in rows if 'Q2Profile' + phase + 'End' in r[0]]
        if len(begin) != 1 or len(end) != 1 or end[0][2] <= begin[0][3]:
            raise ValueError('Invalid phase markers')
        low, high = begin[0][3], end[0][2]
        selected = [r for r in rows if low <= r[2] and r[3] <= high
                    and 'Q2Profile' not in r[0]]
        if not selected or any(r[3] <= r[2] for r in selected):
            raise ValueError('Empty/invalid measured phase')
        crossing = [r for r in rows if 'Q2Profile' not in r[0]
                    and r[2] < high and r[3] > low and r not in selected]
        if crossing:
            raise ValueError('Kernel crosses a phase boundary')
        changes = defaultdict(Counter)
        streams = defaultdict(lambda: dict(dispatches=0, kernel_sum_ns=0, kernels=Counter()))
        for name, stream, start, stop in selected:
            changes[start][stream] += 1
            changes[stop][stream] -= 1
            streams[stream]['dispatches'] += 1
            streams[stream]['kernel_sum_ns'] += stop - start
            streams[stream]['kernels'][name] += 1
        active = Counter()
        previous = min(changes)
        histogram = Counter()
        intervals = []
        for at, delta in sorted(changes.items()):
            count = sum(v > 0 for v in active.values())
            histogram[count] += at - previous
            if count > 1 and at > previous:
                intervals.append([previous - low, at - low, count])
            active.update(delta)
            if any(v < 0 for v in active.values()):
                raise ValueError('Unbalanced dispatch endpoints')
            previous = at
        if any(active.values()):
            raise ValueError('Unfinished dispatch')
        span = max(changes) - min(changes)
        kernel_sum = sum(s['kernel_sum_ns'] for s in streams.values())
        busy = sum(v for k, v in histogram.items() if k)
        result['phases'][phase.lower()] = dict(streams=dict(streams), span_ns=span,
            kernel_sum_ns=kernel_sum, union_busy_ns=busy, gaps_ns=histogram[0],
            simultaneous_streams_ns=dict(histogram), overlap_ns=sum(v for k, v in histogram.items() if k > 1),
            kernel_sum_minus_union_ns=kernel_sum-busy, overlap_intervals_relative_ns=intervals,
            dispatches=[dict(kernel=n, stream=s, start_ns=a-low, end_ns=b-low) for n, s, a, b in selected])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = report(args.database)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    for phase, row in data['phases'].items():
        print(phase, json.dumps({k: row[k] for k in ('span_ns', 'kernel_sum_ns', 'union_busy_ns', 'overlap_ns', 'simultaneous_streams_ns')}))
