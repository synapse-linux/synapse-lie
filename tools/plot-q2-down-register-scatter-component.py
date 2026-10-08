#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all register-scatter component samples, including warmups."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT/'config/q2-down-register-scatter-component-results.json').read_text())
    rows = report['timings']
    assert len(rows) == 28 and report['device_work_safe']
    out = ROOT/'docs/figures/q2-down-register-scatter-component'
    assert not any(out.with_suffix(s).exists() for s in ('.csv','.svg','.png'))
    with out.with_suffix('.csv').open('x') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1,2,figsize=(11,5))
    for ax, group in zip(axes,report['summaries']):
        for index, arm in enumerate(('reference','candidate')):
            values = group[arm]
            ax.bar(index,values['median'],color=('#379878','#c4844e')[index])
            selected = [r for r in rows if r['scope']==group['scope'] and r['candidate']==bool(index)]
            measured = [r['us_per_iteration'] for r in selected if not r['warmup']]
            warm = [r['us_per_iteration'] for r in selected if r['warmup']]
            ax.scatter([index+(i-2)*.04 for i in range(5)],measured,c='black',s=22,zorder=3,
                       label='Five measured samples' if index==0 else None)
            ax.scatter([index-.02,index+.02],warm,facecolors='none',edgecolors='black',s=30,zorder=3,
                       label='Two warmups' if index==0 else None)
            ax.annotate(f"{values['median']:.2f}",(index,max(measured+warm)),
                        xytext=(0,8),textcoords='offset points',ha='center')
        ax.set_xticks([0,1],['Saved-parent\nLDS transpose','New register\ntranspose'])
        ax.set_title(group['scope']+f"\nCandidate time {group['candidate_time_change_percent']:+.3f}%")
        ax.set_ylabel('Microseconds per cycle; lower is faster')
        ax.set_ylim(0,max(r['us_per_iteration'] for r in rows if r['scope']==group['scope'])*1.16)
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='lower left',fontsize=8)
    fig.suptitle('Q2 register scatter: one production distribution on .157')
    fig.text(.5,.02,'2048 tokens, 512 experts, 10 routes/token, BN48; three rotating weight sets total 990,904,320 bytes.\n'
        'Original rounding/consumer checked separately. Component timing is not model throughput.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.10,1,.95))
    for suffix in ('.svg','.png'):
        fig.savefig(out.with_suffix(suffix),dpi=150)
    plt.close(fig)
    print(json.dumps(dict(samples=len(rows),output=str(out))))


if __name__ == '__main__':
    main()
