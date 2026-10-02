#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot the measured half-wave components and their unchanged raw control."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shuffle_report', type=Path)
    parser.add_argument('permute_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    shuffle = json.loads(args.shuffle_report.read_text())
    permute = json.loads(args.permute_report.read_text())
    if shuffle['reference'] != permute['reference']:
        raise ValueError('The candidates require the same measured reference')
    if not shuffle['exact'] or not permute['exact']:
        raise ValueError('This comparison requires passing complete output replay')
    arms = [('Reference', shuffle['reference']),
            ('XOR shuffle', shuffle['candidate']),
            ('Row permute', permute['candidate'])]
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    rows = []
    for ax, packed, key, title in zip(axes, [True, False], ['packed', 'raw'],
                                     ['Changed packed-Q2 path', 'Unchanged raw-input control']):
        medians = [arm['median_us'][key] / 1000 for _, arm in arms]
        bars = ax.bar([name for name, _ in arms], medians,
                      color=['#376fbd', '#cf7738', '#49895d'])
        ax.bar_label(bars, labels=[f'{v:.3f}' for v in medians], padding=5)
        maximum = max(medians)
        for x, (label, arm) in enumerate(arms):
            samples = [r for r in arm['samples'] if r['packed'] == packed]
            values = [r['us_per_launch'] / 1000 for r in samples]
            maximum = max(maximum, max(values))
            ax.scatter([x + (i - 2) * .045 for i in range(len(samples))], values,
                       color='#222222', zorder=3, s=15)
            rows.extend(dict(arm=label, source=arm['path'], path=key, **r) for r in samples)
        ax.set_title(title)
        ax.set_ylabel('Milliseconds per launch (lower is better)')
        ax.set_ylim(0, maximum * 1.17)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Q2 half-wave decoding on .157 — shaped synthetic matrices')
    fig.text(.5, .02, 'Medians and all five batched samples per path; eight launches per sample.\n'
             '315 MiB encoded weights. Paths alternate within each arm; arms run sequentially.\n'
             'GPU component timing only; no complete-model throughput claim.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .15, 1, .91))
    for extension in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(extension), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
