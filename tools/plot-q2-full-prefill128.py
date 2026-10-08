#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all exact full-prefix observations, including both saved8K attempts."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'config/q2-full-prefill128-results.json').read_text())
rows=report['rows'];out=ROOT/'docs/figures/q2-full-prefill128'
labels=[str(r['depth']//1024)+'K'+(' #'+str(r['attempt']+1) if r['depth']==8192 else '') for r in rows]
styles=[('current','Current retained Q2','#087f8c','-'),('ud','Saved UD','#c05224','--'),
        ('before','Saved Q2 before','#8a8e9a',':'),('after','Saved Q2 after','#566079',':')]
matplotlib.rcParams['svg.hashsalt']='q2-full-prefill128'
fig,axes=plt.subplots(2,1,figsize=(12,8),layout='constrained')
for ax,field,title,unit in [(axes[0],'prefill_tps','Complete uncached prefill throughput','Tokens/s'),
                           (axes[1],'prefill_seconds','Complete uncached prefill duration','Seconds')]:
    for key,label,color,line in styles:
        ax.plot(range(len(rows)),[r[key+'_'+field] for r in rows],label=label,color=color,linestyle=line,marker='o',markersize=4)
    ax.set_xticks(range(len(rows)),labels);ax.set_xlabel('Original requested prefix depth')
    ax.set_ylabel(unit);ax.set_title(title);ax.set_ylim(bottom=0);ax.grid(alpha=.2)
axes[0].legend(ncol=2,fontsize=9)
fig.suptitle('.157 GPU / retained Q2 / native synapse-lie-bench / capacity133760 / chunk2048\n'
    'Exact saved messages and physical counts; all full chunks plus the natural last remainder\n'
    'Archived references, one sample each.64K/128K recovered in separate sessions after cooling.',fontsize=10)
for ext in ('svg','png'):
    target=out/('full-prefill.'+ext)
    if target.exists():raise ValueError('Preserve existing plot')
    fig.savefig(target,dpi=160,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
p=out/'full-prefill.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
print(out)
