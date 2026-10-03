#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot diagnostic timings without hiding the rejected numerical result."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / 'config/q2-hc-deferred-norm-results.json').read_text())
    if not report['validation_pass'] or report['numerical_qualification_pass'] or report['promoted']:
        raise ValueError('Unexpected qualification status for this rejected experiment')
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax, moe in zip(axes, (False, True)):
        arms = [x for x in report['summaries'] if x['moe'] == moe]
        medians = [x['median_us'] for x in arms]
        bars = ax.bar(['Materialized F32', 'Deferred F32'], medians, color=['#376fbd', '#bd6b37'])
        ax.bar_label(bars, labels=[f'{x:.2f}' for x in medians], padding=5)
        for i, arm in enumerate(arms):
            ax.scatter([i + (j - 2) * .04 for j in range(5)], arm['samples_us'], color='#222222', s=20, zorder=3)
        ax.set_title(('MoE' if moe else 'Ordinary') + f" cycle: {arms[-1]['time_change_percent']:+.2f}% time")
        ax.set_ylabel('Microseconds per complete cycle')
        ax.set_ylim(0, max(x['max_us'] for x in arms) * 1.17)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Deferred HC normalization on .157 — candidate rejected')
    fig.text(.5, .035, '2048 tokens; 5 x 16 cycles; 200 MiB rotating weights.\n'
             'Complete output mismatches; numerical exit 1. Diagnostic timings only.\n'
             'No original-model throughput or reactive speedup measured.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .16, 1, .94))
    output = ROOT / 'docs/figures/q2-hc-deferred-norm'
    for suffix in ('.svg', '.png'):
        fig.savefig(output.with_suffix(suffix), dpi=150)
    svg = output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    rows = [{k: v for k, v in x.items() if k != 'event'} for x in report['events']
            if x['event'] == 'hc_deferred_microbench']
    with output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
