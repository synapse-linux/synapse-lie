#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all four historical counting replay arms, including warmup samples."""
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
    if report['schema'] != 'synapse-lie.q2-counting-regression.v1':
        raise ValueError('Expected audited historical counting replay')
    metrics = [('prefill_tok_s', 'Prefill', 'Tokens / second'),
               ('decode_steps_s', 'Decode (127 timed calls)', 'Calls / second'),
               ('prefill_s', 'Prefill duration', 'Seconds'),
               ('decode_s', 'Decode duration', 'Seconds')]
    labels = dict(legacy='Historical Q2\nreplayed', ordered='Q2 ordered\nIQ2 signs',
                  mixed='Q2 mixed\n128/64 maps', ud='Pristine UD\nreplayed')
    rows = []
    for key, label in labels.items():
        arm = report['model'][key]
        if [s['rep'] for s in arm['samples']] != list(range(4)):
            raise ValueError('Incomplete sample sequence')
        for metric, _, _ in metrics:
            values = [s[metric] for s in arm['samples'] if not s['warmup']]
            measured = arm['measurements'][metric]
            if len(values) != 3 or values != measured['samples'] or sorted(values)[1] != measured['median']:
                raise ValueError('Samples and audited median differ')
        for sample in arm['samples']:
            rows.append(dict(arm=key, source=arm['path'], repetition=sample['rep'],
                warmup=sample['warmup'], prompt_tokens=sample['prompt_tokens'],
                output_tokens=sample['output_tokens'], decode_steps=sample['decode_steps'],
                **{m: sample[m] for m, _, _ in metrics}))
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (metric, title, unit) in zip(axes.flat, metrics):
        medians = [report['model'][k]['measurements'][metric]['median'] for k in labels]
        bars = ax.bar(list(labels.values()), medians, color=['#486fa9', '#389878', '#8b65aa', '#d18b36'])
        decimals = 3 if metric.endswith('_s') and metric in ('prefill_s', 'decode_s') else 2
        ax.bar_label(bars, labels=[f'{v:.{decimals}f}' for v in medians], padding=5)
        maximum = max(medians)
        for x, key in enumerate(labels):
            samples = report['model'][key]['samples']
            values = [s[metric] for s in samples]
            maximum = max(maximum, *values)
            ax.scatter([x-.09], [values[0]], facecolors='none', edgecolors='#222222',
                       s=30, zorder=4, label='Warmup' if x == 0 else None)
            ax.scatter([x-.055, x, x+.055], values[1:], c='#222222', s=17,
                       zorder=4, label='Measured samples' if x == 0 else None)
        old = report['historical']['measurements'][metric]['median']
        ax.axhline(old, color='#486fa9', linestyle='--', linewidth=1,
                   label=f'Previous Q2 median: {old:.{decimals}f}')
        maximum = max(maximum, old)
        ax.set_ylim(0, maximum*1.45)
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper left', fontsize=7)
    fig.suptitle('Historical counting workload on .157 — four complete model replays')
    fig.text(.5, .025, 'Exact original tester: pp2048 / 128 outputs / 127 timed decode calls; C1, MTP off.\n'
             'Bars: median of three measurements; all warmups shown. Sequential arms; 15 s pauses outside timing.\n'
             'This workload is separate from the canonical prose HTTP context curve.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .105, 1, .95))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(arms=len(labels), samples=len(rows), output=str(args.output))))


if __name__ == '__main__':
    main()
