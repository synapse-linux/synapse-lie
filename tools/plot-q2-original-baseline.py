#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export verified historical/fresh C17 benchmark samples and comparison figures."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'docs/figures/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    r = json.loads((ROOT/'config/q2-original-baseline-results.json').read_text())
    destination = ROOT/'docs/figures/q2-original-baseline'
    destination.parent.mkdir(exist_ok=True)
    targets = ('512','2048','8192')
    groups = [('Historical UD',r['historical']),('Fresh Q2',r['model']['q2']),
              ('Fresh UD',r['model']['ud'])]
    fields = ('series','target','physical_tokens','rep','warmup','completed_tokens',
              'prefill_seconds','decode_seconds','prefill_tok_s','decode_tok_s',
              'prefill_logits_sha256','decode_logits_sha256')
    count = 0
    with destination.with_suffix('.csv').open('w',newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name,model in groups:
            for target in targets:
                p=model['profiles'][target]
                for s in p['samples']:
                    pp,tg=s['prefill_ns']/1e9,s['decode_ns']/1e9
                    writer.writerow(dict(series=name,target=target,physical_tokens=s['prompt_tokens'],
                        rep=s['rep'],warmup=s['warmup'],completed_tokens=s['completed_decode_tokens'],
                        prefill_seconds=pp,decode_seconds=tg,prefill_tok_s=s['prompt_tokens']/pp,
                        decode_tok_s=s['completed_decode_tokens']/tg,
                        prefill_logits_sha256=s['prefill_logits_sha256'],
                        decode_logits_sha256=s['decode_logits_sha256']))
                    count += 1
    assert count == 36
    colors = {'q2':'#007f8b','ud':'#d66a28'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(12,8),gridspec_kw={'height_ratios':[2.1,1]})
    x=np.arange(3);width=.34
    labels=[str(r['historical']['profiles'][t]['input']['prompt_tokens']) for t in targets]
    for column,metric,title in [(0,'prefill_tok_s','Prefill'),(1,'decode_tok_s','Completed decode')]:
        ax=axes[0,column]
        for name,offset in [('q2',-width/2),('ud',width/2)]:
            profiles=r['model'][name]['profiles']
            median=np.array([profiles[t]['medians'][metric] for t in targets])
            low=np.array([min(profiles[t]['rates'][metric]) for t in targets])
            high=np.array([max(profiles[t]['rates'][metric]) for t in targets])
            bars=ax.bar(x+offset,median,width,color=colors[name],label='Fresh '+name.upper(),
                yerr=np.array([median-low,high-median]),capsize=3)
            ax.bar_label(bars,labels=[f'{v:.3f}' for v in median],padding=6,fontsize=9)
        historical=[r['historical']['profiles'][t]['medians'][metric] for t in targets]
        ax.plot(x,historical,'o--',color='#323c46',markersize=4,linewidth=1,label='Historical UD median')
        ax.set(title=title,ylabel='tokens / second',xticks=x,xticklabels=labels)
        ax.set_ylim(0,max(ax.get_ylim()[1],max(historical)*1.2))
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        gap=axes[1,column]
        changes=[r['q2_change_percent'][t]['fresh_ud'][metric] for t in targets]
        bars=gap.bar(x,changes,width=.55,color=colors['q2'])
        gap.bar_label(bars,labels=[f'{v:.2f}%' for v in changes],padding=4,fontsize=10)
        gap.axhline(0,color='#323c46',linewidth=.8)
        gap.set(xticks=x,xticklabels=labels,ylabel='Q2 versus fresh UD (%)',xlabel='Physical prompt tokens')
        gap.set_ylim(min(changes)*1.3,1);gap.grid(axis='y',alpha=.18);gap.set_axisbelow(True)
    fig.suptitle('Original C17 benchmark: Q2 still trails UD',fontsize=17,fontweight='bold',y=.985)
    fig.text(.5,.94,'Same historical benchmark, ABI and adapter; original model files; .157 GPU',ha='center',color='#52606d')
    handles,legend_labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='upper center',bbox_to_anchor=(.5,.923),
               ncol=3,fontsize=9,frameon=False)
    fig.text(.06,.022,'C1 AR, context 9216, chunk 2048, 128 completed tokens. One warmup + three measured rounds.\n'
             'Bars: medians; whiskers: retained min/max. Existing numerical rejection remains. No new GPU speedup claimed.',
             fontsize=9,color='#52606d')
    fig.subplots_adjust(top=.86,bottom=.14,hspace=.35,wspace=.24)
    fig.savefig(destination.with_suffix('.svg'))
    fig.savefig(destination.with_suffix('.png'),dpi=170)
    plt.close(fig)
    print(json.dumps({'csv_rows':count,'svg':str(destination.with_suffix('.svg')),
                      'png':str(destination.with_suffix('.png'))}))


if __name__ == '__main__':
    main()
