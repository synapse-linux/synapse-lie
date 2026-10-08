#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot every retained HC component sample; never convert it to model rates."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/q2-norm-fixed-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    report = json.loads((ROOT/'config/q2-norm-fixed-results.json').read_text())
    out = ROOT/'docs/figures/q2-norm-fixed'
    if any(out.with_suffix(suffix).exists() for suffix in ('.png','.svg')):
        raise ValueError('Refusing to overwrite retained figures')
    matplotlib.rcParams['svg.hashsalt'] = 'q2-norm-fixed'
    fig, axes = plt.subplots(2,2,figsize=(10,7),layout='constrained')
    labels = {'before':'Reference before','candidate':'Fixed shape','after':'Reference after'}
    for column,moe in enumerate((False,True)):
        for row,paired in enumerate((True,False)):
            axis = axes[row,column]
            for name,arm in report['arms'].items():
                values = [t for t in arm['timings'] if t['moe']==moe and t['paired']==paired]
                axis.plot([t['rep']+1 for t in values],
                          [t['microseconds_per_iteration']/1000 for t in values],
                          marker='o',label=labels[name])
            axis.set(title=('MoE' if moe else 'Ordinary')+' / '+('paired producer' if paired else 'unchanged control'),
                     xlabel='Measured repetition, identical input',ylabel='Complete cycle, ms',xticks=range(1,6))
            axis.grid(alpha=.2);axis.legend(fontsize=8)
    fig.suptitle('2048-row HC component: all 60 samples; candidate rejected, no model throughput claim')
    fig.savefig(out.with_suffix('.png'),dpi=160)
    fig.savefig(out.with_suffix('.svg'),metadata={'Date':None})
    svg=out.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__ == '__main__':
    main()
