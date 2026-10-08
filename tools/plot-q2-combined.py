#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all cumulative Q2 model samples, including prefill/decode durations."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    report = json.loads((ROOT / 'config/q2-combined-results.json').read_text())
    output = ROOT / 'docs/figures/q2-combined'
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    names = ('reference', 'retained', 'scaled_control', 'scaled', 'ud')
    labels = ('Q2 cumulative\nreference', 'Q2 combined\nretained', 'Q2 scaled\ncontrol',
              'Q2 combined\nscaled', 'UD')
    colors = ('#4477aa', '#228833', '#ccbb44', '#ee9933', '#884488')
    rows = []
    for ax, metric, title, unit in zip(axes.flat,
            ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s'),
            ('Prefill throughput', 'Decode throughput', '2048-token prefill', '127 decode calls'),
            ('Tokens/s', 'Forward calls/s', 'Seconds', 'Seconds')):
        for i, (name, color) in enumerate(zip(names, colors)):
            data = report['model'][name]['measurements'][metric]
            ax.bar(i, data['median'], color=color, width=.65)
            ax.scatter([i + (j-1)*.07 for j in range(3)], data['samples'], color='#222222', s=22)
            ax.annotate(f"{data['median']:.3f}", (i, data['max']), xytext=(0, 7),
                        textcoords='offset points', ha='center', fontsize=9)
            rows.extend(dict(arm=name, metric=metric, repetition=j+1, value=value)
                        for j, value in enumerate(data['samples']))
        ax.set_xticks(range(len(names)), labels, fontsize=9)
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.set_ylim(0, max(report['model'][n]['measurements'][metric]['max'] for n in names)*1.2)
        ax.yaxis.grid(True, alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('Cumulative Q2 / UD: complete-model measurements on .157')
    fig.text(.5, .015, 'C1, 2048 input / 128 output, 1 warmup + 3 samples; 15s idle excluded. '
             'Fan82; scaled numerical rejection retained.\nSingle-chunk native inference: '
             'multi-chunk C17 PLE overlap is measured separately.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .955))
    for suffix in ('.svg', '.png'):
        fig.savefig(output.with_suffix(suffix), dpi=160)
    svg = output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
