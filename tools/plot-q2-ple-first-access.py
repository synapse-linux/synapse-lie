#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all balanced PLE observations as CSV and standalone figures."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['svg.hashsalt'] = 'synapse-q2-ple-first-access'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path, help='Output stem for .csv/.svg/.png')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    rows = sorted(report['observations'], key=lambda r: (r['rep'], r['order_position']))
    columns = ['rep', 'mode', 'order_position', 'seconds', 'tokens_per_second',
               'forced_decode_seconds', 'forced_decode_steps_per_second',
               'requested_pages', 'resident_before', 'resident_after', 'resident_before_percent',
               'process_read_bytes', 'read_mib', 'overlap_seconds', 'prepare_ns',
               'consume_ns', 'consumer_wait_ns', 'peak_owned_slots', 'good']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    panels = [(0, 'seconds', 'New input: first position', 'Prefill seconds'),
              (1, 'seconds', 'Same input: replay position', 'Prefill seconds'),
              (0, 'read_mib', 'First-position physical reads', 'Process read MiB'),
              (0, 'resident_before_percent', 'First-position page residency', 'Requested pages resident (%)')]
    colors = {'native': '#3465a4', 'lookahead': '#c45e16'}
    for ax, (position, metric, title, ylabel) in zip(axes.flat, panels):
        for mode in ('native', 'lookahead'):
            samples = [r for r in rows if r['order_position'] == position and r['mode'] == mode]
            ax.scatter([r['rep'] + 1 for r in samples], [r[metric] for r in samples],
                       s=60, label=mode, color=colors[mode], zorder=3)
        ax.set(title=title, ylabel=ylabel, xlabel='Input set', xticks=range(1, 9), xlim=(0.5, 8.5))
        shown = [r[metric] for r in rows if r['order_position'] == position]
        ax.set_ylim(0, max(shown) * 1.25)
        if metric == 'resident_before_percent':
            ax.set_ylim(0, 100)
        ax.grid(axis='y', alpha=0.25)
        ax.legend(loc='best')
    fig.suptitle('Original Q2: 8192-token prefill, native vs C17 PLE lookahead\n'
                 'Different sets, first order ABBAABBA; no page eviction; not controlled cold-cache states',
                 fontsize=13)
    for suffix in ('.svg', '.png'):
        path = args.output.with_suffix(suffix)
        fig.savefig(path, dpi=170, metadata={'Date': None} if suffix == '.svg' else None)
        if suffix == '.svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)
    print(json.dumps(dict(samples=len(rows), verdict=report['verdict'], output=str(args.output))))


if __name__ == '__main__':
    main()
