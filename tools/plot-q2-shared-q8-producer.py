#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot retained producer/shared-expert component times, including both controls."""
import argparse
import csv
import json
import os
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if report['schema'] != 'synapse-lie.q2-shared-q8-producer-r3-results.v1':
        raise ValueError('Expected audited shared Q8 component results')
    samples = report['samples']
    if len(samples) != 90 or report['model_throughput_measured']:
        raise ValueError('Expected ninety component samples, without model rates')
    scopes = ('producer', 'complete')
    labels = ('Reference before', 'Q8 producer', 'Reference after')
    grouped = {}
    for scope in scopes:
        for order, name in enumerate(('before', 'candidate', 'after')):
            rows = [r for r in samples if r['scope'] == scope and r['order'] == order]
            if [r['rep'] for r in rows] != list(range(15)):
                raise ValueError('Incomplete chronological sample sequence')
            values = [r['us_per_cycle'] for r in rows]
            if statistics.median(values) != report['groups'][scope]['median_us'][name]:
                raise ValueError('Audited median differs from samples')
            grouped[scope, order] = values
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))
    for ax, scope in zip(axes, scopes):
        medians = [statistics.median(grouped[scope, order]) for order in range(3)]
        ax.bar(labels, medians, color=('#486fa9', '#389878', '#8b65aa'))
        for order, median in enumerate(medians):
            values = grouped[scope, order]
            ax.scatter([order + (rep-7)*.016 for rep in range(15)], values,
                       s=14, c='#222222', zorder=3)
            ax.annotate(f'{median:.3f}', (order, max(values)), xytext=(0, 6),
                        textcoords='offset points', ha='center', va='bottom')
        ax.set_ylim(0, max(max(grouped[scope, order]) for order in range(3))*1.18)
        ax.set_ylabel('Microseconds / cycle (lower is faster)')
        ax.set_title('Raw HC / Q8 producer' if scope == 'producer' else 'Complete shared-expert cycle')
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('Shared Q8 producer on .157 — synthetic GPU component')
    fig.text(.5, .035, '15 interleaved reference / candidate / reference repetitions; all 90 samples shown.\n'
             '2048 rows; 16 rotating weight sets (191,037,440 bytes). Numerical gate failed.\n'
             'No model prefill/decode rate, quality promotion or context-curve result.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .16, 1, .94))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.png', '.svg'):
        fig.savefig(args.output.with_suffix(suffix), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(samples)
    print(json.dumps(dict(samples=len(samples), output=str(args.output), model_throughput=False)))


if __name__ == '__main__':
    main()
