#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export every new model sample beside the unchanged saved Q2/UD controls."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / 'config/q2-down-half-vector-model-results.json').read_text())
    if report['controls_rerun'] or report['component_rerun'] or not report['original_tester_unchanged']:
        raise ValueError('Expected one new model with saved comparisons')
    arms = {key: report['references'][key] for key in ('fixed_q2', 'best_parent')}
    arms['down_half_vector'] = report['model']
    arms['fixed_ud'] = report['references']['fixed_ud']
    labels = {'fixed_q2': 'Fixed Q2', 'best_parent': 'Saved Q2\nhalf pairs',
              'down_half_vector': 'New Q2 down\neight-half stores', 'fixed_ud': 'Fixed UD'}
    output = ROOT / 'docs/figures/q2-down-half-vector-model-wrapped'
    if any(output.with_suffix(suffix).exists() for suffix in ('.csv', '.svg', '.png')):
        raise ValueError('Refusing to overwrite model exports')
    rows = [dict(candidate=key, historical=key in ('fixed_q2', 'best_parent', 'fixed_ud'), source=Path(arm['path']).name,
                 **{field: sample[field] for field in ('rep', 'warmup', 'prompt_tokens', 'output_tokens',
                     'decode_steps', 'prefill_s', 'decode_s', 'prefill_tok_s', 'decode_steps_s')})
            for key, arm in arms.items() for sample in arm['samples']]
    if len(rows) != 16:
        raise ValueError('Expected four new and twelve saved samples')
    with output.with_suffix('.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, metric, title in zip(axes, ('prefill_tok_s', 'decode_steps_s'), ('Prefill tokens/s', 'Decode forward calls/s')):
        values = [arm['measurements'][metric]['median'] for arm in arms.values()]
        ax.bar([labels[key] for key in arms], values, color=['#748fb5', '#379878', '#c4844e', '#5b6477'])
        for x, (key, arm) in enumerate(arms.items()):
            samples = arm['samples']
            warmup = [sample[metric] for sample in samples if sample['warmup']]
            measured = [sample[metric] for sample in samples if not sample['warmup']]
            ax.scatter([x], warmup, facecolors='none', edgecolors='black', s=34,
                       label='One warmup' if x == 0 else None, zorder=4)
            ax.scatter([x - .06, x, x + .06], measured, c='black', s=25,
                       label='Three measured sessions' if x == 0 else None, zorder=4)
            ax.annotate(f'{values[x]:.3f}', (x, max(*warmup, *measured)), xytext=(0, 8),
                        textcoords='offset points', ha='center')
        ax.set_ylim(0, max(sample[metric] for arm in arms.values() for sample in arm['samples']) * 1.17)
        ax.set_title(title)
        ax.set_ylabel('Higher is faster')
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
        ax.legend(loc='lower left', fontsize=8)
    fig.suptitle('Q2 aligned eight-half output stores: one new fixed model on .157')
    fig.text(.5, .025, 'Original exact2048 input and timers; capacity9216,chunk2048,tg128,127 timed decode calls.\n'
             'All four new and twelve saved samples shown. Saved controls are reused; inherited F16 rounding requires separate quality evidence.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .10, 1, .95))
    for suffix in ('.svg', '.png'):
        fig.savefig(output.with_suffix(suffix), dpi=150)
    svg = output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    print(json.dumps(dict(new_samples=4, saved_samples=12, output=str(output))))


if __name__ == '__main__':
    main()
