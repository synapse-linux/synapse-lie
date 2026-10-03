#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot all scaled-input component timings alongside the numerical rejection."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    data=json.loads(args.report.read_text())['component']
    os.environ.setdefault('MPLCONFIGDIR',str(Path('evidence/.mpl-cache').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4.2))
    records=[]
    for axis,(active,group) in zip(axes,data['timing'].items()):
        names=['Compensated','Scaled + packing']
        medians=[group[k]['median']/1000 for k in ('reference','candidate')]
        bars=axis.bar(names,medians,color=['#376fbd','#c28031'])
        axis.bar_label(bars,labels=[f'{v:.3f}' for v in medians],padding=4)
        for index,key in enumerate(('reference','candidate')):
            samples=group[key]['samples']
            axis.scatter([index+(r-2)*.025 for r in range(5)], [v/1000 for v in samples],color='#222222',s=12,zorder=3)
            records.extend(dict(active_experts=active,arm=key,repetition=r,value_us=v) for r,v in enumerate(samples))
        axis.set_title(f"{active} active experts\n{group['time_change_percent']:.2f}% cycle time")
        axis.set_ylabel('Milliseconds per packing + down cycle')
        axis.set_ylim(0,max(medians)*1.2)
        axis.grid(axis='y',alpha=.2);axis.set_axisbelow(True)
    fig.suptitle('Q2 scaled input: faster component, numerical acceptance FAILED')
    fig.text(.5,.025,'Original weights and FP64 operands; 18 operator failures at unchanged 0.002 limits.\n'
             'Three large-shape sampled oracles pass. These are component times, not model throughput.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.13,1,.90))
    for suffix in ('.svg','.png'):fig.savefig(args.output.with_suffix(suffix),dpi=150)
    svg=args.output.with_suffix('.svg');lines=svg.read_text().splitlines();lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    with args.output.with_suffix('.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n');writer.writeheader();writer.writerows(records)


if __name__=='__main__':main()
