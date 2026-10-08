#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot every HC up component sample and export the plotted values."""
import argparse
import csv
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    report = json.loads(args.report.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    rows = []
    for ax, key, title in zip(axes, ('fused', 'separate_control'),
                              ('Fused HC up and mix', 'Unchanged separate-path control')):
        for x, (arm, label, color) in enumerate((('reference', 'Palette', '#386cb0'),
                                               ('candidate', 'Paired chains', '#36845b'))):
            data = report[arm]['arms'][key]
            ax.bar(x, data['median'], color=color, width=.65)
            ax.scatter([x + (i - 2) * .035 for i in range(5)], data['samples'], color='#252525', s=25)
            ax.annotate(f"{data['median']:.2f}", (x, max(data['samples'])),
                        xytext=(0, 8), textcoords='offset points', ha='center')
            rows.extend(dict(arm=arm, path=report[arm]['path'], component=key,
                             repetition=i + 1, microseconds=value) for i, value in enumerate(data['samples']))
        ax.set_xticks([0, 1], ['Palette', 'Paired chains'])
        ax.set_ylabel('Microseconds per complete path')
        ax.set_title(title)
        ax.set_ylim(bottom=0, top=max(report[a]['arms'][key]['max'] for a in ('reference', 'candidate')) * 1.2)
        ax.yaxis.grid(True, alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('HC up: original arithmetic with larger wave-paired tiles on .157')
    fig.text(.5, .02, '2048 rows; 100 MiB rotating weights; five alternating path pairs per source.\n'
                     'GPU-event component time; allocation, transfers and validation excluded.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .1, 1, .94))
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=160)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
