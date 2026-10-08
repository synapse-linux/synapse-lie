#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot every saved Q2 tile timing; export component values, not model rates."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if len(report['runs']) != 1:
        raise ValueError('Plot one complete three-routing run at a time')
    run = report['runs'][0]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.6))
    rows = []
    for ax, case in zip(axes, run['cases']):
        for x, tile in enumerate((48, run['candidate_tile'])):
            data = case['microseconds'][str(tile)]
            ax.bar(x, data['median'] / 1000, width=.65, color=('#386cb0', '#bd6457')[x])
            ax.scatter([x + (i - 2) * .04 for i in range(5)],
                       [v / 1000 for v in data['samples']], color='#252525', s=22)
            ax.annotate(f"{data['median'] / 1000:.3f}", (x, data['max'] / 1000),
                        xytext=(0, 8), textcoords='offset points', ha='center')
            rows.extend(dict(active_experts=case['active_experts'], tile=tile,
                             repetition=i + 1, microseconds=v)
                        for i, v in enumerate(data['samples']))
        ax.set_xticks([0, 1], ['Tile 48', f"Tile {run['candidate_tile']}"])
        ax.set_title(f"{case['active_experts']} active experts\n"
                     f"Candidate time: +{100 * (case['time_ratio'] - 1):.2f}%")
        ax.set_ylabel('GPU component milliseconds')
        ax.set_ylim(0, max(v['max'] for v in case['microseconds'].values()) / 1000 * 1.2)
        ax.yaxis.grid(True, alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('Q2 expert down: larger tiles regress on .157')
    fig.text(.5, .015, '2048 tokens; five alternating pairs, eight launches per sample; exact complete outputs.\n'
             'Active weights exceed 32 MiB in every case. Allocation, transfers and validation excluded.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .10, 1, .94))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=160)
    plt.close(fig)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} component samples")


if __name__ == '__main__':
    main()
