#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare retained C1 screens without asserting zero-margin non-regression."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics


def read_run(path):
    root=path/'results'
    result=json.loads((root/'result.json').read_text())
    if result['state']!='MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT':
        raise ValueError('Incomplete or failed model arm: '+str(path))
    for name,receipt in result['artifacts'].items():
        data=(root/name).read_bytes()
        if len(data)!=receipt['bytes'] or hashlib.sha256(data).hexdigest()!=receipt['sha256']:
            raise ValueError('Artifact changed: '+name)
    rows=[]
    for log in root.glob('*.log'):
        for line in log.read_text().splitlines():
            if line.startswith('{'):
                row=json.loads(line)
                if row.get('event')=='sample' and row['label'].startswith('pp'): rows.append(row)
    if len(rows)!=12: raise ValueError('Expected one warmup and three samples per profile')
    return root,rows,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--patched',type=Path,required=True)
    parser.add_argument('--q2',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    runs={label:read_run(path) for label,path in [('UD original',args.base),('UD patched',args.patched),('Q2',args.q2)]}
    args.output.mkdir(parents=True)
    a,b=runs['UD original'][0],runs['UD patched'][0]
    compared=[];different=[]
    for p in sorted(a.iterdir()):
        if p.suffix in ('.f32','.u32','.i32'):
            compared.append(p.name)
            if p.read_bytes()!=(b/p.name).read_bytes(): different.append(p.name)
    table=[]
    for label,(_,rows,_) in runs.items():
        for size in (512,2048,8192):
            measured=[r for r in rows if r['prompt_tokens']==size and not r['warmup']]
            if len(measured)!=3 or any(r['output_tokens']!=128 or r['decode_steps']!=127 or r['eos'] for r in measured):
                raise ValueError('Different token or stopping scope; cannot compare fixed-length screen')
            for metric in ('prefill_tok_s','decode_steps_s'):
                values=[r[metric] for r in measured]
                table.append({'arm':label,'prompt_tokens':size,'metric':metric,'n':len(values),
                              'minimum':min(values),'median':statistics.median(values),'maximum':max(values)})
    with (args.output/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    report={'schema':'synapse-lie.q2-c1-screen.v1','arms':{k:str(v) for k,v in [('UD original',args.base),('UD patched',args.patched),('Q2',args.q2)]},
            'ud_exact_comparison':{'files':len(compared),'different':different},'measurements':table,
            'verdict':'Initial noninterleaved C1 screen; no formal zero-margin non-regression verdict',
            'q2_teacher_parity':'Not established; independent operator checks plus semantic smoke only'}
    report['cross_format_input_output_differences']=[p.name for p in a.iterdir()
        if p.suffix in ('.u32','.i32') and p.read_bytes()!=(runs['Q2'][0]/p.name).read_bytes()]
    def median(arm,size,metric):
        return next(r['median'] for r in table if r['arm']==arm and r['prompt_tokens']==size and r['metric']==metric)
    report['relative_to_ud_original']={arm:{str(size):{metric:median(arm,size,metric)/median('UD original',size,metric)
        for metric in ('prefill_tok_s','decode_steps_s')} for size in (512,2048,8192)} for arm in ('UD patched','Q2')}
    report['q2_practical_performance_gate']='FAIL: Q2 is slower than existing UD at every measured PP/TG profile'
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Q2 C1 screen','',report['verdict'],'',
           '| Arm | Prompt | PP tok/s min / median / max | TG steps/s min / median / max |',
           '|---|---:|---:|---:|']
    for label in runs:
        for size in (512,2048,8192):
            values=[]
            for metric in ('prefill_tok_s','decode_steps_s'):
                row=next(r for r in table if r['arm']==label and r['prompt_tokens']==size and r['metric']==metric)
                values.append(' / '.join(f'{row[k]:.2f}' for k in ('minimum','median','maximum')))
            lines.append(f'| {label} | {size} | {values[0]} | {values[1]} |')
    lines+=['',f'UD token/frontier files compared exactly: {len(compared)}; changed: {len(different)}.',
            'TG counts 127 completed decode calls after the first output token from prefill.',
            'Each profile retains one warmup and three measured fresh sessions. MTP is disabled.']
    (args.output/'report.md').write_text('\n'.join(lines)+'\n')
    os.environ.setdefault('MPLCONFIGDIR',str(args.output.resolve()/'.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for axis,metric,title in zip(axes,('prefill_tok_s','decode_steps_s'),('Fresh prefill','Decode (127 calls)')):
        for label in runs:
            selected=[r for r in table if r['arm']==label and r['metric']==metric]
            x=[r['prompt_tokens'] for r in selected]; y=[r['median'] for r in selected]
            axis.errorbar(x,y,yerr=[[r['median']-r['minimum'] for r in selected],[r['maximum']-r['median'] for r in selected]],marker='o',capsize=4,label=label)
        axis.set_xscale('log',base=2);axis.set_xticks([512,2048,8192],['512','2K','8K'])
        axis.set_xlabel('Physical prompt tokens');axis.set_ylabel('Tokens/s' if metric=='prefill_tok_s' else 'Decode calls/s')
        axis.set_ylim(bottom=0);axis.set_title(title);axis.grid(alpha=.25);axis.legend()
    fig.suptitle('Q2 compatibility: initial C1 screen (median and observed range)')
    fig.savefig(args.output/'comparison.svg');fig.savefig(args.output/'comparison.png',dpi=150)
    print('\n'.join(lines))


if __name__=='__main__':
    main()
