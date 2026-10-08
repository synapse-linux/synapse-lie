#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render audited component samples; no inference and no model-rate claim."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
result = json.loads((root/'config/q2-scaled-row-results.json').read_text())
dest = root/'docs/figures/q2-scaled-row'
dest.mkdir(parents=True, exist_ok=True)
names = list(result['medians'])
labels = ['d0 / L6', 'd0 / L0', 'd128K / L16', 'd128K / L6', 'Full-tile control']
fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
colors = ('#617d98', '#1b9e77', '#b18c56')
for ax, scope, title, unit, divisor in zip(axes, ('pack', 'pack-down'),
        ('Packing only', 'Complete packing + down projection'), ('Microseconds', 'Milliseconds'), (1, 1000)):
    for index, (arm, label, color) in enumerate(zip(result['arms'],
            ('Unchanged before', 'Input reuse', 'Unchanged after'), colors)):
        values = [arm['timing'][name][scope]['median_us'] / divisor for name in names]
        lo = [(arm['timing'][name][scope]['median_us'] - arm['timing'][name][scope]['minimum_us']) / divisor for name in names]
        hi = [(arm['timing'][name][scope]['maximum_us'] - arm['timing'][name][scope]['median_us']) / divisor for name in names]
        ax.bar([i + (index-1)*.25 for i in range(len(names))], values, width=.24,
               color=color, label=label, yerr=[lo, hi], capsize=2)
    ax.set_xticks(range(len(names)), labels, rotation=20, ha='right')
    ax.set_title(title); ax.set_ylabel(unit + ' per call; lower is faster')
    ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
axes[0].legend(loc='lower left', fontsize=8)
fig.suptitle('Q2 scaled-row reuse: synthetic GPU components on .157')
fig.text(.5, .02, 'Labels identify source routing histograms, not model context runs. Median of 5 samples; whiskers are min/max.\n'
         'All three arms retain the same 15 numerical rejections. Complete outputs match across arms.', ha='center', fontsize=9)
fig.tight_layout(rect=(0, .09, 1, .95))
fig.savefig(dest/'components.png', dpi=150)
fig.savefig(dest/'components.svg')
with (dest/'samples.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(('arm', 'routing_case', 'scope', 'sample', 'us_per_call'))
    for arm in result['arms']:
        for name, scopes in arm['timing'].items():
            for scope, values in scopes.items():
                for sample, value in enumerate(values['samples_us'], 2):
                    writer.writerow((arm['label'], name, scope, sample, value))
