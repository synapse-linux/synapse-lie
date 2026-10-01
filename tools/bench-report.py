#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate benchmark JSONL; export summaries and scientific SVG/PNG plots."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics


def read_result(path):
    rows=[json.loads(x) for x in Path(path).read_text().splitlines()]
    if not rows or rows[0].get('schema')!='synapse-lie.bench.v1' or rows[-1]!={'event':'complete','exit_code':0}:
        raise ValueError('incomplete/failed benchmark; preserve raw evidence, no partial averaging')
    identity=rows[0]
    inputs={r['point']:r for r in rows if r['event']=='input'}
    samples=[r for r in rows if r['event']=='sample']
    result=[]
    for point,p in sorted(inputs.items()):
        group=[r for r in samples if r['point']==point]
        expected=identity['warmups']+identity['repetitions']
        if len(group)!=expected or [r['rep'] for r in group]!=list(range(expected)):
            raise ValueError('missing/reordered/duplicate sample')
        if len(p['physical_ids'])!=p['prompt_tokens']:
            raise ValueError('physical input count')
        ids=b''.join(int(i).to_bytes(4,'little',signed=True) for i in p['physical_ids'])
        if hashlib.sha256(ids).hexdigest()!=p['physical_ids_sha256']:
            raise ValueError('physical input hash')
        for r in group:
            if r['warmup']!=int(r['rep']<identity['warmups']) or (r['depth'],r['users'],r['prompt_tokens'])!=(p['depth'],p['users'],p['prompt_tokens']):
                raise ValueError('workload/warmup drift')
            if r['cache_tokens']!=r['depth'] or r['prefill_tokens_per_user']!=r['prompt_tokens']-r['cache_tokens']:
                raise ValueError('fresh versus reused prefill accounting')
            if r['output_tokens']!=r['users']*r['output_tokens_per_user'] or len(r['output_ids'])!=r['output_tokens_per_user'] or not 0<=r['output_tokens_per_user']<=identity['output_limit']:
                raise ValueError('confirmed output count')
            if r['full_output_budget']!=int(r['output_tokens_per_user']==identity['output_limit']) or (not r['full_output_budget'] and not r['stop']):
                raise ValueError('short output without EOS')
            if not r['finite_frontiers'] or not r['identical_input_peers_verified']:
                raise ValueError('unverified frontier or peers')
            if identity.get('execution')=='LIE-reactive-ready-batch':
                calls=r['output_tokens_per_user']+int(bool(r['stop']))
                # Emitted final tokens and zero-emission EOS are both allowed;
                # the homogeneous fixture completes every peer in the same step.
                counters=[r.get(k) for k in ('decode_single_calls','decode_batches','decode_batch_rows')]
                if any(type(v) is not int or v<0 for v in counters):raise ValueError('invalid reactive dispatch counters')
                single,batches,batch_rows=counters
                if single+batches not in (r['output_tokens_per_user'],calls):raise ValueError('reactive completed dispatch count')
                if r['users']==1 and (batches or batch_rows):raise ValueError('unexpected single-user batch')
                if r['users']>1 and (single or batch_rows!=batches*r['users']):raise ValueError('unconfirmed batch rows')
            for key,numerator,elapsed in [('prefill_tps',r['prefill_tokens_per_user']*r['users'],r['prefill_ns']),('decode_tps',r['output_tokens'],r['decode_ns'])]:
                if type(elapsed) is not int or elapsed<=0 or not math.isfinite(r[key]) or not math.isclose(r[key],numerator*1e9/elapsed,rel_tol=1e-12):
                    raise ValueError('invalid timing/rate')
            for key in ['prefill_logits_sha256','decode_logits_sha256','output_ids','output_tokens_per_user','stop']:
                if r[key]!=group[0][key]:raise ValueError('repeatability mismatch')
        measured=[r for r in group if not r['warmup']]
        entry={k:p[k] for k in ['point','depth','users','context_capacity','prompt_tokens','physical_ids_sha256']}
        entry.update(repetitions=len(measured),full_output_budget=all(r['full_output_budget'] for r in measured),
                     output_ids=measured[0]['output_ids'],prefill_logits_sha256=measured[0]['prefill_logits_sha256'],decode_logits_sha256=measured[0]['decode_logits_sha256'])
        for key in ['prefill_tps','decode_tps']:
            values=[r[key] for r in measured]
            entry[key]={'median':statistics.median(values),'min':min(values),'max':max(values),'all':values}
        result.append(entry)
    if not inputs and identity['suite']!='loading':raise ValueError('no workload inputs')
    if samples and len(samples)!=len(inputs)*(identity['warmups']+identity['repetitions']):raise ValueError('unbound sample')
    return {'identity':identity,'source':str(Path(path).resolve()),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'configurations':result,'loading':[r for r in rows if r['event']=='model_loaded']}


def compare(a,b):
    if a['identity']['synthetic']!=b['identity']['synthetic']:
        raise ValueError('cannot compare CPU fixtures with model inference')
    if a['identity']['suite']!=b['identity']['suite'] or a['identity']['output_limit']!=b['identity']['output_limit']:
        raise ValueError('comparison suite/output mismatch')
    other={(r['depth'],r['users'],r['prompt_tokens']):r for r in b['configurations']}
    comparisons=[]
    for r in a['configurations']:
        q=other.get((r['depth'],r['users'],r['prompt_tokens']))
        if q is None:raise ValueError('comparison point missing')
        if (r['context_capacity'],r['physical_ids_sha256'])!=(q['context_capacity'],q['physical_ids_sha256']):
            raise ValueError('comparison capacity/physical prompt mismatch')
        equal=r['output_ids']==q['output_ids']
        eligible=bool(equal and r['full_output_budget'] and q['full_output_budget'])
        comparisons.append({'depth':r['depth'],'users':r['users'],'tokens_equal':equal,'full_output_budget':bool(r['full_output_budget'] and q['full_output_budget']),
                            'pp_frontier_equal':r['prefill_logits_sha256']==q['prefill_logits_sha256'],'tg_frontier_equal':r['decode_logits_sha256']==q['decode_logits_sha256'],
                            'eligible':eligible,'decode_ratio':r['decode_tps']['median']/q['decode_tps']['median'] if eligible else None})
    if len(other)!=len(comparisons):raise ValueError('comparison has extra points')
    return comparisons


def export(result,out,label,reference=None,reference_label='Gufo reference'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    summary={'primary':result,'reference':reference,'comparison':compare(result,reference) if reference else None}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['label','depth','users','context_capacity','prompt_tokens','repetitions','full_output_budget','pp_median_tps','pp_min_tps','pp_max_tps','tg_median_tps','tg_min_tps','tg_max_tps'])
        for name,data in [(label,result)]+([(reference_label,reference)] if reference else []):
            for r in data['configurations']:writer.writerow([name,*[r[k] for k in ['depth','users','context_capacity','prompt_tokens','repetitions','full_output_budget']],*[r[metric][stat] for metric in ['prefill_tps','decode_tps'] for stat in ['median','min','max']]])
    # Explicit paths keep matplotlib cache private; no install, device opens or tuning.
    os.environ.setdefault('MPLCONFIGDIR',str(out/'matplotlib-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    suite=result['identity']['suite']
    if suite=='loading':
        fig,ax=plt.subplots(figsize=(6,4),layout='constrained')
        series=[(label,result)]+([(reference_label,reference)] if reference else [])
        ax.bar([name for name,_ in series],[statistics.median(r['model_load_ns']/1e9 for r in data['loading']) for _,data in series]);ax.set_ylabel('Model load seconds (OS cache uncontrolled)')
        fig.suptitle('AR model loading — excludes HTTP readiness, not cold-file loading')
    else:
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        for name,data in [(label,result)]+([(reference_label,reference)] if reference else []):
            rows=data['configurations'];x=[r['users'] if suite=='multi' else r['prompt_tokens'] if suite=='fresh' else r['depth'] for r in rows]
            for ax,key,title in [(axes[0],'prefill_tps','Aggregate new prefill tokens/s'),(axes[1],'decode_tps','Aggregate confirmed decode tokens/s')]:
                values=[r[key] for r in rows];y=[v['median'] for v in values]
                ax.errorbar(x,y,yerr=[[v['median']-v['min'] for v in values],[v['max']-v['median'] for v in values]],marker='o',capsize=4,label=name)
                ax.set_ylabel(title);ax.set_xlabel('Users' if suite=='multi' else 'Full physical prompt tokens' if suite=='fresh' else 'Reused physical prefix tokens');ax.grid(alpha=.25);ax.legend()
                for xx,yy,r in zip(x,y,rows):
                    if not r['full_output_budget']:ax.annotate('early EOS',(xx,yy),fontsize=8)
        scope='CPU fixture — NOT-INFERENCE' if result['identity']['synthetic'] else 'Simplified direct GPU executor'
        pp='full prompt' if suite=='fresh' else '2048 / 4096' if suite=='memory' else str(result['identity']['pp_target'])
        capacities=','.join(str(n) for n in sorted({r['context_capacity'] for r in result['configurations']}))
        fig.suptitle(f'{scope} — {suite}, AR, greedy, capacity {capacities}\nPP {pp} / TG {result["identity"]["output_limit"]} · n={result["identity"]["repetitions"]} · median and observed min/max · no HTTP')
    fig.savefig(out/'benchmark.svg');fig.savefig(out/'benchmark.png',dpi=160);plt.close(fig)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input');parser.add_argument('--output',required=True);parser.add_argument('--label',default='LIE');parser.add_argument('--compare');parser.add_argument('--reference-label',default='Gufo reference')
    args=parser.parse_args()
    result=read_result(args.input);reference=read_result(args.compare) if args.compare else None
    export(result,args.output,args.label,reference,args.reference_label)
    print(json.dumps({'output':str(Path(args.output).resolve()),'artifacts':['summary.json','summary.csv','benchmark.svg','benchmark.png']}))

if __name__=='__main__':main()
