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
state_rows=[];job_rows=[];summary=[];failed=[]
for arm in manifest['arms']:
    path=root/arm['id']/'results/result.json'
    if not path.exists():continue
    receipt=json.loads(path.read_text())
    if receipt['state']!='SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION':
        failed.append({'arm':arm['id'],'error':receipt.get('error'),'exit':receipt.get('child_exit_code')});continue
    result=report['read_result'](path.with_name('measurements.jsonl'))
    telemetry=[json.loads(line) for line in path.with_name('telemetry.jsonl').read_text().splitlines()]
    peaks={}
    for row in telemetry:
        for sensor in row['temperatures']:peaks[sensor['name']]=max(peaks.get(sensor['name'],-40),sensor['value_c'])
    threads=sorted({int(row['process']['Threads']) for row in telemetry if 'Threads' in row['process']})
    summary.append({'arm':arm['id'],'peak_c':peaks,'sampled_threads_including_loader':threads})
    if arm.get('state'):
        ssd=result['ssd'];transfer=result['ssd_transfer'];p=result['input']
        row={'arm':arm['id'],'mode':ssd['mode'],'prompt_tokens':p['prompt_tokens'],'checkpoint_tokens':p['checkpoint_tokens'],
             'model_load_ms':ssd['model_load_ns']/1e6,'identity_hash_ms':ssd['identity_ns']/1e6,
             'retained_bytes':result['capture']['retained_bytes'],'peak_staging_bytes':transfer['peak_staging_bytes'],
             'capture_ms':result['capture'].get('capture_ns',0)/1e6,'write_ms':transfer.get('write_ns',0)/1e6,
             'read_ms':transfer.get('read_ns',0)/1e6,'pairs':len(result['pairs'])}
        for key in ('fresh_prefill_ns','restore_ns','tail_prefill_ns'):
            row[key.replace('_ns','_median_ms')]=statistics.median(p[key] for p in result['pairs'])/1e6 if result['pairs'] else None
        state_rows.append(row)
    else:
        raw=[json.loads(line) for line in path.with_name('measurements.jsonl').read_text().splitlines()]
        load=next(r['load_to_ready_ns']/1e6 for r in raw if r['event']=='core_ready')
        for j in result['jobs']:
            row={k:j[k] for k in ('rep','warmup','prompt_tokens','prefill_tokens','cached_tokens','ssd_cached_tokens','output_tokens','finish')}
            row.update(arm=arm['id'],policy=arm['policy'],load_to_ready_ms=load)
            for key in ('prefill_ns','decode_ns','cache_capture_ns','cache_restore_ns','ssd_read_ns','first_token_ns','total_ns'):
                row[key.replace('_ns','_ms')]=None if j[key] is None else j[key]/1e6
            row['executed_pp_tps']=j['prefill_tokens']*1e9/j['prefill_ns'] if j['prefill_tokens'] and j['prefill_ns'] else None
            row['executor_tg_tps']=j['output_tokens']*1e9/j['decode_ns'] if j['decode_ns'] else None
            row['output_per_total_wall_tps']=j['output_tokens']*1e9/j['total_ns']
            job_rows.append(row)
for name,rows in [('state',state_rows),('jobs',job_rows)]:
    if rows:
        with (out/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
result={'scope':'Matched same-provider SSD checkpoint qualification; OS file cache uncontrolled; state pairs are correctness, core timings include distinct policy costs',
        'campaign_state':campaign['state'],'state':state_rows,'jobs':job_rows,'resources':summary,'failed':failed,
        'postflight':json.loads((root/'postflight.json').read_text())}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
if job_rows:
    import os
    os.environ['MPLCONFIGDIR']=str(out/'matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    groups={}
    for row in job_rows:
        if not row['warmup']:groups.setdefault((row['prompt_tokens'],row['policy']),[]).append(row)
    keys=list(groups);labels=[str(n)+'\n'+policy for n,policy in keys]
    for ax,key,title in [(axes[0],'first_token_ms','Core TTFT (ms)'),(axes[1],'cache_restore_ms','Owner checkpoint upload (ms)')]:
        ax.bar(labels,[statistics.median(r[key] for r in groups[k]) for k in keys]);ax.set_ylabel(title);ax.tick_params(axis='x',labelrotation=35);ax.grid(axis='y',alpha=.25)
    fig.suptitle('C1 AR SSD restart — matched inputs, distinct cache policies\nModel loading/full identity excluded; OS file cache uncontrolled')
    fig.savefig(out/'ssd-restart.svg');fig.savefig(out/'ssd-restart.png',dpi=160);plt.close(fig)
print(json.dumps({'state_arms':len(state_rows),'core_jobs':len(job_rows),'failed':failed}))
