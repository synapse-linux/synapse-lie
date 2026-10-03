#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot reconciled kernel-family costs, preserving all phase values in CSV."""
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
    rows = report['deltas']['prefill']['groups']
    for phase in report['deltas'].values():
        if sum(r['delta_ns'] for r in phase['groups']) != phase['kernel_sum_delta_ns']:
            raise ValueError('Unreconciled timing')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels = dict(explicit_activation_packing='Activation preparation',
                  hc_down_projection='HC down', moe_hc_combine='MoE + HC combine',
                  hc_up_projection='HC up', routed_gate_up='Expert gate/up',
                  hc_mix_epilogues='HC mix epilogues', q8_dense_gemv='Q8 dense GEMV',
                  hc_combine='HC combine', attention_projection='Attention projection',
                  gdn_recurrence_and_epilogues='GDN recurrence / epilogues',
                  causal_attention='Causal attention', routed_down='Expert down',
                  other='Other', other_dense_wmma='Other dense WMMA',
                  gdn_projection_convolution='GDN projection / convolution')
    fig, axes = plt.subplots(1, 2, figsize=(12, 8), gridspec_kw={'width_ratios': [1.5, 1]})
    y = list(range(len(rows)))
    axes[0].barh([v - .18 for v in y], [r['q2_ns'] / 1e6 for r in rows], .35,
                 color='#386faf', label='Q2 scaled + HC library')
    axes[0].barh([v + .18 for v in y], [r['ud_ns'] / 1e6 for r in rows], .35,
                 color='#cc7a36', label='Fresh UD')
    axes[0].set_yticks(y, [labels.get(r['group'], r['group']) for r in rows])
    axes[0].set_title('Prefill kernel time by family')
    axes[0].set_xlabel('Milliseconds')
    axes[0].legend(loc='lower right', fontsize=8)
    delta = [r['delta_ns'] / 1e6 for r in rows]
    bars = axes[1].barh(y, delta, color=['#b14f49' if v > 0 else '#408271' for v in delta])
    axes[1].bar_label(bars, labels=[f'{v:+.2f}' for v in delta], padding=4, fontsize=8)
    axes[1].set_yticks(y, [''] * len(y))
    axes[1].set_xlim(min(delta) - 12, max(delta) + 18)
    axes[1].axvline(0, color='#666', linewidth=.8)
    axes[1].set_title('Q2 minus UD')
    axes[1].set_xlabel('Extra milliseconds (negative: Q2 faster)')
    for ax in axes:
        ax.invert_yaxis()
        ax.set_axisbelow(True)
        ax.grid(axis='x', alpha=.2)
    total = report['deltas']['prefill']['kernel_sum_delta_ns'] / 1e6
    fig.suptitle(f'Composed Q2 / UD diagnostic profile on .157: {total:.2f} ms extra Q2 kernel time')
    fig.text(.5, .02, 'Marked pp2048 / tg16; one sequential diagnostic trace per arm.\n'
             '28/28 saved replay checks exact. Kernel timing is not an unprofiled throughput benchmark.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .96))
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=150)
    p = args.output.with_suffix('.svg')
    lines = p.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    p.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['phase', 'group', 'q2_ns', 'ud_ns', 'q2_calls', 'ud_calls', 'delta_ns'], lineterminator='\n')
        writer.writeheader()
        for phase, data in report['deltas'].items():
            writer.writerows(dict(phase=phase, **row) for row in data['groups'])


if __name__ == '__main__':
    main()
