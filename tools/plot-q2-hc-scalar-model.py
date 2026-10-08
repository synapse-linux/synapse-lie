#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot unchanged fixed-point references and all new HC candidate samples."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    result = json.loads((ROOT / 'config/q2-hc-scalar-model-results.json').read_text())
    parent = json.loads((ROOT / 'config/q2-iq2-fixed-bounds-model-results.json').read_text())['model']
    fixed = json.loads((ROOT / 'config/q2-fixed-prefill-reference.json').read_text())['arms']
    arms = [('Original Q2\n(saved)', fixed['mixed']['measurements'], None),
            ('Retained Q2\n(saved)', parent['measurements'], parent['samples']),
            ('HC scalar\n(new)', result['measurements'], result['samples']),
            ('UD\n(saved)', fixed['ud']['measurements'], None)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for axis, key, title in zip(axes, ('prefill_tok_s', 'decode_steps_s'),
                                ('Prefill', 'Decode: 127 timed calls')):
        medians = [a[1][key]['median'] for a in arms]
        axis.bar(range(4), medians, color=['#94a3b8', '#3b82f6', '#16a34a', '#b0a3bd'],
                 alpha=.65, width=.55)
        for i, (_, measurements, samples) in enumerate(arms):
            values = measurements[key]['samples']
            axis.scatter([i-.1, i, i+.1], values, s=22, c='#17212f', zorder=3)
            axis.text(i, medians[i] + max(medians)*.035, f'{medians[i]:.2f}',
                      ha='center', fontsize=10)
            if samples:
                warmup = next(s[key] for s in samples if s['label'] == 'pp2048' and s['warmup'])
                axis.scatter([i], [warmup], s=35, facecolors='none', edgecolors='#17212f', zorder=4)
        axis.set_xticks(range(4), [a[0] for a in arms])
        axis.set_ylabel('tokens/s')
        axis.set_title(title)
        axis.set_ylim(0, max(medians)*1.16)
        axis.grid(axis='y', alpha=.2)
        axis.set_axisbelow(True)
    fig.suptitle('Q2 scalar HC fusion: original fixed 2048 / tg128 comparison')
    fig.text(.5, .075, 'Capacity 9216; chunk 2048; C1 AR; three measured samples per arm. '
             'Bars: original median aggregation; dots: samples.', ha='center', fontsize=9)
    fig.text(.5, .035, 'HC candidate: all 21 parent files exact. Historical controls reused. '
             'No new long-context measurement or inherited task-quality qualification.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .13, 1, .94))
    for ext in ('png', 'svg'):
        path = ROOT / ('docs/figures/q2-hc-scalar-model.' + ext)
        if path.exists():
            raise ValueError('Preserve existing plot')
        fig.savefig(path, dpi=160)
    print('Saved HC model PNG and SVG from verified measurements; no GPU run.')


if __name__ == '__main__':
    main()
