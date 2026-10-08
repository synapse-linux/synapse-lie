#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot every algorithm and sample from a validated HC library screen."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.report.read_text())
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    rows = []
    for ax, shape in zip(axes, data['shapes'].values()):
        arms = shape['arms']
        labels = [('Native before' if i == 0 else 'Native after') if arm['algorithm'] == -1
                  else f"Library {arm['algorithm']}" for i, arm in enumerate(arms)]
        medians = [arm['timing_us']['median'] for arm in arms]
        colors = ['#376fbd' if arm['algorithm'] == -1 else '#49895d' if arm['checks_pass']
                  else '#ce8339' for arm in arms]
        bars = ax.barh(labels, medians, color=colors)
        ax.bar_label(bars, labels=[f'{v:.1f}' for v in medians], padding=5, fontsize=9)
        for i, arm in enumerate(arms):
            samples = arm['timing_us']['samples']
            ax.scatter(samples, [i + (j - 2) * .055 for j in range(5)], s=10, c='#222222', zorder=3)
            for rep, value in enumerate(samples):
                rows.append(dict(m=shape['m'], k=shape['k'], n=shape['n'], arm=arm['arm'],
                    algorithm=arm['algorithm'], workspace_bytes=arm['workspace_bytes'],
                    fp64_ok=arm['numeric_ok'], position_ok=arm['row_invariance']['inconsistent_values'] == 0,
                    repetition=rep + 1, us_per_launch=value))
        ax.invert_yaxis()
        ax.set_xlim(0, max(max(arm['timing_us']['samples']) for arm in arms) * 1.16)
        ax.grid(axis='x', alpha=.2)
        ax.set_axisbelow(True)
        ax.set_xlabel('Microseconds / launch; lower is faster')
        ax.set_title(f"HC {'down' if shape['m'] == 320 else 'up'}: {shape['m']} × {shape['k']}, n2048")
    fig.suptitle('Original F16 HC: native and hipBLASLt algorithms on .157')
    fig.text(.5, .025, 'Five samples × 16 launches; 100 MiB weight rotation. Blue: native control.\n'
             'Orange: fails FP64 and/or exact position invariance. All supplied algorithms use zero workspace.\n'
             'Synthetic component results; numerical failures retained; no model throughput claim.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .94))
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=150)
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
