#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all HC cycle samples; keep wall microtimings separate from model rates."""
import csv
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / 'config/q2-hc-inject-reuse-component-results.json').read_text())
    if (result['model_inference'] or result['controls_rerun'] or
            not result['monotonic_cycle_wall_valid'] or not result['device_work_safe']):
        raise ValueError('Expected safe collected component-only wall timings')
    events = [json.loads(line) for line in
        (ROOT / 'evidence' / result['label'] / 'results/03.log').read_text().splitlines()
        if line.startswith('{"event"')]
    timings = [row for row in events if row['event'] == 'hc_reuse_timing']
    if len(timings) != 42:
        raise ValueError('Incomplete cycle timings')
    output = ROOT / 'docs/figures/q2-hc-inject-reuse'
    if any(output.with_suffix(suffix).exists() for suffix in ('.svg', '.png')):
        raise ValueError('Refusing to replace historical exports')
    fields = ('case', 'rep', 'order', 'candidate', 'warmup', 'iterations',
              'rotating_weight_bytes', 'wall_us_per_cycle', 'hip_ms_raw',
              'hip_ms_raw_bits', 'hip_timer_valid')
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: row[k] for k in fields} for row in timings)
    csv_path = output.with_suffix('.csv')
    if csv_path.exists():
        if csv_path.read_text() != stream.getvalue():
            raise ValueError('Existing CSV differs from collected timings')
    else:
        with csv_path.open('x') as saved:
            saved.write(stream.getvalue())
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8))
    for ax, group, label in zip(axes, result['summaries'],
                                ('Raw F16', 'Raw F16 + Q8', 'Deferred norm')):
        for x, arm in enumerate(('reference', 'candidate')):
            median = group[arm]['wall_median_us']
            ax.bar(x, median, color=('#748fb5', '#379878')[x], alpha=.75)
            ax.scatter([x + (i - 2) * .035 for i in range(5)],
                group[arm]['wall_samples_us'], c='black', s=24, zorder=3)
            warm = [r['wall_us_per_cycle'] for r in timings if
                r['case'] == group['case'] and r['candidate'] == bool(x) and r['warmup']]
            ax.scatter([x - .04, x + .04], warm, facecolors='none',
                       edgecolors='black', s=35, zorder=3)
            ax.annotate(f'{median:.3f}', (x, median), xytext=(0, 12),
                        textcoords='offset points', ha='center')
        ax.set_xticks([0, 1], ['Retained cycle', 'HC reuse'])
        ax.set_ylabel('Complete-cycle wall µs; lower is faster')
        ax.set_ylim(0, max(r['wall_us_per_cycle'] for r in timings
                         if r['case'] == group['case']) * 1.17)
        ax.set_title(f"{label}: {group['wall_cycle_time_change_percent']:+.3f}% time")
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('HC input reuse on .157 — component only, n2048')
    fig.text(.5, .025, 'Five alternating measured pairs (solid); two warm pairs (open). '
        'Six weight rotations, 39,321,600 bytes.\nWall includes event submission and terminal sync; '
        'all 42 HIP elapsed values are invalid zero. No model tokens/s measured.',
        ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .12, 1, .95))
    for suffix in ('.svg', '.png'):
        fig.savefig(output.with_suffix(suffix), dpi=150)
    svg = output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    print(json.dumps(dict(component_samples=42, model_samples=0, output=str(output))))


if __name__ == '__main__':
    main()
