#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all Q2 weight-staging component samples with the unchanged control."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    report = json.loads(a.report.read_text())
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    csv_rows = []
    for ax, packed, key, title in zip(axes, [True, False], ['packed', 'raw'],
                                     ['Changed packed-Q2 path', 'Unchanged raw-input control']):
        medians = [report[name]['median_us'][key] / 1000 for name in ('reference', 'candidate')]
        bars = ax.bar(['Reference', 'Staged weights'], medians, color=['#376fbd', '#cf7738'])
        ax.bar_label(bars, labels=[f'{v:.3f}' for v in medians], padding=5)
        maximum = max(medians)
        for x, arm in enumerate(('reference', 'candidate')):
            samples = [r for r in report[arm]['samples'] if r['packed'] == packed]
            values = [r['us_per_launch'] / 1000 for r in samples]
            maximum = max(maximum, max(values))
            ax.scatter([x + (i - 2) * .045 for i in range(5)], values,
                       color='#222222', zorder=3, s=15)
            csv_rows.extend(dict(arm=arm, path=key, **r) for r in samples)
        ax.set_title(title)
        ax.set_ylabel('Milliseconds per launch (lower is better)')
        ax.set_ylim(0, maximum * 1.17)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Q2 down projection on .157 — original-shape synthetic matrices')
    fig.text(.5, .02, 'Medians and all five samples; eight launches per sample, alternating input paths.\n'
             '315 MiB encoded weights. No model throughput claim; output checks are outside timing.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .91))
    for extension in ('.svg', '.png'):
        fig.savefig(a.output.with_suffix(extension), dpi=150)
    svg = a.output.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    with a.output.with_suffix('.csv').open('w') as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(csv_rows)


if __name__ == '__main__':
    main()
