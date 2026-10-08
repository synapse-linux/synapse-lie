#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot two new exact2048 compositions and three retained historical arms."""
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
    if (report['schema'] != 'synapse-lie.q2-reaudit-composition.v1' or
            report['controls_rerun'] or set(report['model']) != {'exact', 'norm'}):
        raise ValueError('Expected audited candidate-only compositions')
    metrics = [('prefill_tok_s', 'Prefill', 'Tokens / second'),
               ('decode_steps_s', 'Decode (127 timed calls)', 'Calls / second'),
               ('prefill_s', 'Prefill duration', 'Seconds'),
               ('decode_s', 'Decode duration', 'Seconds')]
    labels = dict(fixed_q2='Fixed Q2\nhistorical', retained_q8='Q8 alone\nhistorical',
                  exact='New Q8 + row', norm='New Q8 + row\n+ norm', fixed_ud='Fixed UD\nhistorical')
    arms = dict(report['references'], **report['model'])
    rows = []
    for key in labels:
        arm = arms[key]
        if [s['rep'] for s in arm['samples']] != list(range(4)):
            raise ValueError('Incomplete sample sequence')
        for metric, _, _ in metrics:
            values = [s[metric] for s in arm['samples'] if not s['warmup']]
            measured = arm['measurements'][metric]
            if len(values) != 3 or values != measured['samples'] or sorted(values)[1] != measured['median']:
                raise ValueError('Samples and audited median differ')
        for sample in arm['samples']:
            rows.append(dict(arm=key, historical=key not in report['model'],
                source=arm['path'], repetition=sample['rep'], warmup=sample['warmup'],
                prompt_tokens=sample['prompt_tokens'], output_tokens=sample['output_tokens'],
                decode_steps=sample['decode_steps'], **{m: sample[m] for m, _, _ in metrics}))
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, (metric, title, unit) in zip(axes.flat, metrics):
        medians = [arms[k]['measurements'][metric]['median'] for k in labels]
        ax.bar(list(labels.values()), medians,
               color=['#486fa9', '#74acbb', '#389878', '#9878b5', '#d18b36'])
        decimals = 3 if metric in ('prefill_s', 'decode_s') else 2
        maximum = max(medians)
        for x, key in enumerate(labels):
            values = [s[metric] for s in arms[key]['samples']]
            maximum = max(maximum, *values)
            ax.scatter([x-.09], [values[0]], facecolors='none', edgecolors='#222222',
                       s=30, zorder=4, label='Warmup' if x == 0 else None)
            ax.scatter([x-.055, x, x+.055], values[1:], c='#222222', s=17,
                       zorder=4, label='Measured samples' if x == 0 else None)
            ax.annotate(f'{medians[x]:.{decimals}f}', (x, max(values)),
                        xytext=(0, 6), textcoords='offset points', ha='center', va='bottom')
        for historic, color in (('q2', '#486fa9'), ('ud', '#d18b36')):
            old = report['references']['fixed_'+historic]['measurements'][metric]['median']
            ax.axhline(old, color=color, linestyle='--', linewidth=1,
                       label=f'Fixed {historic.upper()}: {old:.{decimals}f}')
        ax.set_ylim(0, maximum*1.55)
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper left', fontsize=8)
    fig.suptitle('Retained Q2 compositions on .157 — unchanged exact2048 model tester')
    fig.text(.5, .025, 'Original tester: pp2048 / 128 outputs / 127 timed decode calls; C1, MTP off.\n'
             'Bars: three-sample medians; all warmups shown. Only two new compositions run; Q2, Q8-alone and UD evidence is historical.\n'
             'Q8 + row: exact Q2 replay. Norm: changed logits, unchanged tokens. Original numerical rejections retained.',
             ha='center', fontsize=10)
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
