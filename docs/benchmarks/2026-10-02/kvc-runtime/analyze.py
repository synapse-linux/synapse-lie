# SPDX-License-Identifier: MIT
"""Offline runtime-format comparison; no GPU or model access."""
import csv,json,os,statistics,sys,runpy
from pathlib import Path
roots=[Path(p) for p in sys.argv[1].split(',')];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
report=runpy.run_path(str(Path(__file__).resolve().parent/'bench-report.py'))
entries=[(root,arm) for root in roots for arm in json.loads((root/'suite-manifest.json').read_text())['arms']];arms={};table=[];state=[];comparisons=[];full_jobs=[];full_pairs=[]
median=lambda xs:statistics.median(xs) if xs else None
for root,arm in entries:
 path=root/arm['id']/'results/measurements.jsonl'
 if not path.exists():continue
 rows=[json.loads(line) for line in path.read_text().splitlines()]
 if rows[-1].get('event')!='complete':continue
 data=report['read_result'](path);arms[arm['id']]=data
 if arm['kind']=='state':
  common={'arm':arm['id'],'variant':arm['variant'],**data['input'],**data['capture']}
  for key in ('ssd','ssd_prepare','ssd_transfer'):
   if data[key]:common.update({key+'_'+k:v for k,v in data[key].items() if k!='event'})
  for pair in data['pairs'] or [{}]:full_pairs.append({**common,**pair})
  state.append({'arm':arm['id'],'input':data['input'],'capture':data['capture'],'ssd':data['ssd'],'ssd_prepare':data['ssd_prepare'],'ssd_transfer':data['ssd_transfer'],'pairs':data['pairs']});continue
 jobs=data['jobs'];full_jobs.extend({'arm':arm['id'],'variant':arm['variant'],'users':data['identity']['users'],'context':data['identity']['context_capacity'],**j} for j in jobs);cold=[j for j in jobs if j['warmup'] or arm.get('ssd_store',{}).get('mode')=='create'];hot=[j for j in jobs if j not in cold]
 point=data['configurations'][0];samples=data['samples']
 row={'arm':arm['id'],'format':data['identity']['state_format'],'users':data['identity']['users'],'prompt_tokens':point['prompt_tokens'],'context':point['context_capacity'],'input_kind':point['input_kind'],'cache_tier':point['cache_policy'],'cold_jobs':len(cold),'warm_jobs':len(hot)}
 row['ram_budget_bytes']=data['identity']['prefix_cache_bytes']
 for kind,group in [('cold',cold),('warm',hot)]:
  for field,scale in [('cached_tokens',1),('ssd_cached_tokens',1),('prefill_tokens',1),('prefill_ns',1e-6),('decode_ns',1e-6),('cache_capture_ns',1e-6),('cache_restore_ns',1e-6),('ssd_read_ns',1e-6),('first_token_ns',1e-6),('total_ns',1e-6)]:
   key=field.replace('_ns','_ms');row[kind+'_'+key]=median([j[field]*scale for j in group if j.get(field) is not None])
  row[kind+'_executed_pp_tps']=median([j['prefill_tokens']*1e9/j['prefill_ns'] for j in group if j['prefill_ns']])
  row[kind+'_executor_tg_tps']=median([j['output_tokens']*1e9/j['decode_ns'] for j in group if j['decode_ns']])
 row['warm_cohort_output_wall_tps']=median([s['output_per_total_wall_tps'] for s in samples if not s['warmup']]) if hot else None
 telemetry=[json.loads(line) for line in (path.parent/'telemetry.jsonl').read_text().splitlines()]
 threads=[int(r['process']['Threads']) for r in telemetry if r.get('process',{}).get('Threads')]
 row['sampled_threads_min']=min(threads) if threads else None;row['sampled_threads_max']=max(threads) if threads else None
 active=[int(r['process']['Threads']) for r in telemetry if r.get('process',{}).get('Threads') and str(r.get('gpu',{}).get('gpu_busy_percent','')).isdigit() and int(r['gpu']['gpu_busy_percent'])>=50]
 row['gpu_busy_threads_min']=min(active) if active else None;row['gpu_busy_threads_max']=max(active) if active else None
 for kind,names in [('cpu',('k10temp','coretemp')),('gpu',('amdgpu',))]:
  temps=[t['value_c'] for r in telemetry for t in r.get('temperatures',[]) if t['name'] in names]
  row[kind+'_peak_c']=max(temps) if temps else None
 row['retained_bytes']=samples[-1]['cache_retained_bytes'];row['expanded_bytes']=samples[-1]['cache_expanded_bytes'];row['captures']=sum(s['cache_captures'] for s in samples)
 row['evictions']=sum(s['cache_evictions'] for s in samples)
 row['ssd_writes']=sum(s['ssd_writes'] for s in samples);row['ssd_write_ms']=sum(s['ssd_write_ns'] for s in samples)*1e-6;row['ssd_disk_bytes']=samples[-1]['ssd_disk_bytes']
 table.append(row)
 if arm.get('reference_arm'):
  ref=arms[arm['reference_arm']];comp=report['compare'](data,ref,True)[0];assert comp['eligible'];comp.update(primary=arm['id'],reference=arm['reference_arm']);comparisons.append(comp)
  report['export'](data,out/arm['id'],'DS4 payload',ref,'Legacy components',True)
state_checks=[]
for root,arm in entries:
 if arm.get('state_reference') and arm['id'] in arms:
  a=arms[arm['id']];b=arms[arm['state_reference']]
  fields=('generation','decode_calls','output_ids','full_logits_sha256')
  assert len(a['pairs'])==len(b['pairs'])==3
  assert all(all(p[k]==q[k] for k in fields) for p,q in zip(a['pairs'],b['pairs']))
  state_checks.append({'primary':arm['id'],'reference':arm['state_reference'],'complete_frontiers_exact':True,'pairs':3})
regressions=[]
by_name={r['arm']:r for r in table}
for c in comparisons:
 a,b=by_name[c['primary']],by_name[c['reference']]
 for key,higher in [('warm_executed_pp_tps',True),('warm_executor_tg_tps',True),('warm_cohort_output_wall_tps',True),('warm_first_token_ms',False),('warm_cache_restore_ms',False)]:
  if a[key] is None or not b[key]:continue
  ratio=a[key]/b[key];slower=(ratio<.95) if higher else (ratio>1.05)
  regressions.append({'primary':c['primary'],'reference':c['reference'],'metric':key,'ratio':ratio,'over_5_percent_regression':slower})
summary={'scope':'Paired legacy versus DS4 runtime payload/provider. Same shared reactive core and capture policy; no foreign DS4 checkpoints. One warmup and three measured core cohorts. No causal reactive gain claim.','core':table,'state':state,'comparisons':comparisons,'state_comparisons':state_checks,'regression_checks':regressions}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'summary.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(table[0]),lineterminator='\n');writer.writeheader();writer.writerows(table)
for name,records in [('core-jobs',full_jobs),('state-pairs',full_pairs)]:
 keys=sorted({k for row in records for k in row})
 with (out/(name+'.csv')).open('w',newline='') as f:
  writer=csv.DictWriter(f,keys,lineterminator='\n');writer.writeheader()
  for row in records:writer.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in row.items()})
paired=[c for c in comparisons];by_name={r['arm']:r for r in table}
os.environ.setdefault('MPLCONFIGDIR',str(out/'matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
metrics=[('cold_executed_pp_tps','Cold executed prefill tok/s',1),('warm_executed_pp_tps','Warm remaining prefill tok/s',1),('warm_cached_tokens','Warm reused tokens',1),('warm_first_token_ms','Warm first-token latency ms',1),('warm_executor_tg_tps','Per-job executor TG tok/s',1),('retained_bytes','Retained checkpoint MiB',1/1048576)]
for ax,(field,title,scale) in zip(axes.flat,metrics):
 for role,delta,color in [('reference',-.18,'#72859c'),('primary',.18,'#247f71')]:
  values=[by_name[c[role]][field] for c in paired]
  ax.bar([i+delta for i in range(len(paired))],[v*scale if v is not None else 0 for v in values],width=.34,color=color,label='Legacy' if role=='reference' else 'DS4 payload')
  for i,v in enumerate(values):
   if v is None:ax.text(i+delta,0,'N/A',ha='center',va='bottom',fontsize=8)
 labels=[f"{by_name[c['primary']]['prompt_tokens']} / C{by_name[c['primary']]['users']}\n{by_name[c['primary']]['ram_budget_bytes']/1024**3:g} GiB"+(' text' if by_name[c['primary']]['input_kind']=='raw-text' else '') for c in paired]
 ax.set_xticks(range(len(paired)),labels,rotation=15);ax.set_ylabel(title);ax.grid(axis='y',alpha=.2)
 if field=='warm_first_token_ms':ax.set_yscale('log');ax.set_ylabel(title+' (log scale)')
axes[0,0].legend();fig.suptitle('Qwen3.8 Flash Next UD-Q4_K_XL / Strix Halo .157\nDS4 runtime payload vs legacy; one cold cohort and three warm cohorts; full cache hits have no executed PP throughput')
fig.savefig(out/'cache-format.svg');fig.savefig(out/'cache-format.png',dpi=160);plt.close(fig)
svg=out/'cache-format.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print(json.dumps({'completed_arms':len(arms),'comparisons':len(comparisons),'state_pairs':sum(len(s['pairs']) for s in state),'cross_variant_pairs':sum(s['pairs'] for s in state_checks),'regressions':[r for r in regressions if r['over_5_percent_regression']]},indent=2))
