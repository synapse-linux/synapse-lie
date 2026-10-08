#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export observed tail occupancy; this chart contains no performance estimate."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/q2-current-routing-v2-preparation/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    report = json.loads((ROOT/'config/q2-current-routing-v2-results.json').read_text())
    data = report['summaries']['tail64_live_rows']
    rows = [dict(live_rows=f'{1+16*i}-{16*(i+1)}', tiles=data['live16_fragments'][str(i+1)],
                 percent=100*data['live16_fragments'][str(i+1)]/data['tiles']) for i in range(4)]
    base = ROOT/'docs/figures/q2-current-routing'
    base.parent.mkdir(exist_ok=True)
    with base.with_suffix('.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout='constrained')
    bars = ax.bar([r['live_rows'] for r in rows], [r['percent'] for r in rows],
                  color=['#246a95', '#799caf', '#799caf', '#799caf'], width=.65)
    ax.bar_label(bars, [f"{r['percent']:.1f}%\n{r['tiles']:,} tiles" for r in rows], padding=4)
    ax.set(ylim=(0, 85), xlabel='Live rows in each 64-row tail tile', ylabel='Share of tail tiles (%)',
           title='Fixed2048 routing: 70.7% of tails need at most 16 rows')
    ax.spines[['top', 'right']].set_visible(False)
    ax.text(.5, -.22, 'Saved1585 executable · 48 layers · 12,753 tail tiles\n'
            'Observed routing distribution; no measured speedup or occupancy claim.',
            ha='center', va='top', transform=ax.transAxes, fontsize=9)
    for suffix in ('svg', 'png'):
        fig.savefig(base.with_suffix('.'+suffix), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(json.dumps(dict(files=[str(base.with_suffix('.'+s).relative_to(ROOT)) for s in ('csv','svg','png')],
                          headline_eligible=False)))


if __name__ == '__main__':
    main()
