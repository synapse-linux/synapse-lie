#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot row-gather and complete model diagnostics on separate time scales."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--io', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    io, model = [json.loads(path.read_text()) for path in (a.io, a.model)]
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    series = [
        ('Isolated row gather\n12 warmed samples per cache', 'row_gather',
         [io['q2']['capacity'][name]['owned_cache_repeats']['median_ms']
          for name in ('reference', 'candidate')]),
        ('Complete 2K prefill\n3 repeated requests per cache', 'prefill',
         [model[name]['model']['varied']['prefill']['repeated_owned_cache']['elapsed_ms_median']
          for name in ('reference', 'candidate')]),
        ('Complete forced decode step\n96 calls per cache', 'decode',
         [model[name]['model']['varied']['decode']['repeated_owned_cache']['elapsed_ms_median']
          for name in ('reference', 'candidate')])]
    rows = []
    for ax, (title, scope, values) in zip(axes, series):
        bars = ax.bar(['16K rows\n5 MiB', '64K rows\n20 MiB'], values,
                      color=['#376fbd', '#d77630'])
        ax.bar_label(bars, labels=[f'{v:,.2f}' for v in values], padding=4)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel('Median milliseconds')
        ax.set_ylim(0, max(values) * 1.17)
        ax.grid(axis='y', alpha=0.2)
        ax.set_axisbelow(True)
        for name, value in zip(('reference', 'candidate'), values):
            rows.append({'scope': scope, 'cache': name, 'median_ms': value})
    fig.suptitle('Q2 PLE cache capacity on .157 — original embedding bytes', fontsize=14)
    fig.text(0.5, 0.02, 'Synthetic varied inputs; instrumented diagnostics, not throughput acceptance.\n'
             'Independent axis scales. Cache sizes count encoded rows; metadata is additional.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, 0.12, 1, 0.93))
    for ext in ('.svg', '.png'):
        fig.savefig(a.output.with_suffix(ext), dpi=150)
    svg = a.output.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    with a.output.with_suffix('.csv').open('w') as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
