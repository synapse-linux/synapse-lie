# SPDX-License-Identifier: MIT
"""Offline ON/OFF comparison. No inference, remote access or ignored warmups."""
import csv,hashlib,json,pathlib,runpy,statistics,sys
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True)
report=runpy.run_path(str(pathlib.Path(__file__).resolve().parent/'bench-report.py'))
median=lambda xs:statistics.median(xs) if xs else None
arms={};table=[]
for path in sorted(root.glob('core-*/results/measurements.jsonl')):
 data=report['read_result'](path);name=path.parent.parent.name;arms[name]=data
 jobs=data['jobs'];hot=[j for j in jobs if not j['warmup']];cold=[j for j in jobs if j['warmup']]
 rows=data['samples'];warmrows=[r for r in rows if not r['warmup']]
 row=dict(arm=name,users=data['identity']['users'],prompt_tokens=jobs[0]['prompt_tokens'],context_capacity=data['identity']['context_capacity'],cache_budget_bytes=data['identity']['prefix_cache_bytes'],checkpoint_codec=data['configurations'][0]['checkpoint_codec'],retention=data['identity']['cache_retention_policy'],compression=data['identity']['checkpoint_compression'],jobs=len(jobs),cold_executed_pp_tps=median([j['prefill_tokens']*1e9/j['prefill_ns'] for j in cold if j['prefill_ns']]),cold_capture_ms=max(j['cache_capture_ns']/1e6 for j in cold),hot_ttft_ms=median([j['first_token_ns']/1e6 for j in hot]),hot_restore_ms=median([j['cache_restore_ns']/1e6 for j in hot]),hot_executor_tg_tps=median([j['output_tokens']*1e9/j['decode_ns'] for j in hot if j['decode_ns']]),hot_output_wall_tps=median([r['output_per_total_wall_tps'] for r in warmrows]),retained_bytes=rows[-1]['cache_retained_bytes'],expanded_bytes=rows[-1]['cache_expanded_bytes'],compressed_captures=sum(r['cache_compressed_captures'] for r in rows))
 row['saved_fraction']=1-row['retained_bytes']/row['expanded_bytes'] if row['expanded_bytes'] else 0
 table.append(row)
comparisons=[]
for name,a in arms.items():
 if name.endswith('-on'):
  other=name[:-3]+'-off'
  if other in arms:
   comparison=report['compare'](a,arms[other],True)[0];comparison.update(primary=name,reference=other)
   comparisons.append(comparison);report['export'](a,out/name,'Cache features ON',arms[other],'Cache features OFF',True)
state=[]
for path in sorted(root.glob('state-*/results/measurements.jsonl')):
 data=report['read_result'](path);state.append(dict(arm=path.parent.parent.name,capture=data['capture'],pairs=data['pairs']))
http=[]
helper=runpy.run_path(str(pathlib.Path(__file__).resolve().parent/'bench-ssd-http.py'))
for path in sorted(root.glob('http-*/results/http.jsonl.summary.json')):
 data=json.loads(path.read_text());name=path.parent.parent.name
 helper['export'](data,out/name)
 http.append(dict(arm=name,state=data['state'],phase=data['phase'],samples=len(data['samples']),cohorts=data['cohorts'],counts=[{k:r[k] for k in ('case','prompt_tokens','output_tokens','cached_tokens')} for r in data['samples'][:2]],overlap=data.get('overlap',{}).get('state'),slow_client=data.get('slow_client',{}).get('state')))
summary=dict(scope='Matched build-feature ablation; one cold warmup and three measured warm cohorts per arm. No confidence interval or kernel/reactive causal speedup claim.',core=table,comparisons=comparisons,state=state,http=http)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
import os
os.environ.setdefault('MPLCONFIGDIR',str(out/'matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
configs=sorted({(r['prompt_tokens'],r['users']) for r in table})
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
for ax,(key,title,scale) in zip(axes.flat,[('cold_executed_pp_tps','Executed prefill tok/s (one cold cohort)',1),('cold_capture_ms','Largest capture call in cold cohort, ms',1),('hot_executor_tg_tps','Per-job executor generation tok/s',1),('hot_ttft_ms','Warm-cache first token, ms',1),('hot_restore_ms','Warm-cache restore, ms',1),('retained_bytes','Retained checkpoint MiB',1/1048576)]):
 for flag,color,delta in [('off','#73869e',-.18),('on','#257e72',.18)]:
  series=[next(r for r in table if (r['prompt_tokens'],r['users'])==c and r['arm'].endswith('-'+flag)) for c in configs]
  ax.bar([x+delta for x in range(len(configs))],[r[key]*scale for r in series],width=.34,label='Features '+flag.upper(),color=color)
 ax.set_xticks(range(len(configs)),[f'{n//1024}K / C{c}' for n,c in configs]);ax.set_ylabel(title);ax.grid(axis='y',alpha=.2)
axes[0,0].legend()
fig.suptitle('Qwen3.8 Flash Next UD-Q4_K_XL / Strix Halo .157 / same reactive core\nDefault cache features ON vs OFF; warm medians over 3 cohorts; raw fallback when packing is not admitted')
fig.savefig(out/'cache-features.svg');fig.savefig(out/'cache-features.png',dpi=160);plt.close(fig)
print(json.dumps(summary,indent=2))
