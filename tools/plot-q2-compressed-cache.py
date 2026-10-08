#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all new cache timings and unchanged historical model comparisons."""
import csv,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
phase=sys.argv[1]
if phase not in ('component','model'):raise SystemExit('Expected component/model')
r=json.loads((ROOT/('config/q2-compressed-cache-'+phase+'-results.json')).read_text())
output=ROOT/('docs/figures/q2-compressed-cache-'+phase)
if any(output.with_suffix(s).exists() for s in ('.csv','.svg','.png')):raise ValueError('Refusing overwrite')
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
if phase=='component':
 rows=r['timings'];fig,axes=plt.subplots(2,2,figsize=(13,9));axes=axes.ravel()
 for ax,(name,pair) in zip(axes,r['summaries'].items()):
  for index,arm in enumerate(('original','cached')):
   samples=[x for x in rows if x['case']==name and x['cached']==bool(index)]
   value=pair[arm]['median'];ax.bar(index,value,color='#c4844e' if index else '#379878')
   warm=[x['us'] for x in samples if x['warmup']];measured=[x['us'] for x in samples if not x['warmup']]
   ax.scatter([index-.025,index+.025],warm,facecolors='none',edgecolors='black',label='Two warmups' if index==0 else None,zorder=3)
   ax.scatter([index-.08+.04*i for i in range(5)],measured,c='black',s=22,label='Five measured' if index==0 else None,zorder=3)
   ax.annotate(f'{value:.2f}',(index,max(*warm,*measured)),xytext=(0,8),textcoords='offset points',ha='center')
  ax.set_xticks([0,1],['Encoded weights','Compressed slots']);ax.set_ylim(0,max(x['us'] for x in rows if x['case']==name)*1.2)
  ax.set_title(('IQ2 gate/up' if name.startswith('iq2') else 'Q2 down, half output')+' / '+('512' if 'e512' in name else '64')+' active experts')
  ax.set_ylabel('Projection microseconds; lower is faster');ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2);ax.legend(loc='lower left',fontsize=8)
 fig.suptitle('Q2 compressed expert slots: all 56 component timings on .157')
 fig.text(.5,.012,'Three weight rotations beyond32MiB. Slot upload/setup excluded; original K16 arithmetic retained.\nComponent timings do not establish model throughput.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.06,1,.95))
else:
 arms={k:r['references'][k] for k in ('fixed_q2','best_parent')};arms['cache']=r['model'];arms['fixed_ud']=r['references']['fixed_ud']
 labels=['Fixed Q2','Saved Q2\n1585 candidate','New Q2\ncompressed slots','Fixed UD']
 rows=[dict(arm=k,historical=k!='cache',source=Path(v['path']).name,**{f:s[f] for f in ('rep','warmup','prompt_tokens','output_tokens','decode_steps','prefill_s','decode_s','prefill_tok_s','decode_steps_s')}) for k,v in arms.items() for s in v['samples']]
 assert len(rows)==16
 fig,axes=plt.subplots(1,2,figsize=(13,6))
 for ax,metric,title in zip(axes,('prefill_tok_s','decode_steps_s'),('Prefill tokens/s','Decode forward calls/s')):
  for index,(name,arm) in enumerate(arms.items()):
   v=arm['measurements'][metric]['median'];ax.bar(index,v,color=['#748fb5','#379878','#c4844e','#5b6477'][index])
   warm=[x[metric] for x in arm['samples'] if x['warmup']];measured=[x[metric] for x in arm['samples'] if not x['warmup']]
   ax.scatter([index],warm,facecolors='none',edgecolors='black',label='Warmup' if index==0 else None,zorder=3)
   ax.scatter([index-.06,index,index+.06],measured,c='black',s=23,label='Three measured' if index==0 else None,zorder=3)
   ax.annotate(f'{v:.3f}',(index,max(*warm,*measured)),xytext=(0,8),textcoords='offset points',ha='center')
  ax.set_xticks(range(4),labels);ax.set_ylim(0,max(x[metric] for arm in arms.values() for x in arm['samples'])*1.17)
  ax.set_title(title);ax.set_ylabel('Higher is faster');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(loc='lower left',fontsize=8)
 fig.suptitle('Q2 compressed expert slots: one new original2048/tg128 model on .157')
 fig.text(.5,.025,'23061 of24576 compressed expert slots; 32GiB quota replaces expert allocations. Four new and twelve saved samples.\nOriginal input/timers, capacity9216/chunk2048/MTP off; saved controls reused without rerun.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.10,1,.95))
with output.with_suffix('.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
for suffix in ('.svg','.png'):fig.savefig(output.with_suffix(suffix),dpi=150)
p=output.with_suffix('.svg');lines=p.read_text().splitlines();lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->');p.write_text('\n'.join(x.rstrip() for x in lines)+'\n')
print(json.dumps(dict(phase=phase,rows=len(rows),output=str(output))))
