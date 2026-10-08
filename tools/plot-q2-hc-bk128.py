#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export BK128 timings beside the saved bounded parent and full FP64 checks."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def csv_file(path,rows):
    with path.open('x') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    report=json.loads((ROOT/'config/q2-hc-bk128-component-results.json').read_text())
    parent=json.loads((ROOT/'config/q2-hc-bk256-component-results.json').read_text())['arms']['bounded']
    if report['schema']!='synapse-lie.q2-hc-bk128-component.v1' or report['controls_rerun']:
        raise ValueError('Expected candidate-only BK128 components')
    arms=dict(parent=parent,**report['arms'])
    output=ROOT/'docs/figures/q2-hc-bk128'
    output.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for key,arm in arms.items():
        for sample in arm['timings']:
            rows.append(dict(candidate=key,historical=key=='parent',source=arm['label'],**sample))
    if len(rows)!=168:
        raise ValueError('Expected112 new and56 saved timings')
    csv_file(output.with_suffix('.csv'),rows)
    checks=[dict(candidate=key,**e) for key,arm in report['arms'].items() for e in arm['down_fp64_checks']]
    csv_file(output.with_name(output.name+'-fp64.csv'),checks)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(16,10))
    keys=[(key,native) for key in arms for native in (False,True)]
    for ax,(moe,complete) in zip(axes.flat,[(False,False),(False,True),(True,False),(True,True)]):
        names=[('Saved BK256' if key=='parent' else 'BK128 '+key)+'\n'+
               ('native' if native else 'library') for key,native in keys]
        medians=[]
        for key,native in keys:
            scope=next(s for s in arms[key]['summaries'] if s['moe']==moe and s['complete']==complete)
            medians.append(scope['native' if native else 'library']['median'])
        ax.bar(names,medians,color=['#74acbb','#389878','#74acbb','#b35c57','#74acbb','#8a75a9'])
        maximum=max(medians)
        for x,(key,native) in enumerate(keys):
            samples=[s for s in arms[key]['timings'] if s['moe']==moe and
                     s['complete']==complete and s['native']==native]
            values=[s['us_per_iteration'] for s in samples]
            maximum=max(maximum,*values)
            ax.scatter([x-.08,x+.08],values[:2],facecolors='none',edgecolors='black',s=25,zorder=4,
                       label='Two warmups' if x==0 else None)
            ax.scatter([x-.08,x-.04,x,x+.04,x+.08],values[2:],c='black',s=17,zorder=4,
                       label='Five measured samples' if x==0 else None)
            ax.annotate(f'{medians[x]:.2f}',(x,max(values)),xytext=(0,6),textcoords='offset points',ha='center')
        ax.set_ylim(0,maximum*1.3)
        ax.set_ylabel('Microseconds / iteration; lower is faster')
        ax.set_title(('MoE' if moe else 'Ordinary')+' — '+('producer + down' if complete else 'down only'))
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper left',fontsize=8)
    fig.suptitle('BK128 staging on .157 — two new candidates and saved BK256 parent')
    fig.text(.5,.025,'100 MiB rotating original-F16 weights,2048 tokens. All112 new and56 historical timings shown.\n'
             'Both new components preserve every parent output but are slower; no model selected. Strict numerical exits1 retained.',
             ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.09,1,.95))
    for suffix in ('.svg','.png'):
        if output.with_suffix(suffix).exists():
            raise ValueError('Refusing to overwrite graph')
        fig.savefig(output.with_suffix(suffix),dpi=150)
    svg=output.with_suffix('.svg');lines=svg.read_text().splitlines();lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    print(json.dumps(dict(new_timings=112,historical_timings=56,fp64_checks=len(checks),output=str(output))))


if __name__=='__main__':
    main()
