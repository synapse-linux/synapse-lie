#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export diagnostic PLE waits and process I/O, never headline throughput."""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    assert report['schema'] == 'synapse-lie.q2-curve-ple-profile.v1'
    assert report['diagnostic_only'] and not report['headline_eligible']
    args.output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='q2-curve-profile-mpl-') as cache:
        os.environ.setdefault('MPLCONFIGDIR',cache)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        rows = []
        for model,group in report['models'].items():
            for row in group['rows']:
                for phase,s in row['phases'].items():
                    item = dict(model=model,depth=row['depth'],phase=phase,calls=s['calls'],tokens=s['tokens'],
                        forward_ms=s['forward_ms'],server_executor_ms=s['server_executor_ms'],
                        process_read_bytes=s['process_read_bytes'],cache_hit_fraction=s['cache_hit_fraction'])
                    item.update(s['ple'])
                    rows.append(item)
        with (args.output/'samples.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
        fig,axes=plt.subplots(2,2,figsize=(12,8))
        for ri,phase in enumerate(('prefill','decode')):
            for model,color in [('q2','#007f8b'),('ud','#d66a28')]:
                group=[r for r in rows if r['model']==model and r['phase']==phase]
                axes[ri,0].plot(range(8),[r['blocked_ns']/1e6 for r in group],'o-',color=color,label=model.upper())
                axes[ri,1].plot(range(8),[r['process_read_bytes']/2**20 for r in group],'o-',color=color,label=model.upper())
            for ci,ax in enumerate(axes[ri]):
                ax.set(title=('New-turn prefill' if ri==0 else 'Complete 128-token decode') +
                       (': host PLE wait' if ci==0 else ': process storage reads'),
                       xlabel='Cached-prefix target',ylabel='milliseconds' if ci==0 else 'MiB',
                       xticks=range(8),xticklabels=['0','4K','8K','12K','16K','32K','64K','128K'])
                ax.grid(alpha=.2);ax.legend(frameon=False)
        fig.suptitle('Q2 / UD diagnostic attribution on the canonical HTTP workload',fontsize=14)
        fig.text(.065,.025,'Instrumented runs; not throughput evidence. Host wait can overlap GPU work.\n'
                 'Process I/O includes all storage reads. The Q2 8K spike is retained; one observation per cell.',fontsize=9)
        fig.subplots_adjust(top=.89,bottom=.15,hspace=.48,wspace=.27)
        fig.savefig(args.output/'profile.png',dpi=160);fig.savefig(args.output/'profile.svg')
        svg=args.output/'profile.svg'
        svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n')
    print(json.dumps(dict(rows=len(rows),output=str(args.output))))


if __name__ == '__main__':
    main()
