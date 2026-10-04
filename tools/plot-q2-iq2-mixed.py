#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the retained IQ2 mixed-tile samples and complete-cycle comparison."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT/'config/q2-iq2-mixed-results.json').read_text())
out = ROOT/'docs/figures/q2-iq2-mixed'
out.mkdir(parents=True, exist_ok=True)
with (out/'samples.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['arm','case','scope','sample','warmup',
        'calls','microseconds_per_call','wall_microseconds_per_call'], lineterminator='\n')
    writer.writeheader()
    for arm, data in report['arms'].items():
        for name, case in data['cases'].items():
            for scope, samples in case['scopes'].items():
                for sample in samples['samples']:
                    writer.writerow({key: dict(sample, arm=arm)[key] for key in writer.fieldnames})
matplotlib.rcParams['svg.hashsalt'] = 'q2-iq2-mixed'
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout='constrained', sharey=True)
labels = ['Depth 0 / layer 6', 'Depth 0 / layer 0', 'Depth 128K / layer 16',
          'Depth 128K / layer 6', 'Full 128-row control']
for ax, scope, title in zip(axes, ('resident-map-cycle','map-upload-cycle'),
        ('Map already on GPU', 'Map construction + pinned upload + cycle')):
    values = [row[scope]['time_change_percent'] for row in report['cells'].values()]
    ax.barh(range(5), values, color=['#b34b37' if v > 0 else '#187c87' for v in values], height=.6)
    for i, value in enumerate(values):
        ax.text(value + (.08 if value >= 0 else -.08), i, f'{value:+.2f}%',
                va='center', ha='left' if value >= 0 else 'right', fontsize=10)
    ax.set_yticks(range(5), labels)
    ax.set_xlim(-5.2, 1.1)
    ax.axvline(0, color='#555', lw=.8)
    ax.grid(axis='x', alpha=.2)
    ax.set_xlabel('Median time change (%) — lower is faster')
    ax.set_title(title, fontsize=10)
axes[0].invert_yaxis()
fig.suptitle('IQ2 mixed 128/64 tiles on .157 — complete component cycles\n'
             'Measured routing, synthetic operands; exact outputs; no model throughput claim', fontsize=11)
for suffix in ('svg','png'):
    fig.savefig(out/f'cycles.{suffix}', dpi=160,
                metadata={'Date': None} if suffix == 'svg' else None)
svg = out/'cycles.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
plt.close(fig)
print(out)
