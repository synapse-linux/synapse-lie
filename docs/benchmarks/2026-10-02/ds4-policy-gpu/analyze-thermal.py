# SPDX-License-Identifier: MIT
"""Offline sampled temperatures, clock observations and completed-job rates."""
from pathlib import Path
import csv
import hashlib
import json
import os
import re
import statistics
import sys

source=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
raw=[json.loads(line) for line in source.read_text().splitlines()]
records=[r['remote'] for r in raw if 'remote' in r]
end=[r for r in raw if r.get('event')=='connection_closed']
if not records or len(end)!=1:raise SystemExit('Observer has not closed; preserve incomplete data separately')
base=records[0]['remote_monotonic_s'];samples=[];jobs=[]
for r in records:
    temps={t['name']:int(t['raw_millic'])/1000 for t in r['temperatures']
           if t['name'] in ('amdgpu','k10temp') and t['raw_millic'] is not None}
    nvme=[int(t['raw_millic'])/1000 for t in r['temperatures'] if t['name']=='nvme' and t['label']=='Composite' and t['raw_millic'] is not None]
    nvme_all=[int(t['raw_millic'])/1000 for t in r['temperatures'] if t['name']=='nvme' and t['raw_millic'] is not None]
    gpu=r['gpu'][0] if r['gpu'] else {};clock=re.search(r'\d+:\s*(\d+)Mhz\s*\*',gpu.get('pp_dpm_sclk') or '')
    arm=(r.get('campaign') or {}).get('current_arm')
    row={'elapsed_s':r['remote_monotonic_s']-base,'at':r['at'],'arm':arm,
         'cpu_c':temps.get('k10temp'),'gpu_c':temps.get('amdgpu'),
         'nvme_composite_c':max(nvme) if nvme else None,
         'nvme_hottest_sensor_c':max(nvme_all) if nvme_all else None,
         'gpu_active_sclk_mhz':int(clock[1]) if clock else None,
         'cpu_max_reported_mhz':max(r['cpu_mhz']) if r['cpu_mhz'] else None,
         'gpu_busy_percent':int(gpu['gpu_busy_percent']) if gpu.get('gpu_busy_percent') is not None else None}
    samples.append(row)
    for e in r['benchmark_events']:
        if 'prefill_ns' not in e or 'decode_ns' not in e or 'output_tokens' not in e:continue
        jobs.append({'observed_elapsed_s':row['elapsed_s'],'arm':arm,'rep':e.get('rep'),'warmup':e.get('warmup'),
                     'gpu_c_at_observation':row['gpu_c'],'cpu_c_at_observation':row['cpu_c'],
                     'prefill_tps':e['prefill_tokens']*1e9/e['prefill_ns'] if e.get('prefill_tokens') and e['prefill_ns'] else None,
                     'decode_tps':e['output_tokens']*1e9/e['decode_ns'] if e['decode_ns'] else None,
                     'output_tokens':e['output_tokens'],'first_token_ms':e['first_token_ns']/1e6 if e.get('first_token_ns') is not None else None})

def threshold(key,limit):
    active=[];runs=[]
    for r in samples:
        if r[key] is not None and r[key]>=limit:
            if active and r['elapsed_s']-active[-1]>2.5:runs.append(active);active=[]
            active.append(r['elapsed_s'])
        elif active:runs.append(active);active=[]
    if active:runs.append(active)
    brackets=[]
    for run in runs:
        before=[r for r in samples if r['elapsed_s']<run[0] and r[key] is not None and r[key]<limit]
        after=[r for r in samples if r['elapsed_s']>run[-1] and r[key] is not None and r[key]<limit]
        if before and after:brackets.append(after[0]['elapsed_s']-before[-1]['elapsed_s'])
    return {'at_or_above_c':limit,'samples':sum(len(r) for r in runs),
            'longest_consecutive_samples':max((len(r) for r in runs),default=0),
            'longest_observed_span_s':max((r[-1]-r[0] for r in runs),default=0),
            'bracketed_episodes':len(brackets),'total_episodes':len(runs),
            'longest_below_threshold_bracket_s':max(brackets,default=None)}

summary={'scope':'1 Hz read-only telemetry during SSD qualification; received samples persisted on editing host. No fan RPM exposed. Clocks are reported snapshots, not an independent thermal-throttling detector.',
         'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'samples':len(samples),
         'duration_s':samples[-1]['elapsed_s'],'boot_ids':sorted({r['boot_id'] for r in records}),
         'last_campaign':records[-1].get('campaign'),
         'max_sample_gap_s':max((b['elapsed_s']-a['elapsed_s'] for a,b in zip(samples,samples[1:])),default=0),
         'observer_exit':end[0],'temperatures':{},'jobs':jobs,
         'timing_limit':'Threshold spans are bounded by observed sample timestamps, with gaps over 2.5 s split. Completed-job rates are associated with receipt time, up to sampling/delivery delay after completion. Events at arm transitions may be missed: full benchmark files are authoritative. A connection loss alone does not prove a crash.'}
for key in ('cpu_c','gpu_c','nvme_composite_c','nvme_hottest_sensor_c'):
    vals=[r for r in samples if r[key] is not None]
    top=max(vals,key=lambda r:r[key])
    summary['temperatures'][key]={'max_c':top[key],'peak_first_at':top['at'],
        'thresholds':[threshold(key,n) for n in ((95,98,99,100) if not key.startswith('nvme_') else (75,80,82.85,85))]}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for name,rows in [('samples',samples),('jobs',jobs)]:
    if not rows:continue
    with (out/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
os.environ['MPLCONFIGDIR']=str(out/'matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(4,1,figsize=(13,12),sharex=True,layout='constrained')
x=[r['elapsed_s']/60 for r in samples]
for key,name in [('cpu_c','CPU Tctl'),('gpu_c','GPU edge'),('nvme_composite_c','NVMe composite'),('nvme_hottest_sensor_c','NVMe hottest sensor')]:
    axes[0].plot(x,[r[key] for r in samples],label=name,lw=1)
axes[0].axhline(98,color='gray',ls=':',label='Earlier software ceiling (disabled for CPU/GPU)')
axes[0].set_ylabel('Temperature (C)');axes[0].legend(loc='lower left')
for key,name in [('gpu_active_sclk_mhz','GPU reported active SCLK'),('cpu_max_reported_mhz','Maximum reported CPU MHz')]:
    axes[1].plot(x,[r[key] for r in samples],label=name,lw=.8)
axes[1].set_ylabel('Reported clock (MHz)');axes[1].legend(loc='lower left')
axes[2].plot(x,[r['gpu_busy_percent'] for r in samples],lw=.8);axes[2].set_ylabel('GPU busy (%)')
tg=axes[3].twinx()
for ax,key,label,color in [(axes[3],'prefill_tps','Executed PP','tab:blue'),(tg,'decode_tps','Executor TG','tab:orange')]:
    points=[r for r in jobs if r[key] is not None and not r['warmup']]
    ax.scatter([r['observed_elapsed_s']/60 for r in points],[r[key] for r in points],color=color,label=label,s=24)
    ax.set_ylabel(label+' (tok/s)',color=color)
axes[3].set_xlabel('Minutes from first received remote sample')
previous=None
for r in samples:
    if r['arm'] and r['arm']!=previous:
        for ax in axes:ax.axvline(r['elapsed_s']/60,color='gray',alpha=.15,lw=.8)
        previous=r['arm']
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Strix Halo .157 — SSD campaign, fan mode reported as dynamic by owner\nNo hardware settings changed; load/hash, state checks and core requests have distinct phases')
fig.savefig(out/'thermal-timeline.svg');fig.savefig(out/'thermal-timeline.png',dpi=150);plt.close(fig)
svg=out/'thermal-timeline.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print(json.dumps({'samples':len(samples),'duration_s':summary['duration_s'],'peaks':{k:v['max_c'] for k,v in summary['temperatures'].items()},'observed_jobs':len(jobs),'ssh_exit':end[0]['ssh_exit_code']}))
