#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render saved and new original128K PP/TG observations without a GPU run."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    result=json.loads((ROOT/'config/q2-iq2-decode-lds-native128-results.json').read_text())
    keys=['original','isolated_hc','down_rows','iq2_lds']
    labels=['Saved original','Isolated HC','Retained down rows','IQ2 LDS candidate']
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for ax,key,title,target in zip(axes,['prefill_tps','decode_tps'],
                                  ['Complete prefill','Decode: eight calls'],[1500,30]):
        values=[result['rates'][k][key] for k in keys]
        ax.bar(range(4),values,color=['#64748b','#3b82f6','#15996f','#e8a242'],width=.6)
        for i,value in enumerate(values):
            ax.text(i,value+target*.025,f'{value:.2f}',ha='center',fontsize=9)
        ax.axhline(target,color='#9b3747',linestyle='--',linewidth=1,label=f'Target: {target} tokens/s')
        ax.set_xticks(range(4),labels,fontsize=9)
        ax.set_ylim(0,target*1.15)
        ax.set_ylabel('tokens/s')
        ax.set_title(title)
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper center',fontsize=8)
    fig.suptitle('Q2 original 128K input: IQ2 LDS model trial')
    fig.text(.5,.09,'130,925 input tokens; 63 x 2,048 + 1,901; capacity 133,760; zero cached tokens.',ha='center',fontsize=9)
    fig.text(.5,.05,'Same native benchmark and original four requests. Saved references reused; performance / 120 W verified.',ha='center',fontsize=9)
    fig.text(.5,.012,'PP +0.013%, TG -0.053% versus retained down rows: no material gain. Four outputs exact; sustained TG128 remains open.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.15,1,.94))
    for extension in ('png','svg'):
        path=ROOT/('docs/figures/q2-iq2-decode-lds-native128.'+extension)
        fig.savefig(path,dpi=160)
        if extension=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    print('Saved original128K PP/TG PNG and SVG; no GPU operation.')


if __name__=='__main__':
    main()
