#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot the measured HC scheduling probes against their shared fresh control."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wave4_report', type=Path)
    parser.add_argument('k4_report', type=Path)
    parser.add_argument('wide_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    reports = [json.loads(path.read_text())['micro'] for path in
               (args.wave4_report, args.k4_report, args.wide_report)]
    if any(report['reference'] != reports[0]['reference'] for report in reports):
        raise ValueError('The candidates require the same measured reference')
    if any(report['changed_full_output_hashes'] for report in reports):
        raise ValueError('This chart requires unchanged complete output hashes')
    arms = [('64x128\nreference', reports[0]['reference'])] + list(zip(
        ['64x64\n4 row waves', '64x64\n4 K blocks', '64x128\n4 row waves'],
        [report['candidate'] for report in reports]))
    if any(arm['numerical_failures'] != 4 or arm['command_exit'] != 1 for _, arm in arms):
        raise ValueError('The chart annotation requires four retained numerical failures')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    rows = []
    for ax, shape, title in zip(axes, ['320x10240', '10240x320'],
                                ['Changed HC down path', 'Unchanged HC up control']):
        medians = [arm['shapes'][shape]['us_per_launch']['median'] / 1000 for _, arm in arms]
        bars = ax.bar([label for label, _ in arms], medians,
                      color=['#376fbd', '#cf7738', '#49895d', '#9768a7'])
        ax.bar_label(bars, labels=[f'{v:.3f}' for v in medians], padding=5)
        maximum = max(medians)
        for x, (label, arm) in enumerate(arms):
            samples = arm['shapes'][shape]['us_per_launch']['samples']
            values = [value / 1000 for value in samples]
            maximum = max(maximum, max(values))
            ax.scatter([x + (i - 2) * .045 for i in range(len(values))], values,
                       color='#222222', zorder=3, s=15)
            rows.extend(dict(arm=label.replace('\n', ' '), source=arm['path'], shape=shape,
                             rep=i, us_per_launch=value) for i, value in enumerate(samples))
        ax.set_title(title)
        ax.set_ylabel('Milliseconds per launch (lower is better)')
        ax.set_ylim(0, maximum * 1.17)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('HC down scheduling on .157 — synthetic F16 matrices')
    fig.text(.5, .02, 'Medians and all five batched samples; 16 launches across 100 MiB of weights per sample.\n'
             'Sequential arms. All 22 complete output hashes agree; every arm retains four\n'
             'unchanged-library numerical failures and exit 1. No complete-model throughput claim.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .16, 1, .92))
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
