#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Separate PP/TG kernel costs using diagnostic-only GPU boundary markers."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3


def summarize(rows):
    kernels = defaultdict(lambda: {'calls': 0, 'total_ns': 0, 'max_ns': 0})
    intervals = []
    for name, start, end in rows:
        if end <= start:
            raise ValueError('Invalid dispatch duration inside measured phase')
        stat = kernels[name]
        stat['calls'] += 1
        stat['total_ns'] += end - start
        stat['max_ns'] = max(stat['max_ns'], end - start)
        intervals.append((start, end))
    if not intervals:
        raise ValueError('Empty marked phase')
    intervals.sort()
    first, last = intervals[0]
    busy = 0
    gaps = []
    for start, end in intervals[1:]:
        if start > last:
            busy += last - first
            gaps.append(start - last)
            first, last = start, end
        else:
            last = max(last, end)
    busy += last - first
    span = last - intervals[0][0]
    total = sum(row['total_ns'] for row in kernels.values())
    top = [{'kernel': name, **stat, 'kernel_time_percent': 100 * stat['total_ns'] / total}
           for name, stat in sorted(kernels.items(), key=lambda pair: pair[1]['total_ns'], reverse=True)]
    return {'dispatches': len(rows), 'kernel_sum_ns': total,
            'gpu_busy_union_ns': busy, 'kernel_span_ns': span,
            'inter_kernel_gap_ns': span - busy,
            'largest_inter_kernel_gaps_ns': sorted(gaps, reverse=True)[:10],
            'kernels': top}


def analyze(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT ks.display_name, kd.start, kd.end
            FROM rocpd_kernel_dispatch kd
            JOIN rocpd_info_kernel_symbol ks ON ks.id = kd.kernel_id
            ORDER BY kd.start''').fetchall()
    result = {'scope': 'Diagnostic kernel trace; not an unprofiled wall benchmark',
              'excluded': 'Loading, semantic smoke, warmup, session allocation and marker kernels',
              'phases': {}}
    for phase in ('Prefill', 'Decode'):
        markers = []
        for boundary in ('Begin', 'End'):
            hits = [row for row in rows if 'Q2Profile' + phase + boundary in row[0]]
            if len(hits) != 1:
                raise ValueError(f'Expected exactly one {phase} {boundary} marker')
            markers.append(hits[0])
        low, high = markers[0][2], markers[1][1]
        if high <= low:
            raise ValueError('Reversed profile markers')
        selected = [row for row in rows if row[1] >= low and row[2] <= high
                    and not row[0].startswith('Q2Profile')]
        result['phases'][phase.lower()] = summarize(selected)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = analyze(args.database)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for name, phase in result['phases'].items():
        print(name, json.dumps({k: v for k, v in phase.items() if k != 'kernels'}))
        for row in phase['kernels'][:12]:
            print(f"{row['total_ns']/1e6:10.3f} ms {row['kernel_time_percent']:6.2f}% "
                  f"{row['calls']:6} calls {row['kernel']}")
