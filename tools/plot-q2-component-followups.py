#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot every saved paired sample; requires the existing Matplotlib environment."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
matplotlib.rcParams['svg.hashsalt'] = 'q2-component-followups'


def main():
    for name, shape in [('narrow-vector', (2, 2)), ('scaled-tiles', (2, 3))]:
        report = json.loads((ROOT / 'config' / f'q2-{name}-results.json').read_text())
        fig, axes = plt.subplots(*shape, figsize=(12, 7), layout='constrained')
        cohorts = report['cohorts']
        if name == 'scaled-tiles':
            cohorts = sorted(cohorts, key=lambda c:(c['geometry']['candidate_tile'], -c['geometry']['active_experts']))
        for ax, cohort in zip(axes.flat, cohorts):
            if name == 'narrow-vector':
                title = f"M{cohort['m']} K{cohort['k']}: " + cohort['scope'].replace('_', ' ')
                labels = ['Scalar', 'Vector']
            else:
                g = cohort['geometry']
                title = f"{g['active_experts']} active experts: tile48 vs tile{g['candidate_tile']}"
                labels = ['Tile48', f"Tile{g['candidate_tile']}"]
            for rep in range(5):
                ax.plot([0,1], [cohort[arm]['samples'][rep]/1000 for arm in ('reference','candidate')],
                        marker='o', alpha=.65, label=f'Pair {rep+1}')
            ax.scatter([0,1], [cohort[arm]['median']/1000 for arm in ('reference','candidate')],
                       marker='D', color='black', s=55, zorder=3, label='Median')
            ax.set_xticks([0,1], labels)
            ax.set_xlim(-.25,1.25)
            ax.set_ylabel('Milliseconds per complete timed cycle')
            ax.set_title(title + f"\nMedian time change: {cohort['time_change_percent']:+.2f}%", fontsize=10)
            ax.grid(axis='y', alpha=.25)
        axes.flat[0].legend(fontsize=7)
        subtitle = ('192 conversion cases pass; complete consumers exact; no model speedup measured' if name == 'narrow-vector'
                    else 'Packing included; exact across tiles; 48 original-input failures retained (exit 1)')
        fig.suptitle('Q2 component measurements on .157, fan82 policy\n' + subtitle, fontsize=12)
        for ext in ('svg','png'):
            output = ROOT / 'docs' / 'assets' / f'q2-{name}-results.{ext}'
            output.parent.mkdir(exist_ok=True)
            fig.savefig(output, dpi=160, metadata={'Date': None} if ext == 'svg' else None)
            if ext == 'svg':
                output.write_text('\n'.join(line.rstrip() for line in output.read_text().splitlines()) + '\n')
        plt.close(fig)


if __name__ == '__main__':
    main()
