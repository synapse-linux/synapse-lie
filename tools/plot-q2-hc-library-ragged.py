#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all ragged HC samples and separate component/model comparison charts."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/figures'
os.environ.setdefault('MPLCONFIGDIR', str(DEST/'.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def save(fig, stem):
    path = DEST/stem
    fig.savefig(path.with_suffix('.png'), dpi=170)
    fig.savefig(path.with_suffix('.svg'))
    svg = path.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


def component():
    report = json.loads((ROOT/'config/q2-hc-library-ragged-results.json').read_text())
    assert not report['unsupported_shapes'] and len(report['samples']) == 80
    with (DEST/'q2-hc-library-ragged-component.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report['samples'][0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(report['samples'])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    shapes = (502, 2042, 2047, 2048)
    x = np.arange(4)
    width = .35
    for moe, ax in enumerate(axes):
        for name, lib, offset, color in [('Native', False, -width/2, '#62717e'),
                                        ('Library', True, width/2, '#007f8b')]:
            samples = [[e['microseconds_per_iteration']/1000 for e in report['samples']
                        if (e['tokens'], e['moe'], e['library']) == (n, bool(moe), lib)] for n in shapes]
            medians = np.array([np.median(s) for s in samples])
            errors = np.array([medians-np.array([min(s) for s in samples]),
                               np.array([max(s) for s in samples])-medians])
            bars = ax.bar(x+offset, medians, width, color=color, label=name, yerr=errors, capsize=3)
            labels = ax.bar_label(bars, labels=[f'{v:.3f}' for v in medians], padding=5, fontsize=9)
            if lib:
                labels[0].set_y(17)
        ax.set(title='MoE norm + narrowing + HC down' if moe else 'Norm + narrowing + HC down',
               ylabel='milliseconds / complete cycle (lower is faster)', xlabel='Batch rows',
               xticks=x, xticklabels=['502', '2042', '2047', '2048*'])
        ax.set_ylim(0, 8)
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False)
    fig.suptitle('Ragged HC library dispatch: component timing', fontsize=16, fontweight='bold')
    fig.text(.06, .04, '.157 GPU; five alternating pairs, 16 cycles/arm, 100 MiB rotating weights. Bars: median; whiskers: min/max.\n'
             '*2048 is an existing library control. Numerical and row-position checks fail; no model-rate claim.', fontsize=9)
    fig.subplots_adjust(top=.85, bottom=.23, wspace=.22)
    save(fig, 'q2-hc-library-ragged-component')


def model(path):
    report = json.loads(path.read_text())
    targets = ('512', '2048', '8192')
    fields = ('series', 'physical_tokens', 'rep', 'warmup', 'completed_tokens', 'prefill_seconds',
              'decode_seconds', 'prefill_tok_s', 'decode_tok_s', 'prefill_logits_sha256', 'decode_logits_sha256')
    with (DEST/'q2-hc-library-ragged-model.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        count = 0
        for name, group in [*report['model'].items(), ('historical_ud', report['historical'])]:
            for target in targets:
                for sample in group['profiles'][target]['samples']:
                    pp, tg = sample['prefill_ns']/1e9, sample['decode_ns']/1e9
                    writer.writerow(dict(series=name, physical_tokens=sample['prompt_tokens'], rep=sample['rep'],
                        warmup=sample['warmup'], completed_tokens=sample['completed_decode_tokens'],
                        prefill_seconds=pp, decode_seconds=tg, prefill_tok_s=sample['prompt_tokens']/pp,
                        decode_tok_s=sample['completed_decode_tokens']/tg,
                        prefill_logits_sha256=sample['prefill_logits_sha256'], decode_logits_sha256=sample['decode_logits_sha256']))
                    count += 1
        assert count == 48
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
    x = np.arange(3)
    width = .25
    for ax, metric, title in zip(axes, ('prefill_tok_s', 'decode_tok_s'), ('Prefill', 'Completed decode')):
        for name, offset, color, label in [('control', -width, '#62717e', 'Q2 control'),
                                          ('candidate', 0, '#007f8b', 'Q2 ragged'),
                                          ('ud', width, '#d66a28', 'Fresh UD')]:
            profiles = report['model'][name]['profiles']
            medians = np.array([profiles[t]['medians'][metric] for t in targets])
            lows = np.array([min(profiles[t]['rates'][metric]) for t in targets])
            highs = np.array([max(profiles[t]['rates'][metric]) for t in targets])
            bars = ax.bar(x+offset, medians, width, color=color, label=label,
                          yerr=np.array([medians-lows, highs-medians]), capsize=3)
            ax.bar_label(bars, labels=[f'{v:.2f}' for v in medians], padding=6, fontsize=8, rotation=45)
        old = [report['historical']['profiles'][t]['medians'][metric] for t in targets]
        ax.plot(x, old, 'o--', color='#273744', linewidth=1, markersize=4, label='Historical UD')
        ax.set(title=title, ylabel='tokens / second', xlabel='Physical prompt tokens',
               xticks=x, xticklabels=['502', '2042', '8191'])
        ax.set_ylim(0, ax.get_ylim()[1]*1.15)
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .91), ncol=4, frameon=False)
    fig.suptitle('Original C17 diagnostic: ragged HC dispatch', fontsize=16, fontweight='bold')
    fig.text(.06, .035, '.157 GPU; C1 AR, context 9216, chunk 2048, 128 completed decode steps; one warmup + three measured rounds.\n'
             'Bars: medians; whiskers: all measured min/max. Counting workload; not the HTTP depth curve. Numerical rejection remains.', fontsize=9)
    fig.subplots_adjust(top=.79, bottom=.2, wspace=.25)
    save(fig, 'q2-hc-library-ragged-model')


def main():
    DEST.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    component()
    path = ROOT/'config/q2-hc-library-ragged-model-results.json'
    if path.exists():
        model(path)
    print(json.dumps(dict(component_samples=80, model_samples=48 if path.exists() else None)))


if __name__ == '__main__':
    main()
