#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot validated C1 Q2/reference/UD rates, durations and every measured sample."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reference-label', default='Q2 reference')
    parser.add_argument('--candidate-label', default='Q2 candidate')
    parser.add_argument('--title', default='Q2/UD full-model screen on .157')
    args = parser.parse_args()
    model = json.loads(args.report.read_text())['model']
    arms = [(args.reference_label, model['reference']),
            (args.candidate_label, model['candidate'])]
    if 'ud' in model:
        arms.append(('Fresh UD', model['ud']))
    metrics = [('prefill_tok_s', 'Prefill rate', 'Tokens / second'),
               ('decode_steps_s', 'Decode rate', 'Calls / second'),
               ('prefill_s', 'Prefill duration', 'Seconds'),
               ('decode_s', 'Decode duration', 'Seconds')]
    for _, arm in arms:
        for key, _, _ in metrics:
            values = arm['measurements'][key]
            if len(values['samples']) != 3 or sorted(values['samples'])[1] != values['median']:
                raise ValueError('Expected exactly three validated measured samples')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7))
    rows = []
    for ax, (key, title, unit) in zip(axes.flat, metrics):
        medians = [arm['measurements'][key]['median'] for _, arm in arms]
        bars = ax.bar([label for label, _ in arms], medians,
                      color=['#376fbd', '#49895d', '#cf7738'][:len(arms)])
        decimals = 3 if key in ('prefill_s', 'decode_s') else 2
        ax.bar_label(bars, labels=[f'{v:.{decimals}f}' for v in medians], padding=4)
        largest = max(medians)
        for x, (label, arm) in enumerate(arms):
            values = arm['measurements'][key]['samples']
            largest = max(largest, max(values))
            ax.scatter([x + (i - 1) * .055 for i in range(3)], values,
                       color='#222222', s=14, zorder=3)
            rows.extend(dict(arm=label, source=arm['path'], metric=key,
                             repetition=i + 1, value=value)
                        for i, value in enumerate(values))
        ax.set_ylim(0, largest * 1.17)
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle(args.title)
    fig.text(.5, .025, 'C1, pp2048 / tg128 (127 timed decode calls); one warmup + three measured sessions.\n'
             'MTP off; sequential arms; 15-second idle before each request is outside all timers.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .08, 1, .94))
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
