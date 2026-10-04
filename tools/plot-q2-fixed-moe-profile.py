#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export diagnostic stage costs and complete dispatch summaries; no GPU work."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/q2-fixed-moe-profile-preparation/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    data = json.loads((ROOT/'config/q2-fixed-moe-profile-results.json').read_text())
    destination = ROOT/'docs/figures/q2-fixed-moe-profile-stages'
    names = {
        'dense_q8_f16_activations': 'Q8 weights / F16 activations',
        'dense_q8_quantized_activations': 'Q8 weights / Q8 activations',
        'routed_gate_up_iq2': 'IQ2 expert gate/up', 'routed_down_q2': 'Q2 expert down',
        'hc_norm_combine_inject': 'HC combine / norm / inject',
        'hc_up_mix_f16': 'HC up / mix F16', 'hc_down_f16': 'HC down F16',
        'gdn_ssm': 'GDN / SSM', 'attention_state': 'Attention / state',
        'activation_packing': 'Activation packing', 'other': 'Other',
    }
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.3))
    for axis, phase, title in zip(axes, ('prefill', 'decode'),
                                 ('Prefill: same original 2048 input', 'Decode: diagnostic 15 calls')):
        row = data['phases'][phase]
        stages = list(reversed(row['stages']))
        values = [s['total_ns']/1e6 for s in stages]
        axis.barh([names[s['stage']] for s in stages], values, color='#276996')
        for index, (value, entry) in enumerate(zip(values, stages)):
            axis.text(value + max(values)*.014, index,
                      f'{value:.1f} ms ({entry["kernel_time_percent"]:.1f}%)', va='center', fontsize=8)
        axis.set_xlim(0, max(values)*1.47)
        axis.set_xlabel('GPU kernel duration sum (ms)')
        axis.set_title(title + f'\nGPU busy / kernel span: {100*row["gpu_busy_fraction"]:.2f}%')
        axis.grid(axis='x', alpha=.15)
        axis.set_axisbelow(True)
    fig.suptitle('Saved MoE candidate kernel trace on .157 — diagnostic only', fontsize=13)
    fig.text(.5, .015, 'Installed rocprofv3; saved executable/source/libraries verified; no build or comparator rerun.\n'
             'Loading, smoke, warmup and markers excluded. Unprofiled benchmark remains 1496.830907 PP tokens/s.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .92))
    for suffix in ('.svg', '.png'):
        target = destination.with_suffix(suffix)
        if target.exists():
            raise ValueError('Refusing to overwrite graph')
        fig.savefig(target, dpi=160)
        if suffix == '.svg':
            target.write_text('\n'.join(line.rstrip() for line in target.read_text().splitlines())+'\n')
    plt.close(fig)
    with destination.with_suffix('.csv').open('x', newline='') as stream:
        fields = ('phase', 'stage', 'calls', 'total_ns', 'kernel_time_percent')
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for phase, row in data['phases'].items():
            for item in row['stages']:
                writer.writerow(dict(phase=phase, **item))
    with destination.with_name(destination.name+'-kernels.csv').open('x', newline='') as stream:
        fields = ('phase', 'kernel', 'calls', 'total_ns', 'max_ns', 'kernel_time_percent',
                  'private_bytes_per_work_item', 'shared_bytes_per_work_group', 'work_items_per_group')
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for phase, row in data['phases'].items():
            metadata = {k['kernel']: k for k in row['resources']}
            if len(metadata) != len(row['resources']):
                raise ValueError('Multiple resource shapes for one symbol')
            for item in row['kernels']:
                resource = metadata[item['kernel']]
                if (item['calls'], item['total_ns']) != (resource['calls'], resource['total_ns']):
                    raise ValueError('Resource/timing aggregation differs')
                writer.writerow(dict(phase=phase, **item, **{k:resource[k] for k in fields[-3:]}))
    with destination.with_name(destination.name+'-routing.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data['routing']['layers'][0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(data['routing']['layers'])
    print('Saved diagnostic SVG/PNG and stage/kernel/routing CSV; no performance headline')


if __name__ == '__main__':
    main()
