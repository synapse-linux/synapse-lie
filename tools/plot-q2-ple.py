#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot completed PLE diagnostics; do not stack host wait on GPU latency."""
import argparse
import csv
import json
from pathlib import Path
import os


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    r = json.loads(args.report.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    rows = []
    labels = ['Padding\nrepeated', 'Varied IDs\nfirst access', 'Varied IDs\nrepeated']
    scenarios = [('padding', 'repeated_owned_cache'), ('varied', 'first_owned_cache'), ('varied', 'repeated_owned_cache')]
    for ai, arm in enumerate(('q2', 'ud')):
        color = ('#376fbd', '#d77630')[ai]
        values = [r[arm]['model'][case]['prefill'][rep] for case, rep in scenarios]
        for case, rep in scenarios:
            row = r[arm]['model'][case]['prefill'][rep]
            rows.append({'arm': arm, 'case': case, 'cache': rep,
                         'prefill_ms': row['elapsed_ms_median'], 'ple_wait_ms': row['blocked_ms_median']})
        for ax, key in zip(axes, ('elapsed_ms_median', 'blocked_ms_median')):
            bars = ax.bar([i + (ai - 0.5) * 0.36 for i in range(3)], [v[key] for v in values],
                          width=0.34, label=arm.upper(), color=color)
            ax.bar_label(bars, labels=[f'{v[key]:,.1f}' for v in values], padding=4, fontsize=9)
            ax.set_xticks(range(3), labels)
            ax.grid(axis='y', alpha=0.2)
            ax.set_axisbelow(True)
            ax.set_ylim(0, max([r[a]['model'][c]['prefill'][s][key]
                               for a in ('q2', 'ud') for c, s in scenarios]) * 1.17)
            ax.set_ylabel('Milliseconds')
    axes[0].set_title('Complete 2,048-token prefill')
    axes[1].set_title('Host wait for PLE rows (may overlap GPU)')
    axes[0].legend(frameon=False)
    fig.suptitle('PLE diagnostics on .157 — unchanged model arithmetic', fontsize=14)
    fig.text(0.5, 0.025, 'Instrumented; first access is one observation, repeats are median of three.\n'
             'Fresh owned row cache does not imply a flushed filesystem. Varied IDs are synthetic.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, 0.12, 1, 0.94))
    for ext in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(ext), dpi=150)
    svg = args.output.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


if __name__ == '__main__':
    main()
