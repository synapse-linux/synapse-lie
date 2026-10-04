#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline campaign evidence tables. Never average failed or incomplete arms."""
import csv
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import sys

root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
report=runpy.run_path(str(root/'bench-report.py'))
manifest=json.loads((root/'suite-manifest.json').read_text())
campaign=json.loads((root/'state.json').read_text())
inventory=json.loads((root/'collection-sha256.json').read_text())
for path,expected in inventory.items():
    if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:raise SystemExit('Unverified evidence: '+path)
state_rows=[];job_rows=[];summary=[];failed=[];not_run=[];state_pairs=[];identities=[];drains=[]
for arm in manifest['arms']:
    path=root/arm['id']/'results/result.json'
    if not path.exists():not_run.append(arm['id']);continue
    receipt=json.loads(path.read_text())
    if receipt['state']!='SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION':
        failed.append({'arm':arm['id'],'error':receipt.get('error'),'exit':receipt.get('child_exit_code')});continue
    result=report['read_result'](path.with_name('measurements.jsonl'))
    identities.append({'arm':arm['id'],'identity':result['identity'],'measurement_sha256':hashlib.sha256(path.with_name('measurements.jsonl').read_bytes()).hexdigest()})
    telemetry=[json.loads(line) for line in path.with_name('telemetry.jsonl').read_text().splitlines()]
    peaks={}
    for row in telemetry:
        for sensor in row['temperatures']:peaks[sensor['name']]=max(peaks.get(sensor['name'],-40),sensor['value_c'])
    threads=sorted({int(row['process']['Threads']) for row in telemetry if 'Threads' in row['process']})
    summary.append({'arm':arm['id'],'peak_c':peaks,'sampled_threads_including_loader':threads})
    if arm.get('state'):
        ssd=result['ssd'];transfer=result['ssd_transfer'];p=result['input']
        row={'arm':arm['id'],'mode':ssd['mode'],'prompt_tokens':p['prompt_tokens'],'checkpoint_tokens':p['checkpoint_tokens'],'prefill_chunk':p['chunk'],
             'model_load_ms':ssd['model_load_ns']/1e6,'identity_hash_ms':ssd['identity_ns']/1e6,
             'retained_bytes':result['capture']['retained_bytes'],'peak_staging_bytes':transfer['peak_staging_bytes'],
             'capture_ms':result['capture'].get('capture_ns',0)/1e6,'write_ms':transfer.get('write_ns',0)/1e6,
             'read_ms':transfer.get('read_ns',0)/1e6,'pairs':len(result['pairs']),
             'transfer_bytes':transfer.get('read_bytes',transfer.get('written_bytes')),
             'min_decode_calls':min((p['decode_calls'] for p in result['pairs']),default=None),
             'min_output_tokens':min((len(p['output_ids']) for p in result['pairs']),default=None)}
        state_pairs.extend(dict(arm=arm['id'],**p) for p in result['pairs'])
        for key in ('fresh_prefill_ns','restore_ns','tail_prefill_ns'):
            row[key.replace('_ns','_median_ms')]=statistics.median(p[key] for p in result['pairs'])/1e6 if result['pairs'] else None
        state_rows.append(row)
    else:
        raw=[json.loads(line) for line in path.with_name('measurements.jsonl').read_text().splitlines()]
        load=next(r['load_to_ready_ns']/1e6 for r in raw if r['event']=='core_ready')
        drains.extend(dict(arm=arm['id'],**r) for r in raw if r['event']=='ssd_drained')
        for j in result['jobs']:
            row={k:j[k] for k in ('rep','warmup','prompt_tokens','prefill_tokens','cached_tokens','ssd_cached_tokens','output_tokens','finish')}
            row.update(arm=arm['id'],policy=arm['policy'],prefill_chunk=result['identity']['prefill_chunk'],load_to_ready_ms=load)
            for key in ('prefill_ns','decode_ns','cache_capture_ns','cache_restore_ns','ssd_read_ns','first_token_ns','total_ns'):
                row[key.replace('_ns','_ms')]=None if j[key] is None else j[key]/1e6
            row['executed_pp_tps']=j['prefill_tokens']*1e9/j['prefill_ns'] if j['prefill_tokens'] and j['prefill_ns'] else None
            row['executor_tg_tps']=j['output_tokens']*1e9/j['decode_ns'] if j['decode_ns'] else None
            row['output_per_total_wall_tps']=j['output_tokens']*1e9/j['total_ns']
            job_rows.append(row)
for name,rows in [('state',state_rows),('jobs',job_rows)]:
    if rows:
        with (out/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
result={'scope':'Matched same-provider SSD checkpoint qualification; OS file cache uncontrolled; state pairs are correctness, core timings include distinct policy costs',
        'campaign_state':campaign['state'],'state':state_rows,'state_pairs':state_pairs,'jobs':job_rows,'resources':summary,'failed':failed,'not_run':not_run,'identities':identities,'ssd_drains':drains,
        'complete':campaign['state']=='COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS' and not failed and not not_run and len(summary)==len(manifest['arms']),
        'postflight':json.loads((root/'postflight.json').read_text())}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
if job_rows:
    import os
    os.environ['MPLCONFIGDIR']=str(out/'matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    groups={}
    for row in job_rows:
        if not row['warmup']:groups.setdefault((row['prompt_tokens'],row['prefill_chunk'],row['policy']),[]).append(row)
    keys=list(groups);labels=[str(n//1024)+'K\n'+{'off':'Off','ram':'RAM','ssd-write':'SSD\nwrite','ssd-read':'SSD\nread'}[policy] for n,chunk,policy in keys]
    colors={'off':'#526580','ram':'#29834c','ssd-write':'#bc741d','ssd-read':'#347dac'}
    panels=[('executed_pp_tps','Executed prefill (tok/s)'),('executor_tg_tps','Per-job executor decode (tok/s)'),
            ('first_token_ms','Core TTFT (ms, logarithmic)'),('output_per_total_wall_tps','Output / complete job wall (tok/s)'),
            ('ssd_read_ms','SSD lookup, read and validation (ms)'),('cache_restore_ms','Owner restore path (ms)')]
    for ax,(key,title) in zip(axes.flat,panels):
        for x,k in enumerate(keys):
            vals=[r[key] for r in groups[k] if r[key] is not None]
            if not vals:
                ax.text(x,0,'no PP',ha='center',rotation=90,va='bottom');continue
            mid=statistics.median(vals)
            ax.bar(x,mid,yerr=[[mid-min(vals)],[max(vals)-mid]],capsize=3,color=colors[k[2]])
        ax.set_xticks(range(len(keys)),labels);ax.set_ylabel(title);ax.tick_params(axis='x',labelsize=9);ax.grid(axis='y',alpha=.25)
        ax.set_xlim(-.6,len(keys)-.4)
        if key=='first_token_ms':ax.set_yscale('log')
    fig.suptitle('C1 AR SSD restart, TG128, chunk2048 — median and observed min/max; SSD producer n=1, other groups n=3\nFull hits have no executed PP; model load/identity and final durable-write drain excluded from job intervals')
    fig.savefig(out/'ssd-restart.svg');fig.savefig(out/'ssd-restart.png',dpi=160);plt.close(fig)
    svg=out/'ssd-restart.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print(json.dumps({'state_arms':len(state_rows),'core_jobs':len(job_rows),'failed':failed}))
