#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the audited 256K comparison, including historical control variation."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT/'config/q2-curve256-results.json').read_text())
    out = ROOT/'docs/figures/q2-curve256'
    curves = {key:data['rows'] for key,data in report['arms'].items()}
    curves.update({'historical_'+key:rows for key,rows in report['historical'].items()})
    labels = dict(q2='Retained Q2, capacity266240',ud='UD, capacity266240',
        historical_before='Saved Q2 before, capacity133760',
        historical_after='Saved Q2 after, capacity133760')
    colors = dict(q2='#087f8c',ud='#c05224',historical_before='#8a8e9a',historical_after='#566079')
    depths = [c['depth'] for c in report['cells']]
    ticklabels = ['0' if not d else str(d//1024)+'K' for d in depths]
    matplotlib.rcParams['svg.hashsalt'] = 'q2-curve256'
    fig,axes = plt.subplots(3,2,figsize=(13,11),layout='constrained')
    for ax,metric,title,unit,factor in zip(axes.flat,
        ('pp_tps','tg_tps','prefill_ms','ttft_seconds','prefix_total_prefill_ms','wall_seconds'),
        ('Continuation prefill','Decode','Continuation prefill duration','HTTP time to first output',
         'Prefix construction: accumulated physical prefill','Complete measured HTTP request'),
        ('Tokens/s','Tokens/s','Seconds','Seconds','Seconds','Seconds'),
        (1,1,.001,1,.001,1)):
        for key,rows in curves.items():
            ax.plot([depths.index(r['depth']) for r in rows],
                [r[metric]*factor for r in rows],label=labels[key],color=colors[key],
                linestyle='--' if key.startswith('historical') else '-',marker='o',markersize=3.5)
        ax.set_xticks(range(len(depths)),ticklabels)
        ax.set_xlabel('Requested cached-prefix depth (tokens)')
        ax.set_ylabel(unit);ax.set_title(title,fontsize=11);ax.grid(alpha=.22)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('.157 GPU — native synapse-lie-bench, canonical prose, pp≈2048 / tg128, C1 AR\n'
                 'Capacity266240 forces sparse attention fallback in both new arms\n'
                 'One measurement per depth; old/new comparison also changes capacity, attention route and cache history',fontsize=11)
    for suffix in ('png','svg'):
        target=out/('curve.'+suffix)
        if target.exists():raise ValueError('Preserve existing plot')
        fig.savefig(target,dpi=175,metadata={'Date':None} if suffix=='svg' else None)
    plt.close(fig)
    target=out/'curve.svg'
    target.write_text('\n'.join(s.rstrip() for s in target.read_text().splitlines())+'\n')
    rows=[]
    for cell in report['cells']:
        row={'depth':cell['depth']}
        for key in curves:
            point=next((r for r in curves[key] if r['depth']==cell['depth']),None)
            for metric in ('pp_tps','tg_tps','prefill_ms','decode_ms','prefill_tokens',
                           'cached_tokens','prefix_total_prefill_ms','prefix_total_prefill_tokens'):
                row[key+'_'+metric]=point[metric] if point else None
        row.update({k:v for k,v in cell.items() if k.endswith('_percent')})
        rows.append(row)
    with (out/'comparison.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    print(out)


if __name__ == '__main__':
    main()
