# SPDX-License-Identifier: MIT
# Offline analysis of immutable, completed GPU evidence; no hardware execution.
import collections,csv,hashlib,json,math,os,pathlib,runpy,statistics,sys
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
repo=next(p for p in pathlib.Path(__file__).resolve().parents if (p/'tools/bench-report.py').is_file())
os.environ.setdefault('MPLCONFIGDIR',str(repo/'run/core-gpu-matplotlib-cache'))
report=runpy.run_path(str(repo/'tools/bench-report.py'))
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
for name,h in json.loads((root/'collection-sha256.json').read_text()).items():assert sha(root/name)==h,name
state=json.loads((root/'state.json').read_text());manifest=json.loads((root/'suite-manifest.json').read_text())
assert state['state']=='COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS',state
assert len(state['runs'])==len(manifest['arms'])==13 and all(r['exit_code']==0 for r in state['runs'])
assert {r['arm'] for r in state['runs']}=={a['id'] for a in manifest['arms']}
assert all(r.get('tokens_match_executor') is True for r in state['runs'] if r['arm'].startswith('core-'))
results={arm['id']:json.loads((root/arm['id']/'results/result.json').read_text()) for arm in manifest['arms']}
assert all(not v.get('error') and v.get('server_exit_code',v.get('child_exit_code'))==0 for v in results.values())
common_dsos={}
for result in results.values():
 for path,digest in result['dsos'].items():
  assert common_dsos.setdefault(path,digest)==digest,'DSO drift: '+path
for suffix in ['http','multi','fresh']:
 assert results['baseline-'+suffix]['dsos']==results['candidate-'+suffix]['dsos'],'matched dependency closure drift'
executor_results={}
summary={'schema':'synapse-lie.core-gpu-regression.v1','scope':'core extraction with unchanged delegated Gufo; no owned numerical claim','baseline':'2ba01ed','candidate':'81c2f60','campaign':state,'executor':{},'core':[],'http':[],'threads':{},'regression_flags':[],'model_files_unchanged':True,'common_runtime_dsos_equal':True,'matched_binary_dependency_sets_equal':True}
def dist(values):return {'median':statistics.median(values),'min':min(values),'max':max(values),'all':values}
for suite in ['multi','fresh']:
 a=report['read_result'](root/('candidate-'+suite)/'results/measurements.jsonl');b=report['read_result'](root/('baseline-'+suite)/'results/measurements.jsonl')
 executor_results[suite]=a
 comparisons=report['compare'](a,b)
 assert all(c['eligible'] and c['tokens_equal'] and c['pp_frontier_equal'] and c['tg_frontier_equal'] for c in comparisons)
 pairs=[]
 for x,y in zip(a['configurations'],b['configurations']):
  assert (x['users'],x['prompt_tokens'])==(y['users'],y['prompt_tokens'])
  row={'users':x['users'],'prompt_tokens':x['prompt_tokens'],'baseline_prefill':y['prefill_tps'],'candidate_prefill':x['prefill_tps'],'baseline_decode':y['decode_tps'],'candidate_decode':x['decode_tps'],'tokens_equal':True,'frontiers_equal':True}
  for phase in ['prefill','decode']:
   ratio=row['candidate_'+phase]['median']/row['baseline_'+phase]['median'];row[phase+'_ratio']=ratio
   if ratio<.95:summary['regression_flags'].append({'scope':suite,'users':x['users'],'prompt_tokens':x['prompt_tokens'],'metric':phase,'ratio':ratio})
  pairs.append(row)
 summary['executor'][suite]=pairs
for arm in manifest['arms']:
 name=arm['id'];r=results[name]
 assert r['models_before']==r['models_after'] and not r['postflight_kfd']
 if arm.get('core'):
  a=report['read_result'](root/name/'results/measurements.jsonl');p=a['configurations'][0];jobs=[j for j in a['jobs'] if not j['warmup']]
  reference=executor_results['multi' if p['prompt_tokens']==2048 else 'fresh']
  q=next(q for q in reference['configurations'] if (q['users'],q['prompt_tokens'])==(p['users'],p['prompt_tokens']))
  for key in ['physical_ids_sha256','output_ids','context_capacity']:assert p[key]==q[key],(name,key)
  for key in ['prefill_chunk','output_limit','warmups','repetitions']:assert a['identity'][key]==reference['identity'][key],(name,key)
  assert p['full_output_budget'] and q['full_output_budget']
  row={'arm':name,'tokens_match_executor':True,**p,'job_decode_tps':dist([j['output_tokens']*1e9/j['decode_ns'] for j in jobs]),'sample_dispatch':[ {k:s[k] for k in ['rep','warmup','decode_single_calls','decode_batches','decode_batch_rows']} for s in a['samples']]}
  summary['core'].append(row)
  report['export'](a,out/name,'LIE shared core')
 path=root/name/'results/telemetry.jsonl'
 observed=collections.Counter(int(r['process']['Threads']) for r in (json.loads(line) for line in path.read_text().splitlines()) if r.get('process',{}).get('Threads'))
 summary['threads'][name]={'min':min(observed) if observed else None,'max':max(observed) if observed else None,'sample_counts':dict(observed),'scope':'OS process total at 1 Hz, includes loader/backend/runtime; not utilization'}
a=results['candidate-http']['performance']['configurations'];b=results['baseline-http']['performance']['configurations']
assert len(a)==len(b)==6
key=lambda r:(r['api'],r['label'],r['stream'],r['concurrency'])
for side in ['baseline','candidate']:
 rows=[json.loads(s) for s in (root/(side+'-http')/'results/performance.jsonl').read_text().splitlines()]
 rows=[r for r in rows if r['event']=='performance_sample']
 observed={}
 for r in rows:
  k=(key(r),r['rep'])
  if r['api']=='chat':
   finish=r['body']['choices'][0]['finish_reason'] if not r['stream'] else next(e['value']['choices'][0]['finish_reason'] for e in r['transport_events'] if e['value'].get('choices') and e['value']['choices'][0].get('finish_reason'))
  else:
   finish=r['body']['status'] if not r['stream'] else next(e['value']['response']['status'] for e in r['transport_events'] if e['value']['type'] in ('response.completed','response.incomplete','response.failed'))
  value=(r['request'],r['output'],r['usage'],finish)
  if k in observed:assert observed[k]==value,'HTTP identical peer output mismatch'
  observed[k]=value
 if side=='baseline':http_reference=observed
 else:assert http_reference==observed,'HTTP requests/output/usage mismatch'
for x,y in zip(a,b):
 assert key(x)==key(y)
 row={k:x[k] for k in ['api','label','stream','concurrency','requests','prompt_tokens','output_tokens']}
 for metric in ['end_to_end_ms','first_text_ms','executor_prefill_tps','executor_decode_tps','aggregate_output_tps']:
  row['baseline_'+metric]=y[metric];row['candidate_'+metric]=x[metric]
  ratio=x[metric]['median']/y[metric]['median'] if x[metric] is not None and y[metric] is not None else None
  row[metric+'_ratio']=ratio
  if metric in ['end_to_end_ms','first_text_ms'] and ratio is not None and ratio>1.05:summary['regression_flags'].append({'scope':'http','api':x['api'],'stream':x['stream'],'concurrency':x['concurrency'],'metric':metric,'ratio':ratio})
 summary['http'].append(row)
lifecycle=results['candidate-lifecycle']
assert lifecycle['lifecycle_status']=='PASS' and lifecycle['reactive']['state']=='PASS' and lifecycle['openai']['state']=='PASS'
assert lifecycle['openai']['native_tool_roundtrip'] and lifecycle['openai']['responses_json_sse']
summary['lifecycle']={k:lifecycle[k] for k in ['lifecycle','reactive','openai','final_llm']}
post=json.loads((root/'postflight.json').read_text());assert not post['kfd'] and all(p['owned_identity_absent'] for p in post['owned_processes']) and all(p['free'] and p['unchanged'] for p in post['locks'])
summary['closure']=post
summary['status']='PASS_WITH_PERFORMANCE_FLAGS' if summary['regression_flags'] else 'PASS_WITHIN_SAMPLED_5_PERCENT_GATES'
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'executor.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['suite','users','prompt_tokens','baseline_pp_tps','candidate_pp_tps','pp_change_percent','baseline_tg_tps','candidate_tg_tps','tg_change_percent'])
 for suite,points in summary['executor'].items():
  for p in points:w.writerow([suite,p['users'],p['prompt_tokens'],p['baseline_prefill']['median'],p['candidate_prefill']['median'],100*(p['prefill_ratio']-1),p['baseline_decode']['median'],p['candidate_decode']['median'],100*(p['decode_ratio']-1)])
with (out/'core.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['arm','users','prompt_tokens','job_prefill_tps','job_decode_tps','output_per_total_wall_tps','first_token_ms','total_ms'])
 for p in summary['core']:w.writerow([p['arm'],p['users'],p['prompt_tokens'],p['job_prefill_tps']['median'],p['job_decode_tps']['median'],p['output_per_total_wall_tps']['median'],p['first_token_ns']['median']/1e6,p['total_ns']['median']/1e6])
with (out/'http.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['api','stream','concurrency','scope','side','median','min','max'])
 for row in summary['http']:
  for metric in ['end_to_end_ms','first_text_ms','executor_prefill_tps','executor_decode_tps','aggregate_output_tps']:
   for side in ['baseline','candidate']:
    v=row[side+'_'+metric]
    if v:w.writerow([row['api'],row['stream'],row['concurrency'],metric,side,v['median'],v['min'],v['max']])
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for ax,suite,metric,title in [(axes[0,0],'multi','decode','Executor aggregate TG (tok/s)'),(axes[0,1],'fresh','prefill','Fresh full-prompt PP (tok/s)')]:
 points=summary['executor'][suite];xs=range(len(points))
 for label,color,offset in [('baseline','#64748b',-.18),('candidate','#0284c7',.18)]:
  values=[p[label+'_'+metric] for p in points]
  ax.bar([x+offset for x in xs],[v['median'] for v in values],width=.34,color=color,label=label,yerr=[[v['median']-v['min'] for v in values],[v['max']-v['median'] for v in values]],capsize=3)
 ax.set_xticks(list(xs),[str(p['users'])+' users' if suite=='multi' else str(p['prompt_tokens']) for p in points]);ax.set_title(title);ax.legend()
points=[p for p in summary['http'] if p['stream']]
ax=axes[1,0]
for label,color,offset in [('baseline','#64748b',-.18),('candidate','#0284c7',.18)]:
 values=[p[label+'_first_text_ms'] for p in points]
 ax.bar([x+offset for x in range(len(points))],[v['median'] for v in values],width=.34,color=color,label=label,yerr=[[v['median']-v['min'] for v in values],[v['max']-v['median'] for v in values]],capsize=3)
ax.set_xticks(range(len(points)),[p['api']+' C'+str(p['concurrency']) for p in points]);ax.set_title('HTTP first text, ms (2042 prompt tokens)');ax.legend()
points=[p for p in summary['core'] if p['prompt_tokens']==2048];ax=axes[1,1]
values=[p['output_per_total_wall_tps'] for p in points]
ax.bar([p['users'] for p in points],[v['median'] for v in values],color='#059669',yerr=[[v['median']-v['min'] for v in values],[v['max']-v['median'] for v in values]],capsize=3);ax.set_xticks([p['users'] for p in points]);ax.set_xlabel('Concurrent jobs');ax.set_title('Core output / total wall, tok/s (includes PP)')
for ax in axes.flat:ax.grid(axis='y',alpha=.25);ax.set_axisbelow(True)
fig.suptitle('Shared-core extraction on .157 — original UD-Q4_K_XL\nSeparate timing scopes; medians and observed ranges, not a universal no-regression proof')
fig.savefig(out/'comparison.svg');fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
# Normalize only derived graph/CSV formatting, never raw receipts.
for path in [*out.rglob('*.svg'),*out.rglob('*.csv')]:
 path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
print(json.dumps({'status':summary['status'],'flags':summary['regression_flags'],'output':str(out)},indent=2))
