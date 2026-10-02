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
    if rows and rows[0].get('schema')=='synapse-lie.state-bench.v1':
        return read_state_result(path,rows)
    if rows and rows[0].get('schema')=='synapse-lie.core-bench.v1':
        return read_core_result(path,rows)
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
    if a['identity']['suite']=='state' or b['identity']['suite']=='state':
        raise ValueError('state qualification uses paired exact frontiers, not performance ranking')
    if a['identity']['suite']=='core' or b['identity']['suite']=='core':
        return compare_core(a,b)
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
    if result['identity']['suite']=='core':
        return export_core(result,out,label,reference,reference_label)
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


def distribution(values):
    return {'median':statistics.median(values),'min':min(values),'max':max(values),'all':values} if values else None


def read_state_result(path,rows):
    if [r.get('event') for r in rows]!=['identity','input','capture','pair','pair','pair','complete'] or rows[-1]!={'event':'complete','exit_code':0}:
        raise ValueError('incomplete state qualification')
    identity,p,capture=rows[:3];pairs=rows[3:6]
    if identity.get('suite')!='state' or identity.get('state_abi')!=1 or not 0<p['checkpoint_tokens']<=p['prompt_tokens']<p['context']:
        raise ValueError('invalid state input')
    if p['checkpoint_tokens']!=p['prompt_tokens'] and p['checkpoint_tokens']%p['chunk']:
        raise ValueError('state chunk alignment')
    if not 0<capture['retained_bytes']<=4*1024**3 or not 0<capture['sections']<=256 or capture['capture_ns']<=0:
        raise ValueError('state capture accounting')
    for index,r in enumerate(pairs):
        if r['pair']!=index or r['exact_logits_and_tokens']!=1 or r['reused_tokens']!=p['checkpoint_tokens'] or r['new_tokens']+r['reused_tokens']!=p['prompt_tokens']:
            raise ValueError('state pair accounting')
        if not 0<r['decode_calls']<=16 or not 0<=len(r['output_ids'])<=r['decode_calls'] or len(r['full_logits_sha256'])!=64:
            raise ValueError('state frontier witness')
        if any(type(r[k]) is not int or r[k]<0 for k in ('fresh_prefill_ns','restore_ns','tail_prefill_ns')) or not r['fresh_prefill_ns'] or not r['restore_ns']:
            raise ValueError('state pair timing')
    for key in ('output_ids','full_logits_sha256'):
        if pairs[0][key]!=pairs[2][key]:raise ValueError('independent clone drift')
    return {'identity':identity,'source':str(Path(path).resolve()),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'input':p,'capture':capture,'pairs':pairs}


def read_core_result(path,rows):
    if rows[-1]!={'event':'complete','exit_code':0}:
        raise ValueError('incomplete/failed core benchmark')
    identity=rows[0]
    if identity.get('suite')!='core' or identity.get('execution')!='shared-reactive-core':
        raise ValueError('invalid core benchmark identity')
    users=identity['users'];reps=identity['warmups']+identity['repetitions']
    cache_policy=identity.get('cache_policy','off');cache_budget=identity.get('prefix_cache_bytes',0)
    ram=cache_policy in ('ram','ram+ssd');ssd=cache_policy in ('ssd','ram+ssd')
    if cache_policy not in ('off','ram','ssd','ram+ssd') or type(cache_budget) is not int or cache_budget<0 or ram!=(cache_budget>0):raise ValueError('core cache declaration')
    for key in ('ssd_quota_bytes','ssd_staging_bytes'):
        value=identity.get(key,0)
        if type(value) is not int or value<0 or ssd!=(value>0):raise ValueError('core SSD declaration')
    if not 1<=users<=8 or identity['warmups']<0 or identity['repetitions']<1:
        raise ValueError('invalid core sample configuration')
    inputs=[r for r in rows if r['event']=='input']
    samples=[r for r in rows if r['event']=='sample'];jobs=[r for r in rows if r['event']=='job']
    if len(inputs)!=1 or len(samples)!=reps or len(jobs)!=reps*users or [r['rep'] for r in samples]!=list(range(reps)):
        raise ValueError('missing/duplicate core samples')
    p=inputs[0]
    if not p['physical_ids'] or len(p['physical_ids'])!=p['prompt_tokens'] or p['prompt_tokens']+identity['output_limit']>identity['context_capacity']:
        raise ValueError('core physical input count/capacity')
    if any(type(i) is not int or i<0 or i>2147483647 for i in p['physical_ids']):
        raise ValueError('core physical input IDs')
    packed=b''.join(i.to_bytes(4,'little',signed=True) for i in p['physical_ids'])
    if hashlib.sha256(packed).hexdigest()!=p['physical_ids_sha256']:
        raise ValueError('core physical input hash')
    for sample in samples:
        rep=sample['rep'];group=[r for r in jobs if r['rep']==rep]
        if [r['user'] for r in group]!=list(range(users)) or sample['users']!=users or sample['warmup']!=int(rep<identity['warmups']):
            raise ValueError('core peer/warmup drift')
        for r in group:
            cached=r.get('cached_tokens',0)
            if type(cached) is not int or not 0<=cached<=p['prompt_tokens'] or (cache_policy=='off' and cached):raise ValueError('core cached token count')
            disk=r.get('ssd_cached_tokens',0);read_ns=r.get('ssd_read_ns',0)
            if type(disk) is not int or not 0<=disk<=cached or (not ssd and disk) or (not ram and disk!=cached):raise ValueError('core SSD reused token count')
            if type(read_ns) is not int or read_ns<0 or (not ssd and read_ns):raise ValueError('core SSD read timing')
            if cached!=p['prompt_tokens'] and cached%identity['prefill_chunk']:raise ValueError('unaligned reused prefix')
            if r['warmup']!=sample['warmup'] or r['prompt_tokens']!=p['prompt_tokens'] or r['prefill_tokens']+cached!=p['prompt_tokens']:
                raise ValueError('core prefill accounting')
            for key in ['output_tokens','output_bytes','prefill_ns','decode_ns','prefill_calls','decode_calls','total_ns']:
                if type(r[key]) is not int or r[key]<0:raise ValueError('core timing/count type')
            for key in ['cache_capture_ns','cache_restore_ns']:
                value=r.get(key,0)
                if type(value) is not int or value<0 or (cache_policy=='off' and value):raise ValueError('core cache timing')
            if not r['prefill_tokens'] and (r['prefill_ns'] or r['prefill_calls']):raise ValueError('cached prefill double counting')
            if r['total_ns']<=0 or not 0<=r['output_tokens']<=identity['output_limit'] or len(r['output_ids'])!=r['output_tokens']:
                raise ValueError('core output count')
            if any(type(i) is not int or i<0 or i>2147483647 for i in r['output_ids']):raise ValueError('core output IDs')
            if r['finish'] not in ('stop','length') or (r['finish']=='length' and r['output_tokens']!=identity['output_limit']):
                raise ValueError('core completion reason')
            first=r['first_token_ns']
            if (r['output_tokens']==0 and first is not None) or (r['output_tokens']>0 and (type(first) is not int or not 0<=first<=r['total_ns'])):
                raise ValueError('core first-token timing')
            if r['output_ids']!=jobs[0]['output_ids']:raise ValueError('core greedy output drift')
        if ram:
            hits=sum(r.get('cached_tokens',0)>0 and not r.get('ssd_cached_tokens',0) for r in group)
            if sample.get('cache_hits')!=hits or sample.get('cache_misses')!=users-hits or sample.get('cache_budget_bytes')!=cache_budget or not 0<=sample.get('cache_retained_bytes',-1)<=cache_budget:raise ValueError('core cache cohort accounting')
        elapsed=sample['wall_ns'];tokens=sum(r['output_tokens'] for r in group)
        if type(elapsed) is not int or elapsed<=0 or sample['output_tokens']!=tokens or not math.isfinite(sample['output_per_total_wall_tps']) or not math.isclose(sample['output_per_total_wall_tps'],tokens*1e9/elapsed,rel_tol=1e-12):
            raise ValueError('core common-window accounting')
        for key in ['decode_batches','decode_batch_rows','decode_single_calls']:
            if type(sample[key]) is not int or sample[key]<0:raise ValueError('core dispatch count')
        if not 2*sample['decode_batches']<=sample['decode_batch_rows']<=users*sample['decode_batches']:
            raise ValueError('core batch width accounting')
    measured=[r for r in jobs if not r['warmup']]
    point={k:identity[k] for k in ['users','context_capacity','prefill_chunk','input_kind','output_limit','repetitions']}
    point.update(cache_policy=cache_policy,prefix_cache_bytes=cache_budget,
        ssd_quota_bytes=identity.get('ssd_quota_bytes',0),ssd_staging_bytes=identity.get('ssd_staging_bytes',0),
        ssd_cached_tokens=distribution([r.get('ssd_cached_tokens',0) for r in measured]),
        ssd_read_ns=distribution([r.get('ssd_read_ns',0) for r in measured]),
        cached_tokens=distribution([r.get('cached_tokens',0) for r in measured]),
        cache_capture_ns=distribution([r.get('cache_capture_ns',0) for r in measured]),
        cache_restore_ns=distribution([r.get('cache_restore_ns',0) for r in measured]),
        prompt_tokens=p['prompt_tokens'],physical_ids_sha256=p['physical_ids_sha256'],output_ids=jobs[0]['output_ids'],
        full_output_budget=all(r['output_tokens']==identity['output_limit'] for r in measured),
        first_token_ns=distribution([r['first_token_ns'] for r in measured if r['first_token_ns'] is not None]),
        total_ns=distribution([r['total_ns'] for r in measured]),
        job_prefill_tps=distribution([r['prefill_tokens']*1e9/r['prefill_ns'] for r in measured if r['prefill_ns']]),
        output_per_total_wall_tps=distribution([r['output_per_total_wall_tps'] for r in samples if not r['warmup']]))
    return {'identity':identity,'source':str(Path(path).resolve()),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'configurations':[point],'jobs':jobs,'samples':samples,'loading':[r for r in rows if r['event']=='core_ready']}


def compare_core(a,b):
    if a['identity']['suite']!='core' or b['identity']['suite']!='core' or a['identity']['synthetic']!=b['identity']['synthetic']:
        raise ValueError('core scope/provider-kind mismatch')
    p=a['configurations'][0];q=b['configurations'][0]
    for k in ['users','context_capacity','prefill_chunk','input_kind','output_limit','physical_ids_sha256','cache_policy','prefix_cache_bytes','ssd_quota_bytes','ssd_staging_bytes']:
        if p[k]!=q[k]:raise ValueError('core comparison input/settings mismatch')
    equal=p['output_ids']==q['output_ids'];eligible=equal and p['full_output_budget'] and q['full_output_budget']
    denominator=q['output_per_total_wall_tps']['median']
    return [{'tokens_equal':equal,'eligible':eligible,
        'output_per_total_wall_ratio':p['output_per_total_wall_tps']['median']/denominator if eligible and denominator else None}]


def export_core(result,out,label,reference,reference_label):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    summary={'primary':result,'reference':reference,'comparison':compare_core(result,reference) if reference else None}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    series=[(label,result)]+([(reference_label,reference)] if reference else [])
    with (out/'summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['label','users','prompt_tokens','repetitions','job_prefill_median_tps','output_per_total_wall_median_tps','first_token_median_ms','total_median_ms','cache_policy','cached_tokens_median','cache_capture_median_ms','cache_restore_median_ms','ssd_cached_tokens_median','ssd_read_median_ms'])
        for name,data in series:
            r=data['configurations'][0]
            value=lambda key,scale=1:r[key]['median']*scale if r[key] is not None else None
            writer.writerow([name,r['users'],r['prompt_tokens'],r['repetitions'],value('job_prefill_tps'),value('output_per_total_wall_tps'),value('first_token_ns',1e-6),value('total_ns',1e-6),r['cache_policy'],value('cached_tokens'),value('cache_capture_ns',1e-6),value('cache_restore_ns',1e-6),value('ssd_cached_tokens'),value('ssd_read_ns',1e-6)])
    os.environ.setdefault('MPLCONFIGDIR',str(out/'matplotlib-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for ax,key,scale,title in zip(axes,['job_prefill_tps','output_per_total_wall_tps','first_token_ns'],[1,1,1e-6],
            ['Per-job executor prefill tok/s','Aggregate output / complete wall tok/s','Client first confirmed token, ms']):
        for x,(name,data) in enumerate(series):
            v=data['configurations'][0][key]
            if v is None:
                ax.text(x,.5,'no executed prefill' if key=='job_prefill_tps' else 'unavailable',
                        ha='center',va='center',transform=ax.get_xaxis_transform())
                continue
            ax.bar(x,v['median']*scale,yerr=[[max(0,v['median']-v['min'])*scale],[max(0,v['max']-v['median'])*scale]],capsize=4)
        ax.set_xticks(range(len(series)),[name for name,_ in series]);ax.set_ylabel(title);ax.grid(axis='y',alpha=.25)
        ax.set_xlim(-.5,len(series)-.5)
        if all(data['configurations'][0][key] is None for _,data in series):ax.set_yticks([])
    scope='CPU fixture — NOT-INFERENCE' if result['identity']['synthetic'] else 'Shared reactive C core'
    r=result['configurations'][0]
    fig.suptitle(f'{scope} · {r["users"]} users · {r["prompt_tokens"]} prompt tokens · n={r["repetitions"]}\nCache: {r["cache_policy"]}; no HTTP; per-job executor calls and client wall have different scopes')
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
