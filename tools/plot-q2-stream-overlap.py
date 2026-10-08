#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot saved prefill dispatches and the first bounded shared branch."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.trace.read_text())['phases']['prefill']
    streams = sorted(data['streams'], key=lambda s: data['streams'][s]['dispatches'], reverse=True)
    if len(streams) != 2 or data['streams'][streams[1]]['dispatches'] != 192:
        raise ValueError('Expected the measured two-stream / 48 shared-branch profile')
    rows = data['dispatches']
    branch = [r for r in rows if str(r['stream']) == streams[1]][:4]
    low, high = branch[0]['start_ns'], branch[-1]['end_ns']
    selected = [r for r in rows if r['end_ns'] > low and r['start_ns'] < high]
    left = (low - 150000) / 1e6
    right = (max(r['end_ns'] for r in selected) + 150000) / 1e6
    os.environ.setdefault('MPLCONFIGDIR', str(Path('evidence/.mpl-cache').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.7))
    for axis in axes:
        for i, stream in enumerate(streams):
            intervals = [(r['start_ns']/1e6, (r['end_ns']-r['start_ns'])/1e6)
                         for r in rows if str(r['stream']) == stream]
            axis.broken_barh(intervals, (i-.28, .56), facecolors=['#376fbd', '#49895d'][i])
        axis.set_yticks([0, 1], ['Parent / routed', 'Shared expert'])
        axis.set_xlabel('Milliseconds from prefill begin marker')
        axis.grid(axis='x', alpha=.2)
        axis.set_axisbelow(True)
    axes[0].set_title('Complete prefill dispatch timeline')
    axes[1].set_title('First shared branch and the concurrent parent work')
    axes[1].set_xlim(left, right)
    fig.suptitle(f"Real GPU overlap: {data['overlap_ns']/1e6:.3f} ms on two streams")
    fig.text(.5, .025, 'Diagnostic pp2048/tg16 trace; not the wall benchmark.\n'
             'The unprofiled pp2048/tg128 comparison regresses 1.03% in prefill.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .08, 1, .94))
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    with args.output.with_suffix('.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=['kernel', 'stream', 'start_ns', 'end_ns'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(selected)


if __name__ == '__main__':
    main()
