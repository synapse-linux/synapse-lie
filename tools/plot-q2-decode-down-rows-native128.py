#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all retained original128K HC observations, with both saved comparators."""

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    result = json.loads((ROOT / 'config/q2-decode-down-rows-native128-results.json').read_text())
    arms = [('Saved reference\nRelWithDebInfo', result['saved_unprofiled']),
            ('Retained scalar HC\nIsolated up/mix', result['saved_isolated_up_mix']),
            ('New Q2 down\nFour rows per wave', result['new'])]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for axis, key, title, target in zip(axes, ('prefill_tps', 'decode_tps'),
                                      ('Full cold prefill', 'Decode: eight calls'), (1500, 30)):
        values = [item[key] for _, item in arms]
        axis.bar(range(len(arms)), values, color=['#3b82f6', '#15996f', '#e8a242'], width=.55)
        for i, value in enumerate(values):
            axis.text(i, value + target*.025, f'{value:.2f}', ha='center')
        axis.axhline(target, color='#9b3747', linestyle='--', linewidth=1,
                     label=f'Target: {target} tokens/s')
        axis.set_xticks(range(len(arms)), [label for label, _ in arms])
        axis.set_ylim(0, max(target, *values)*1.16)
        axis.set_ylabel('tokens/s')
        axis.set_title(title)
        axis.grid(axis='y', alpha=.2)
        axis.set_axisbelow(True)
        axis.legend(loc='upper center', fontsize=8)
    fig.suptitle('Q2 original 128K input: prefill and decode')
    fig.text(.5, .085, '130,925 physical input tokens; capacity 133,760; chunks 2,048; '
             'zero cached tokens; same four-request sequence.', ha='center', fontsize=9)
    fig.text(.5, .045, 'One observation per executable; saved control reused. Reply equality is recorded in the result. '
             'Inherited task quality and sustained TG128 remain open.', ha='center', fontsize=9)
    fig.text(.5, .012, 'No new quantization; component rounding differences and original-model task quality remain open.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .14, 1, .94))
    for extension in ('png', 'svg'):
        path = ROOT / ('docs/figures/q2-decode-down-rows-native128.' + extension)
        if path.exists():
            raise ValueError('Preserve existing plot')
        fig.savefig(path, dpi=160)
        if extension == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    path = ROOT / 'docs/figures/q2-decode-down-rows-native128.csv'
    with path.open('x') as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(('arm', 'prefill_tps', 'decode_tps', 'prefill_ms', 'decode_ms'))
        for label, values in arms:
            writer.writerow((label.replace('\n', ' '), *(values[k] for k in
                             ('prefill_tps', 'decode_tps', 'prefill_ms', 'decode_ms'))))
    print('Saved native128K PNG, SVG and exact-value CSV; no GPU operation.')


if __name__ == '__main__':
    main()
