#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot a validated HC down component comparison and its unchanged up control."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--reference-label', default='Retained Q2')
    p.add_argument('--candidate-label', default='Wider HC down')
    p.add_argument('--title', default='Wider paired-wave HC down on .157')
    args = p.parse_args()
    report = json.loads(args.report.read_text())['micro']
    if report['changed_full_output_hashes']:
        raise ValueError('The chart requires unchanged complete operator outputs')
    arms = [(args.reference_label, report['reference']),
            (args.candidate_label, report['candidate'])]
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    rows = []
    for ax, shape, title in zip(axes, ('320x10240', '10240x320'),
                                ('Changed HC down path', 'Unchanged plain HC up control')):
        medians = [a['shapes'][shape]['us_per_launch']['median'] for _, a in arms]
        bars = ax.bar([label for label, _ in arms], medians, color=['#376fbd', '#49895d'])
        ax.bar_label(bars, labels=[f'{v:.2f}' for v in medians], padding=5)
        maximum = max(medians)
        for x, (label, arm) in enumerate(arms):
            samples = arm['shapes'][shape]['us_per_launch']['samples']
            if len(samples) != 5 or sorted(samples)[2] != medians[x]:
                raise ValueError('Expected five validated samples')
            maximum = max(maximum, max(samples))
            ax.scatter([x + (i - 2) * .04 for i in range(5)], samples, color='#222222', zorder=3, s=20)
            rows.extend(dict(arm=label, source=arm['path'], shape=shape,
                             repetition=i + 1, microseconds=v) for i, v in enumerate(samples))
        ax.set_title(title)
        ax.set_ylabel('Microseconds per launch')
        ax.set_ylim(0, maximum * 1.18)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    verdicts = ', '.join(f"{label}: {arm['numerical_failures']} numerical failures, exit {arm['command_exit']}"
                         for label, arm in arms)
    fig.suptitle(args.title)
    fig.text(.5, .025, '2048 tokens; five samples of 16 launches; 100 MiB rotating weights.\n'
             'Sequential arms; complete operator output hashes agree.\n' + verdicts,
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .15, 1, .94))
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
