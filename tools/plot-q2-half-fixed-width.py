#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export every new model sample beside the unchanged saved Q2/UD controls."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / 'config/q2-half-fixed-width-model-results.json').read_text())
    if report['controls_rerun'] or report['component_rerun'] or not report['original_tester_unchanged']:
        raise ValueError('Expected one new model with saved comparisons')
    arms = {key: report['references'][key] for key in ('fixed_q2', 'best_parent')}
    arms['half_fixed_width'] = report['model']
    arms['fixed_ud'] = report['references']['fixed_ud']
    labels = {'fixed_q2': 'Fixed Q2', 'best_parent': 'Saved Q2\neight-value consumer',
              'half_fixed_width': 'New Q2\nfixed integer width', 'fixed_ud': 'Fixed UD'}
    output = ROOT / 'docs/figures/q2-half-fixed-width-model-wrapped'
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
    fig.suptitle('Q2 fixed-width expert consumer: one new fixed model on .157')
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
    component = json.loads((ROOT/'config/q2-half-fixed-width-component-results.json').read_text())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.7))
    for ax, group in zip(axes, component['summaries']):
        for x, key, color in ((0, 'reference', '#379878'), (1, 'candidate', '#c4844e')):
            values = group[key]['samples']
            ax.bar(x, group[key]['median'], color=color)
            ax.scatter([x-.08,x-.04,x,x+.04,x+.08], values, color='black', s=18, zorder=3)
            warms = [t['us_per_iteration'] for t in component['timings']
                     if t['case']==group['case'] and t['candidate']==(key=='candidate') and t['warmup']]
            ax.scatter([x-.04,x+.04], warms, facecolors='none', edgecolors='black', s=25,zorder=3)
        ax.set_xticks([0,1], ['Dynamic integer width','Fixed integer width'])
        ax.set_title(f"{group['used']} experts: {group['candidate_time_change_percent']:+.2f}% time")
        ax.set_ylabel('Complete consumer microseconds (lower is faster)')
        ax.set_ylim(bottom=0)
        ax.set_axisbelow(True); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Ordered half-input MoE + HC + deferred norm, 2048 tokens')
    fig.text(.5,.025,'Two warmups (open) and five measured samples (filled); alternating arms, three rotated input sets.\n'
             'Synthetic component timing; input upload and residual reset excluded equally.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.10,1,.94))
    component_output=ROOT/'docs/figures/q2-half-fixed-width-component'
    for suffix in ('.svg','.png'):
        if component_output.with_suffix(suffix).exists():raise ValueError('Refusing to overwrite component figure')
        fig.savefig(component_output.with_suffix(suffix),dpi=150)
    svg=component_output.with_suffix('.svg');lines=svg.read_text().splitlines()
    lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    print(json.dumps(dict(new_samples=4, saved_samples=12, output=str(output))))


if __name__ == '__main__':
    main()
