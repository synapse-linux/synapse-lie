#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the complete SSM projection/convolution timings separately from model PP."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / 'config/q2-ssm-channel-bounds-component-results.json').read_text())
    rows = report['timings']
    if report['model_inference'] or not report['device_work_safe'] or len(rows) != 14:
        raise ValueError('Expected complete safe component timings, including numerical rejections')
    output = ROOT / 'docs/figures/q2-ssm-channel-bounds-component'
    if any(output.with_suffix(s).exists() for s in ('.csv', '.svg', '.png')):
        raise ValueError('Refusing to overwrite component exports')
    with output.with_suffix('.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    for index, candidate in enumerate((False, True)):
        samples = [row for row in rows if row['candidate'] == candidate]
        name = 'candidate' if candidate else 'reference'
        median = report['summaries'][0][name]['median']
        ax.bar(index, median, color='#c4844e' if candidate else '#379878')
        warmups = [row['us_per_iteration'] for row in samples if row['warmup']]
        measured = [row['us_per_iteration'] for row in samples if not row['warmup']]
        ax.scatter([index - .03, index + .03], warmups, facecolors='none', edgecolors='black',
                   label='Two warmups' if index == 0 else None, zorder=3)
        ax.scatter([index - .08 + .04 * j for j in range(5)], measured, c='black', s=22,
                   label='Five measured samples' if index == 0 else None, zorder=3)
        ax.annotate(f'{median:.3f}', (index, max(*warmups, *measured)), xytext=(0, 8),
                    textcoords='offset points', ha='center')
    ax.set_xticks([0, 1], ['Literal saved Q2 control', 'SSM channel-predicate candidate'])
    ax.set_ylim(0, max(row['us_per_iteration'] for row in rows) * 1.18)
    ax.set_ylabel('Projection + convolution microseconds; lower is faster')
    ax.set_title('SSM M16384 / N2048 / K2560 complete cycle')
    ax.set_axisbelow(True)
    ax.grid(axis='y', alpha=.2)
    ax.legend(loc='lower left')
    fig.text(.5, .025, 'Three weight rotations per sample, beyond32MiB; alternating order.\n'
             'Component timing only; model throughput and numerical quality are separate.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, 1))
    for suffix in ('.svg', '.png'):
        fig.savefig(output.with_suffix(suffix), dpi=150)
    svg = output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    print(json.dumps(dict(timing_rows=14, output=str(output))))


if __name__ == '__main__':
    main()
