#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export corrected Q2/UD model samples with the original UD baseline visible."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / 'config/q2-decode-baseline-results.json').read_text())
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    rows = []
    for i, scope in enumerate(('pp2048', 'historical2042')):
        for j, metric in enumerate(('prefill_tok_s', 'decode_steps_s')):
            ax = axes[i, j]
            medians, samples = [], []
            for name in ('q2', 'ud'):
                data = report['model'][name]['scopes'][scope]
                medians.append(data['measurements'][metric]['median'])
                values = [e[metric] for e in data['samples'] if not e['warmup']]
                samples.append(values)
            ax.barh(['Q2', 'UD'], medians, color=['#cc8844', '#4477aa'])
            ref = 0
            if scope == 'historical2042':
                ref = report['original_ud_baseline']['prefill_tps' if j == 0 else 'decode_tps']['median']
            for arm, values in enumerate(samples):
                ax.scatter(values, [arm+(r-1)*.10 for r in range(3)], color='#222222', s=18, zorder=3)
                ax.text(max(max(values), ref) + max(medians)*.025, arm,
                        f'{medians[arm]:.3f}', va='center')
            if scope == 'historical2042':
                ax.axvline(ref, color='#555555', linestyle='--', label=f'Original UD: {ref:.3f}')
                ax.legend(loc='lower right', fontsize=8)
            ax.invert_yaxis()
            ax.set_xlim(0, max(medians)*1.23)
            ax.set_xlabel('token/s' if j == 0 else 'completed forward calls/s')
            ax.set_title(('Current 2048-token prompt' if i == 0 else 'Historical 2042-token prompt') + (' — prefill' if j == 0 else ' — decode'))
            ax.grid(axis='x', alpha=.2)
            ax.set_axisbelow(True)
        for name in ('q2', 'ud'):
            for e in report['model'][name]['scopes'][scope]['samples']:
                if e['warmup']:
                    continue
                for metric in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s'):
                    rows.append(dict(scope=scope, arm=name, rep=e['rep'], metric=metric, value=e[metric],
                                     prompt_tokens=e['prompt_tokens'], completed_decode_steps=e['decode_steps']))
    fig.suptitle('Corrected sampling benchmark — original Q2 and UD on .157')
    fig.text(.5, .025, 'Bars: medians; points: all 3 measured samples; one excluded warmup per scope.\n'
             'Current scope: 127 forwards / 128 output tokens. Historical scope: 128 forwards / 128 output tokens.\n'
             'Full finite checks retained inside sampling; original baseline has a different sampler/C ABI boundary.\n'
             'Inherited numerical rejection remains. This is not a GPU-kernel speedup or a parity verdict.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .14, 1, .95))
    dest = ROOT / 'docs/figures/q2-decode-baseline'
    for suffix in ('.svg', '.png'):
        fig.savefig(dest.with_suffix(suffix), dpi=150)
    p = dest.with_suffix('.svg')
    lines = p.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    p.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    with dest.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
