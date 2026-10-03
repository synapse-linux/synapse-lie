#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot balanced PLE scheduling samples and measured host callback overlap."""
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
    report = json.loads(args.report.read_text())
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    modes = ['native', 'prepared_serial', 'lookahead']
    labels = ['Native', 'Prepared serial', 'Lookahead']
    colors = ['#4267a9', '#b68930', '#268469']
    fig, (performance, timeline) = plt.subplots(1, 2, figsize=(12, 4.8))
    medians = [report['summary'][m]['prefill_seconds_median'] for m in modes]
    bars = performance.bar(labels, medians, color=colors, alpha=0.8)
    performance.bar_label(bars, labels=[f'{v:.3f}' for v in medians], padding=5)
    for x, mode in enumerate(modes):
        points = [r['seconds'] for r in report['samples'] if r['mode'] == mode and r['rep'] > 0]
        performance.scatter([x - .08, x, x + .08], points, color='#222222', s=18, zorder=3)
    performance.set_ylabel('8K prefill seconds (lower is better)')
    performance.set_title('Median and all three balanced repetitions')
    performance.set_ylim(0, max(r['seconds'] for r in report['samples'] if r['rep'] > 0) * 1.17)
    performance.grid(axis='y', alpha=.2)
    performance.set_axisbelow(True)
    # Select the lookahead repetition closest to its median, never the fastest.
    rep = min((r for r in report['samples'] if r['mode'] == 'lookahead' and r['rep'] > 0),
              key=lambda r: abs(r['seconds'] - medians[2]))['rep']
    intervals = [r for r in report['intervals'] if r['mode'] == 'lookahead' and r['rep'] == rep]
    for event in intervals:
        for y, stage, color in [(1, 'prepare', '#bd6d30'), (0, 'consume', '#376fbd')]:
            start, end = event[stage + '_begin'], event[stage + '_end']
            timeline.broken_barh([(start, end - start)], (y - .2, .4), facecolors=color)
            if stage == 'consume':
                timeline.text((start + end) / 2, y, str(event['chunk'] + 1),
                              ha='center', va='center', color='white')
    timeline.set_yticks([0, 1], ['Forward + drain', 'PLE preparation'])
    timeline.set_xlabel('Seconds since prefill admission')
    timeline.set_ylim(-.6, 1.6)
    timeline.set_title(f'Lookahead host intervals — repetition {rep}')
    timeline.grid(axis='x', alpha=.2)
    fig.suptitle('Original Q2 on .157 — C17 two-buffer PLE lookahead')
    fig.text(.5, .02, 'Synthetic varied 8192-token prompt, chunks 2048; same kernels and cache capacity.\n'
             'First accesses excluded from medians. Callback intervals do not measure GPU occupancy.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .92))
    for extension in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(extension), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w') as file:
        writer = csv.DictWriter(file, fieldnames=list(report['samples'][0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(report['samples'])


if __name__ == '__main__':
    main()
