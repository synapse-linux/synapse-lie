#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all retained original128K HC observations, including the build confound."""

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
    initial = json.loads((ROOT / 'config/q2-hc-scalar-native128-results.json').read_text())
    matched = json.loads((ROOT / 'config/q2-hc-scalar-native128-matched-results.json').read_text())
    isolated = json.loads((ROOT / 'config/q2-hc-scalar-native128-isolated-results.json').read_text())
    arms = [('Saved reference\nRelWithDebInfo', initial['saved_unprofiled']),
            ('Initial HC\nRelease*', initial['new']),
            ('Matching build\nCombined file', matched['new']),
            ('Isolated HC\nSeparate file', isolated['new'])]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for axis, key, title, target in zip(axes, ('prefill_tps', 'decode_tps'),
                                      ('Full cold prefill', 'Decode: eight calls'), (1500, 30)):
        values = [item[key] for _, item in arms]
        axis.bar(range(len(arms)), values, color=['#3b82f6', '#94a3b8', '#f0ad4e', '#15996f'], width=.55)
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
    fig.text(.5, .045, 'One observation per executable; saved control reused. Exact replies. '
             'Inherited task quality and sustained TG128 remain open.', ha='center', fontsize=9)
    fig.text(.5, .012, '* Initial HC uses a different common build mode. Matching and isolated retain common RelWithDebInfo.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .14, 1, .94))
    for extension in ('png', 'svg'):
        path = ROOT / ('docs/figures/q2-hc-native128-isolated.' + extension)
        if path.exists():
            raise ValueError('Preserve existing plot')
        fig.savefig(path, dpi=160)
        if extension == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    path = ROOT / 'docs/figures/q2-hc-native128-isolated.csv'
    with path.open('x') as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(('arm', 'prefill_tps', 'decode_tps', 'prefill_ms', 'decode_ms'))
        for label, values in arms:
            writer.writerow((label.replace('\n', ' '), *(values[k] for k in
                             ('prefill_tps', 'decode_tps', 'prefill_ms', 'decode_ms'))))
    print('Saved native128K PNG, SVG and exact-value CSV; no GPU operation.')


if __name__ == '__main__':
    main()
