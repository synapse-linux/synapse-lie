#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify all new Q8 phase outputs and preserve timings independent of verdict."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hc',ROOT/'tools/analyze-q2-hc-bk256.py');hc=importlib.util.module_from_spec(spec);spec.loader.exec_module(hc)
require,read,sha=hc.require,hc.read,hc.sha

def main():
 output=ROOT/'config/q2-q8-mirror-component-results.json';require(not output.exists(),'Refusing to overwrite component evidence')
 plan_path=ROOT/'config/q2-q8-mirror-plan.json';plan=read(plan_path)
 plan={**plan,'component_cases':{'ragged1': {'tokens': 1, 'rows': 257, 'inner': 96, 'kind': 'plain', 'fields': ['projection']}, 'ragged15': {'tokens': 15, 'rows': 257, 'inner': 96, 'kind': 'plain', 'fields': ['projection']}, 'ragged17': {'tokens': 17, 'rows': 257, 'inner': 96, 'kind': 'plain', 'fields': ['projection']}, 'ragged129': {'tokens': 129, 'rows': 257, 'inner': 96, 'kind': 'plain', 'fields': ['projection']}, 'ragged1025': {'tokens': 1025, 'rows': 257, 'inner': 96, 'kind': 'plain', 'fields': ['projection']}, 'ssm1024': {'tokens': 1024, 'rows': 16384, 'inner': 2560, 'kind': 'ssm', 'fields': ['projection', 'convolution']}, 'ssm1025': {'tokens': 1025, 'rows': 16384, 'inner': 2560, 'kind': 'ssm', 'fields': ['projection', 'convolution']}, 'ssm1057': {'tokens': 1057, 'rows': 16384, 'inner': 2560, 'kind': 'ssm', 'fields': ['projection', 'convolution']}, 'ssm2048': {'tokens': 2048, 'rows': 16384, 'inner': 2560, 'kind': 'ssm', 'fields': ['projection', 'convolution']}, 'output2048': {'tokens': 2048, 'rows': 2560, 'inner': 6144, 'kind': 'plain', 'fields': ['projection']}, 'attention1025': {'tokens': 1025, 'rows': 13312, 'inner': 2560, 'kind': 'attention', 'fields': ['query', 'gate', 'keys', 'values']}, 'attention2048': {'tokens': 2048, 'rows': 13312, 'inner': 2560, 'kind': 'attention', 'fields': ['query', 'gate', 'keys', 'values']}},'component_bench_shapes':['ssm2048','output2048','attention2048']}
 for name,digest in {**plan['manifests'],**plan['fixtures']}.items():require(sha(ROOT/name)==digest,'Frozen identity changed: '+name)
 arm=plan['component'];path=ROOT/'evidence'/arm['label'];receipt,transport=hc.curve.artifact_integrity(path);exits=[c['exit_code'] for c in receipt['commands']]
 require(exits in ([0,0,0],[0,0,1]) and receipt['finished_at'] and receipt['mode']==transport['mode']==arm['mode'] and transport['source_variant']==arm['variant'] and not transport['rebuild_mmq'] and not receipt['model_access'] and receipt['binary_sha256']==receipt['binary_sha256_after'],'Incomplete/changed component')
 require(receipt['locks']==receipt['postflight_locks'] and len(receipt['locks'])==4 and not receipt['preflight_kfd'] and not receipt['postflight_kfd'],'Component ownership changed')
 source=read(ROOT/plan['source_variant_manifest'])['variants'][arm['variant']];capsule=hc.capsule(path,plan['fixtures'],source['files'])
 events=[json.loads(line) for line in (path/'results/03.log').read_text().splitlines() if line.startswith('{"event"')]
 replay=[e for e in events if e['event']=='q8_mirror_replay'];timings=[e for e in events if e['event']=='q8_mirror_timing'];complete=[e for e in events if e['event']=='q8_mirror_complete']
 require(len(replay)==66 and len(timings)==42 and len(complete)==1 and complete[0]['timing_retained'] and not complete[0]['model_inference'],'Incomplete outputs/timings')
 require(len({(e['shape'],e['rotation'],e['field']) for e in replay})==66,'Repeated/missing output pair')
 for label,case in plan['component_cases'].items():
  rows=[e for e in replay if e['shape']==label];require([(e['rotation'],e['field']) for e in rows]==[(r,f) for r in range(3) for f in case['fields']],'Shape coverage changed: '+label)
  for e in rows:
   field=e['field'];width=case['rows'] if field=='projection' else 10240 if field=='convolution' else 6144 if field in ('query','gate') else 512;elem=2 if field in ('keys','values') else 4
   count=case['tokens']*width;required=count
   if case['kind']=='ssm' and field=='projection':
    required=sum(width if t%32<3 or t%32>=29 or t+3>=case['tokens'] else width-10240 for t in range(case['tokens']))
   require(e['bytes']==count*elem and e['required_values']==required and e['expected_unused_values']==count-required and e['guards_exact'],'Required/full output coverage changed: '+label+'/'+field)
   exact=all(e[k]==0 for k in ('changed_values','nonfinite_values','unwritten_values','unexpected_unused_values'))
   require(e['exact']==exact and (e['changed_values']==0)==(e['reference_sha256']==e['candidate_sha256']),'Numerical verdict changed')
 formats=[e for e in events if e['event']=='q8_mirror_format']
 require(len(formats)==1,'Incomplete mirror format check')
 fmt=formats[0]
 require(fmt['scales']==45058 and fmt['code_scale_combinations']==plan['component_expected_format_combinations'] and fmt['guards_exact'] and fmt['unwritten_values']==0,'Unsafe/incomplete mirror format output')
 import array
 buffers={}
 for kind,key in [('candidate','candidate_sha256'),('integer-reference','integer_reference_sha256')]:
  p=path/'results'/('q8-mirror-format-'+kind+'.bin')
  require(p.stat().st_size==11534848*2 and sha(p)==fmt[key],'Full format array changed')
  a=array.array('H');a.frombytes(p.read_bytes());buffers[kind]=a
 changed=sum(a!=b for a,b in zip(buffers['candidate'],buffers['integer-reference']))
 require(changed==fmt['changed_values'] and fmt['exact']==(changed==0),'Integer format verdict changed')
 require(all(e['guards_exact'] and e['unwritten_values']==0 and e['unexpected_unused_values']==0 for e in replay),'Unsafe device output; stop model work')
 for t in timings:require(t['mirror_weight_bytes']==plan['component_mirror_rotation_bytes'][t['shape']],'Mirror rotation scope changed')
 numerical=fmt['exact'] and all(e['exact'] for e in replay);require(complete[0]['numerical_pass']==numerical and exits[-1]==(0 if numerical else 1),'Numeric rejection or exit lost')
 groups=[]
 for label in plan['component_bench_shapes']:
  case=plan['component_cases'][label];pair={}
  for candidate in (False,True):
   rows=[t for t in timings if t['shape']==label and t['candidate']==candidate]
   require([e['rep'] for e in rows]==list(range(7)) and [e['warmup'] for e in rows]==[True,True]+[False]*5 and all(e['candidate']==bool((e['rep']+e['order'])%2) and e['tokens']==case['tokens'] and e['output_rows']==case['rows'] and e['inner']==case['inner'] and e['iterations']==3 and e['weight_bytes']==plan['component_weight_rotation_bytes'][label] and e['weight_bytes']>32*1024*1024 and e['us_per_iteration']>0 for e in rows),'Timing shape/order/rotation changed')
   pair['candidate' if candidate else 'reference']=hc.shared.common.stats([e['us_per_iteration'] for e in rows if not e['warmup']])
  groups.append(dict(shape=label,**pair,candidate_time_change_percent=100*(pair['candidate']['median']/pair['reference']['median']-1)))
 report=dict(schema='synapse-lie.q2-q8-mirror-component.v1',**capsule,plan_sha256=sha(plan_path),command_exits=exits,artifact_count=len(receipt['artifacts']),binary_sha256=receipt['binary_sha256'],numerical_exact=numerical,device_work_safe=True,format_check=fmt,replay=replay,timings=timings,summaries=groups,model_inference=False,original_inputs_immutable_at_fixture_completion=True,complete_query_gate_key_value_outputs_checked=True,ssm_raw_live_mask_checked=True,complete_convolution_checked=True,control_scope='Literal retained parent inside the new fixture; no qualified historical model/cohort rerun',independent_model_quality_qualification=False,full_model_speedup=False,goal_met=False,timing_scope=plan['component_time_scope'])
 with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(command_exits=exits,complete_outputs=len(replay),timing_samples=len(timings),numerical_exact=numerical,summaries=groups)))
if __name__=='__main__':main()
