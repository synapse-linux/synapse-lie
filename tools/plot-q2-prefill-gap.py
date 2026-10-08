#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot the measured GPU prefill gap and isolated HC scheduling candidates."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('token_report', type=Path)
    parser.add_argument('stage_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    reports = [json.loads(path.read_text())['micro']
               for path in (args.token_report, args.stage_report)]
    if reports[0]['reference'] != reports[1]['reference']:
        raise ValueError('Candidates require the same reference')
    if any(report['changed_full_output_hashes'] for report in reports):
        raise ValueError('This chart requires exact complete output replay')
    arms = [('Reference', reports[0]['reference']),
            ('Before token tile', reports[0]['candidate']),
            ('Before K32 stage', reports[1]['candidate'])]
    if any(arm['numerical_failures'] != 4 or arm['command_exit'] != 1
           for _, arm in arms):
        raise ValueError('The annotation requires four retained control failures')
    if not all(arm['exact_replay'] for arm in profile['arms'].values()):
        raise ValueError('Profile outputs differ from their own model controls')
    labels = {'hc_down_projection': 'HC down', 'hc_up_projection': 'HC up',
              'routed_down': 'Expert down', 'routed_gate_up': 'Expert gate/up',
              'explicit_activation_packing': 'Activation packing',
              'q8_dense_gemv': 'Q8 dense GEMV', 'other': 'Other kernels'}
    groups = profile['phase_deltas']['prefill']['groups']
    if sum(row['delta_ns'] for row in groups) != profile['phase_deltas']['prefill']['kernel_sum_delta_ns']:
        raise ValueError('Kernel groups do not reconcile')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8), gridspec_kw={'width_ratios': [1.25, 1]})
    ax = axes[0]
    values = [row['delta_ns'] / 1e6 for row in groups]
    bars = ax.barh([labels[row['group']] for row in groups], values,
                   color=['#c96c42' if value >= 0 else '#4c8569' for value in values])
    ax.bar_label(bars, labels=[f'{value:+.2f}' if value >= 0 else '' for value in values],
                 padding=4, fontsize=9)
    for index, value in enumerate(values):
        if value < 0:
            ax.text(1, index, f'{value:+.2f}', va='center', fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(min(-6, min(values) - 5), max(values) * 1.19)
    ax.set_xlabel('Q2 minus UD GPU kernel time (ms)')
    delta_ms = profile['phase_deltas']['prefill']['kernel_sum_delta_ns'] / 1e6
    ax.set_title(f'Diagnostic prefill gap: {delta_ms:+.2f} ms')
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    ax = axes[1]
    medians = [arm['shapes']['320x10240']['us_per_launch']['median'] / 1000
               for _, arm in arms]
    bars = ax.bar([label.replace('Before ', 'Before\n') for label, _ in arms], medians,
                  color=['#376fbd', '#cf7738', '#9768a7'])
    ax.bar_label(bars, labels=[f'{value:.3f}' for value in medians], padding=5)
    largest = max(medians)
    rows = []
    for x, (label, arm) in enumerate(arms):
        samples = arm['shapes']['320x10240']['us_per_launch']['samples']
        largest = max(largest, max(samples) / 1000)
        ax.scatter([x + (i - 2) * .045 for i in range(len(samples))],
                   [value / 1000 for value in samples], color='#222222', s=15, zorder=3)
        for shape, data in arm['shapes'].items():
            rows.extend(dict(arm=label, source=arm['path'], shape=shape,
                             rep=i, us_per_launch=value)
                        for i, value in enumerate(data['us_per_launch']['samples']))
    ax.set_ylim(0, largest * 1.14)
    ax.set_ylabel('HC down milliseconds per launch')
    ax.set_title('Compiler-boundary component probes')
    ax.grid(axis='y', alpha=.2)
    ax.set_axisbelow(True)
    fig.suptitle('Remaining Q2 prefill costs on .157')
    fig.text(.5, .025,
             'Left: sequential pp2048 traces, recognized kernel families; profiler overhead included.\n'
             'Right: synthetic F16 weights, five samples of 16 launches over 100 MiB; all 22 output hashes agree.\n'
             'Every component arm retains four unchanged-library numerical failures and exit 1. No new model speedup.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .14, 1, .94))
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
    groups_path = args.output.with_name(args.output.name + '-groups').with_suffix('.csv')
    with groups_path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['phase', 'group', 'q2_ns', 'ud_ns', 'delta_ns'],
                                lineterminator='\n')
        writer.writeheader()
        writer.writerows(dict(phase=phase, **row)
                         for phase, data in profile['phase_deltas'].items() for row in data['groups'])


if __name__ == '__main__':
    main()
