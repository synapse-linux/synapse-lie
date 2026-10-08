#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the complete new row-reader observations without replacing retained plots."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
first=json.loads((ROOT/'config/q2-ple-row-bytes-results.json').read_text())
long=json.loads((ROOT/'config/q2-ple-row-bytes-long-results.json').read_text())
rows=first['rows']+long['rows']
assert [r['tokens'] for r in rows]==[4088,8138,8177,12242,16317,32711,65440,130925]
output=ROOT/'docs/figures/q2-ple-row-bytes'
output.mkdir(exist_ok=True)
for suffix in ('png','svg','csv'):
    assert not (output/('pp-tg.'+suffix)).exists(),'Preserve earlier plot'
fields=['tokens','calls','full_chunks','tail','parent_pp','candidate_pp','pp_change_percent',
        'parent_prefill_ms','candidate_prefill_ms','parent_tg','candidate_tg','tg_change_percent',
        'parent_decode_ms','candidate_decode_ms','decode_calls','cached_tokens','reply_exact']
with (output/'pp-tg.csv').open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
matplotlib.rcParams['svg.hashsalt']='q2-ple-row-bytes'
fig,axes=plt.subplots(2,1,figsize=(12,8.5),layout='constrained')
labels=[str(r['depth']//1024)+'K'+(' #'+str(r['attempt']+1) if r['depth']==8192 else '') for r in rows]
for ax,field,title,target in ((axes[0],'pp','Complete uncached prefill',1500),(axes[1],'tg','Autoregressive decode — original eight calls per prefix',30)):
    for key,name,color in (('parent','Saved retained Q2','#536478'),('candidate','Q2 row-sized BF16 reader (trial)','#087f8c')):
        ax.plot(range(len(rows)),[r[key+'_'+field] for r in rows],label=name,color=color,marker='o')
    ax.axhline(target,color='#b24630',linestyle='--',linewidth=1,label=f'Target: {target} tokens/s')
    for i,r in enumerate(rows):
        ax.annotate(f"{r['candidate_'+field]:.1f}",(i,r['candidate_'+field]),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
    ax.set_xticks(range(len(rows)),labels);ax.set_ylabel('Tokens/s');ax.set_title(title);ax.grid(alpha=.2)
    ax.set_ylim(bottom=0);ax.legend(fontsize=9,ncol=3)
axes[1].set_xlabel('Original requested prefix depth (all original 8K observations retained)')
fig.suptitle('.157 GPU · native synapse-lie-bench · capacity 133760 · chunk 2048 · C1 AR\n'
    'Same saved input messages and natural final tails; no prefix-cache hits\n'
    'Single observations; saved controls; separate cooled 64K/128K sessions. New reader not measured at fixed 2K.',fontsize=10)
for suffix in ('png','svg'):
    fig.savefig(output/('pp-tg.'+suffix),dpi=170,metadata={'Date':None} if suffix=='svg' else None)
plt.close(fig)
p=output/'pp-tg.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
print(output/'pp-tg.png')
