# SPDX-License-Identifier: MIT
# Offline analysis only. Never invokes a model/server.
import csv,hashlib,json,os,pathlib,runpy,statistics
root=pathlib.Path.cwd().resolve()  # Run from the feature worktree root.
raw=root/'evidence/state-gpu-r1'
report=runpy.run_path(str(root/'tools/bench-report.py'))
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
for name,h in json.loads((raw/'collection-sha256.json').read_text()).items():assert sha(raw/name)==h,name
state=json.loads((raw/'state.json').read_text())
assert state['state']=='COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS'
assert len(state['runs'])==16 and all(r['exit_code']==0 for r in state['runs'])
post=json.loads((raw/'postflight.json').read_text())
assert not post['kfd'] and all(r['owned_identity_absent'] for r in post['owned_processes']) and all(r['free'] and r['unchanged'] for r in post['locks'])
out=root/'docs/benchmarks/2026-10-02/ram-prefix';out.mkdir(parents=True,exist_ok=True)
data={r['arm']:report['read_result'](raw/r['arm']/'results/measurements.jsonl') for r in state['runs'] if r['arm']!='http-default-ram'}
summary={'source_commit':'4fe6231','cpu_receipt':'reactive-cpu-r12','campaign':'state-gpu-r1','state':state,'postflight':post,'numerical':{},'core':[]}
for name,d in data.items():
 if d['identity']['suite']=='state':
  summary['numerical'][name]={k:d[k] for k in ['input','capture','pairs','source_sha256']}
for n,c in [(8192,1),(131072,1),(2048,2),(2048,4),(2048,8)]:
 row={'prompt_tokens':n,'users':c,'arms':{}}
 for policy in ['off','ram']:
  name=f'core-p{n}-c{c}-{policy}';d=data[name];p=d['configurations'][0]
  measured=[j for j in d['jobs'] if not j['warmup']];cold=[j for j in d['jobs'] if j['warmup']]
  def dist(v):return {'median':statistics.median(v),'min':min(v),'max':max(v),'all':v} if v else None
  rr=json.loads((raw/name/'results/result.json').read_text())
  telemetry=[json.loads(x) for x in (raw/name/'results/telemetry.jsonl').read_text().splitlines()]
  threads=[int(x['process']['Threads']) for x in telemetry if x.get('process',{}).get('Threads')]
  rss=[int(x['process']['VmRSS'].split()[0])*1024 for x in telemetry if x.get('process',{}).get('VmRSS')]
  row['arms'][policy]={'configuration':p,'source_sha256':d['source_sha256'],'measured_jobs':measured,'cold_jobs':cold,'samples':d['samples'],'job_decode_tps':dist([j['output_tokens']*1e9/j['decode_ns'] for j in measured if j['decode_ns']]),'threads_observed':sorted(set(threads)),'rss_max_sampled_bytes':max(rss),'retained_bytes':d['samples'][-1]['cache_retained_bytes'],'peak_retained_bytes':max(x['cache_retained_bytes'] for x in d['samples']),'model_stat_preserved':rr['models_before']==rr['models_after']}
 assert row['arms']['off']['configuration']['output_ids']==row['arms']['ram']['configuration']['output_ids']
 row['total_wall_throughput_ratio']=row['arms']['ram']['configuration']['output_per_total_wall_tps']['median']/row['arms']['off']['configuration']['output_per_total_wall_tps']['median']
 summary['core'].append(row)
http=json.loads((raw/'http-default-ram/results/result.json').read_text());assert http['state']=='MODEL_HTTP_RAM_CACHE_PASS_NOT_NUMERICAL_QUALIFICATION'
summary['http']={k:http[k] for k in ['tests','final_llm','server_exit_code','started_at','finished_at']}
summary['fresh_control_comparison']=next(r['comparison'] for r in state['runs'] if r['arm']=='candidate-fresh')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'values.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['prompt','users','RAM','new_PP_tokens','reused_tokens','PP_tok_s','job_TG_tok_s','aggregate_output_total_wall_tok_s','TTFT_ms','total_ms','restore_path_ms','retained_MiB','cold_capture_ms'])
 for row in summary['core']:
  for policy,a in row['arms'].items():
   p=a['configuration'];new=row['prompt_tokens']-p['cached_tokens']['median']
   w.writerow([row['prompt_tokens'],row['users'],policy,new,p['cached_tokens']['median'],p['job_prefill_tps']['median'] if p['job_prefill_tps'] else '',a['job_decode_tps']['median'],p['output_per_total_wall_tps']['median'],p['first_token_ns']['median']/1e6,p['total_ns']['median']/1e6,p['cache_restore_ns']['median']/1e6,a['retained_bytes']/1024**2,max(j['cache_capture_ns'] for j in a['cold_jobs'])/1e6])
os.environ['MPLCONFIGDIR']=str(root/'run/state-plots-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
for ax,key,scale,title in zip(axes,['first_token_ns','total_ns','output_per_total_wall_tps'],[1e-9,1e-9,1],['First confirmed token (s)','Complete job (s)','Aggregate output / total wall (tok/s)']):
 for offset,policy,color in [(-.18,'off','#64748b'),(.18,'ram','#0891b2')]:
  values=[row['arms'][policy]['configuration'][key] for row in summary['core']]
  ax.bar([i+offset for i in range(5)],[x['median']*scale for x in values],width=.35,label='RAM '+('on' if policy=='ram' else 'off'),color=color,yerr=[[max(0,x['median']-x['min'])*scale for x in values],[max(0,x['max']-x['median'])*scale for x in values]],capsize=3)
 ax.set_xticks(range(5),['8K C1','128K C1','2K C2','2K C4','2K C8']);ax.set_ylabel(title);ax.grid(axis='y',alpha=.2);ax.legend()
 if key!='output_per_total_wall_tps':ax.set_yscale('log')
fig.suptitle('Shared C17 core · original UD-Q4_K_XL · warm RAM prefix versus fresh work\nOne warmup retained separately; n=2 at 8K/128K, n=3 at C2/4/8 · error bars observed range')
fig.savefig(out/'ram-prefix.png',dpi=160);fig.savefig(out/'ram-prefix.svg');plt.close(fig)
# Separate executed full PP/TG from cache transfer time; no synthetic cache PP rate.
fig,axes=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
labels=[];capture=[];restore=[];memory=[]
for name,d in sorted(summary['numerical'].items(),key=lambda item:item[1]['input']['checkpoint_tokens']):
 labels.append(str(d['input']['checkpoint_tokens'])+' tokens')
 capture.append(d['capture']['capture_ns']/1e6)
 restore.append(statistics.median(p['restore_ns'] for p in d['pairs'])/1e6)
 memory.append(d['capture']['retained_bytes']/1024**3)
x=list(range(len(labels)))
axes[0].bar([v-.18 for v in x],capture,width=.35,label='Capture (one sample)',color='#64748b')
axes[0].bar([v+.18 for v in x],restore,width=.35,label='Restore (median of 3)',color='#0891b2')
axes[0].set_ylabel('Completed state operation (ms)');axes[0].legend()
axes[1].bar(x,memory,color='#0891b2');axes[1].axhline(4,linestyle='--',color='#ef4444',label='Default RAM budget')
axes[1].set_ylabel('Retained component allocation (GiB)');axes[1].legend()
for ax in axes:ax.set_xticks(x,labels,rotation=20);ax.grid(axis='y',alpha=.2)
fig.suptitle('C17 hybrid prefix checkpoints · exact fresh/restored logits and tokens\nTyped components; active session storage excluded; SSD absent')
fig.savefig(out/'state-transfer.png',dpi=160);fig.savefig(out/'state-transfer.svg');plt.close(fig)
for name in ['state.json','postflight.json','collection-sha256.json','suite-manifest.json']:(out/name).write_bytes((raw/name).read_bytes())
for label in ['reactive-cpu-r10','reactive-cpu-r11','reactive-cpu-r12']:
 for name in ['result.json','sha256.json']:(out/(label+'-'+name)).write_bytes((root/'evidence'/label/name).read_bytes())
for label in ['state-linked-r1','state-linked-r2','gufo-state-host-r1']:(out/(label+'-receipt.json')).write_bytes((root/'evidence'/label/'result.json').read_bytes())
(out/'analyze.py').write_bytes(pathlib.Path(__file__).read_bytes())
(out/'source-checkpoint.json').write_bytes((root/'evidence/state-source-checkpoint-r1/result.json').read_bytes())
(out/'artifact-sha256.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='artifact-sha256.json'},indent=2)+'\n')
print((out/'values.csv').read_text())
for name,d in summary['numerical'].items():print(name,'MiB',d['capture']['retained_bytes']/1024**2,'capture_ms',d['capture']['capture_ns']/1e6,'restore_ms',[p['restore_ns']/1e6 for p in d['pairs']])
print('HTTP',http['server_exit_code'],'finished',state['finished_at'])
