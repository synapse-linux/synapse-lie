#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export every measured sample in the paired-norm/library experiment."""
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
    data = json.loads(args.report.read_text())
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    rows = []

    def panel(ax, title, metric, unit, arms, scope):
        bars = ax.barh([a[0] for a in arms], [a[2] for a in arms],
                       color=['#4477aa', '#cc8844', '#559966'][:len(arms)])
        ax.bar_label(bars, labels=[f'{a[2]:.3f}' for a in arms], padding=5, fontsize=9)
        for i, (name, samples, _) in enumerate(arms):
            for rep, value in enumerate(samples):
                ax.scatter(value, i + (rep - (len(samples) - 1) / 2) * .09,
                           c='#222222', s=15, zorder=3)
                rows.append(dict(scope=scope, arm=name, metric=metric, unit=unit,
                                 measured_repetition=rep + 1, value=value))
        ax.invert_yaxis()
        ax.set_xlim(0, max(max(a[1]) for a in arms) * 1.22)
        ax.set_title(title)
        ax.set_xlabel(unit)
        ax.grid(axis='x', alpha=.2)
        ax.set_axisbelow(True)

    for ax, moe in zip(axes[0, :2], (False, True)):
        arms = []
        for paired in (False, True):
            summary = next(s for s in data['component']['summaries'] if
                           s['moe'] == moe and s['paired'] == paired)
            arms.append(('Paired' if paired else 'Control', summary['samples_us'], summary['median_us']))
        panel(ax, ('MoE' if moe else 'Ordinary') + ' producer + library down',
              'cycle_us', 'microseconds / cycle (lower is faster)', arms,
              'synthetic_moe' if moe else 'synthetic_ordinary')
    for ax, metric, title, unit in zip(
            [axes[0, 2], *axes[1]],
            ['prefill_tok_s', 'prefill_s', 'decode_steps_s', 'decode_s'],
            ['Model prefill rate', 'Model prefill duration', 'Model decode rate', 'Model decode duration'],
            ['token/s (higher is faster)', 'seconds (lower is faster)',
             'decode calls/s (higher is faster)', 'seconds / 127 calls (lower is faster)']):
        arms = []
        for key, label in [('reference', 'Q2 control'), ('candidate', 'Q2 paired'), ('ud', 'UD')]:
            model = data['model'][key]
            samples = [s[metric] for s in model['samples'] if not s['warmup']]
            arms.append((label, samples, model['measurements'][metric]['median']))
        panel(ax, title, metric, unit, arms, 'original_model_c1_pp2048_tg128')
    fig.suptitle('Paired F32/F16 norm with the HC library consumer — .157')
    fig.text(.5, .018, 'Bars: medians; points: every measured sample. Component: 5 × 16 cycles, 100 MiB rotating weights.\n'
             'Original models: C1 pp2048/tg128, one excluded warmup + 3 samples, same fan82 policy.\n'
             'Decode includes legacy harness validation; the historical 26.049 token/s baseline needs matched reproduction.\n'
             'Numerical rejection retained; no task-quality or Q2/UD parity claim.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .95))
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
