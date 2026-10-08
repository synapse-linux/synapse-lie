#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit completed full-prefill requests, retaining the interrupted first session."""
import csv,datetime,hashlib,importlib.util,json,math,tarfile
from pathlib import Path
from q2_full_prefill128 import inputs,validate_result
from q2_native_curve import check_backend
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('common',ROOT/'tools/analyze-q2-curve.py')
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
read,sha,require=common.read,common.sha,common.require


def cohort(prefix,index,depth=None,partial=False):
    plan_path=ROOT/('config/'+prefix+'-plan.json');plan=read(plan_path)
    release_path=ROOT/plan['release_path'];release=read(release_path)
    require(not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members']
        and release['plan_sha256']==sha(plan_path),'Window not released')
    host=ROOT/'evidence'/plan['host'];hr,ht=common.artifact_integrity(host)
    require(sha(host/'results/result.json')==plan['host_result_sha256'] and ht['exit_code']==0,'Host mismatch')
    entry=plan['arms'][index];directory=ROOT/'evidence'/entry['label']
    result,transport=common.artifact_integrity(directory)
    exits=[c['exit_code'] for c in result['commands']]
    require(result['mode']=='q2-prefill128' and result['model_access'] and
        exits==([0,0,0,-15] if partial else [0,0,0,0]) and transport['exit_code']==(1 if partial else 0),
        'Unexpected execution/exit scope')
    require(result['models_before']==result['models_after'] and result['locks']==result['postflight_locks']
        and not result['preflight_kfd'] and not result['postflight_kfd'],'Model/ownership differs')
    require(result['finished_at']<release['at'] and (directory/'collection.json').stat().st_mtime<=
        datetime.datetime.fromisoformat(release['at']).timestamp(),'Collection follows release')
    pins=read(ROOT/'config/q2-curve128-binaries.json')
    require(result['binary_sha256']==result['binary_sha256_after']==pins['server']['binary_sha256']
        and result['native_bench_binary_sha256']==result['native_bench_binary_sha256_after']==pins['native_bench']['binary_sha256']
        and result['curve_server_reuse']['no_build'] and result['curve_server_reuse']['provider_files']==1028,
        'Binary reuse identity differs')
    provider=read(ROOT/'config/q2-curve128-source.json')
    with tarfile.open(directory/'source.tar.gz') as archive:
        for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest,'Frozen capsule differs: '+name)
        for prefix,files in [('source/',provider['variants']['q2']['files']),('curve-core/',provider['core_files'])]:
            actual={m.name[len(prefix):]:hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix)}
            require(actual==files,'Provider/core inventory differs')
    session=read(directory/'results/curve-session.json');check_backend(session['backend_ready'],'retained128')
    old=read(ROOT/'evidence/q2-native-row-before-r1/results/curve-session.json')['server_argv']
    new=session['server_argv'];old[0]=new[0];old[old.index('--management-port')+1]=new[new.index('--management-port')+1]
    require(old==new,'Server settings changed')
    data=directory/'results/full-prefill.jsonl'
    if not partial:
        require(session['client_exit_code']==session['server_exit_code']==0,'Owned session closure differs')
        check_backend(session['backend_after'],'retained128')
        require(validate_result(ROOT,data,depth)==session['full_prefill_validation'],'Full validation differs')
    else:
        require(result['thermal_stop'] and result['state']=='FAILED','Expected thermal interruption retained')
    _,manifest,cases=inputs(ROOT,depth)
    events=[json.loads(x) for x in data.read_text().splitlines()]
    samples=[s for s in events if s['event']=='sample']
    require(len(samples)==(9 if partial else 4),'Sample count differs')
    rows=[]
    for sample,case,binding in zip(samples,cases,manifest['cases']):
        actual={k:v for k,v in sample['request'].items() if k not in ('stream','stream_options')}
        expected={k:v for k,v in case['body'].items() if k not in ('stream','stream_options')}
        require(sample['case']==case['id'] and actual==expected and
            sample['usage']['prompt_tokens']==binding['expected_prompt_tokens'],'Saved input changed')
        if binding['phase']!='prefix':continue
        t=sample['server_timings'];n=binding['expected_prompt_tokens']
        require(t['valid'] is True and t['scope']=='synchronous_executor_calls' and t['decode_mode']=='ar'
            and t['cached_tokens']==t['ssd_cached_tokens']==t['mtp_drafted_tokens']==t['mtp_accepted_tokens']==0
            and t['prefill_tokens']==n and t['prefill_calls']==math.ceil(n/2048) and t['prefill_ms']>0,
            'Whole-prefill timing/counts differ')
        rows.append(dict(depth=binding['depth'],attempt=binding['attempt'],tokens=n,prefill_calls=t['prefill_calls'],
            full_chunks=n//2048,remainder=n%2048,current_prefill_seconds=t['prefill_ms']/1000,
            current_prefill_tps=n*1000/t['prefill_ms'],current_wall_seconds=sample['wall_seconds'],
            cache_capture_ms=t['cache_capture_ms'],cache_restore_ms=t['cache_restore_ms'],cohort=entry['label']))
    telemetry=[json.loads(x) for x in (directory/'results/telemetry.jsonl').read_text().splitlines()]
    peaks={d:max(t['temperature_mc'] for e in telemetry for t in e['thermal'] if t['device']==d)/1000
        for d in {t['device'] for e in telemetry for t in e['thermal']}}
    if not partial:require(all(not t['over_limit'] for e in telemetry for t in e['thermal']),'Thermal failure')
    return rows,dict(label=entry['label'],result_sha256=sha(directory/'results/result.json'),samples_sha256=sha(data),
        plan_sha256=sha(plan_path),release_sha256=sha(release_path),command_exits=exits,artifacts=len(result['artifacts']),
        state=result['state'],thermal_peaks_c=peaks,partial_session=partial)


def main():
    rows,first=cohort('q2-full-prefill128',0,partial=True);cohorts=[first]
    for prefix,depth in (('q2-full-prefill128-recovery',65536),('q2-full-prefill128-final',131072)):
        extra,receipt=cohort(prefix,0,depth);rows.extend(extra);cohorts.append(receipt)
    require([(r['depth'],r['attempt']) for r in rows]==[(4096,0),(8192,0),(8192,1),(12288,0),(16384,0),(32768,0),(65536,0),(131072,0)],'Complete full-prefill grid missing')
    historical=read(ROOT/'config/q2-historical-full-prefill.json')
    for artifact in historical['artifacts'].values():require(sha(ROOT/artifact['path'])==artifact['sha256'],'Historical data changed')
    for row in rows:
        for key in ('before','after','ud'):
            old=next(o for o in historical['rows'] if o['arm']==key and o['requested_depth']==row['depth'] and o['attempt']==row['attempt'])
            require(old['physical_tokens']==row['tokens'] and old['prefill_calls']==row['prefill_calls'],'Historical counts differ')
            for field in ('prefill_seconds','prefill_tps','request_wall_seconds'):row[key+'_'+field]=old[field]
            row['current_vs_'+key+'_percent']=100*(row['current_prefill_tps']/old['prefill_tps']-1)
    failed_directory=ROOT/'evidence/q2-full-prefill128-recovery-r1'
    failed,failed_transport=common.artifact_integrity(failed_directory)
    require(failed['state']=='FAILED' and [c['exit_code'] for c in failed['commands']]==[0,0,0,1] and failed_transport['exit_code']==1 and not (failed_directory/'results/curve-session.json').exists(),'Preserve pre-model port failure')
    port_failure=dict(label=failed_directory.name,result_sha256=sha(failed_directory/'results/result.json'),command_exits=[0,0,0,1],artifacts=len(failed['artifacts']),model_request_executed=False)
    report=dict(schema='synapse-lie.q2-full-prefill128-results.v1',rows=rows,cohorts=cohorts,port_startup_failure=port_failure,
        original_corpus_sha256=sha(ROOT/'config/q2-full-prefill128-requests.jsonl'),
        all_saved_model_inputs_exact=True,all_prefix_cached_tokens_zero=True,context_capacity=133760,prefill_chunk=2048,
        server_binary_sha256=read(ROOT/'config/q2-curve128-binaries.json')['server']['binary_sha256'],
        native_binary_sha256=read(ROOT/'config/q2-curve128-binaries.json')['native_bench']['binary_sha256'],
        limits='Archived references, one measurement per exact prefix. SSE transport and omitted continuation requests differ from the old native-curve schedule.64K/128K recovered in separate cold-start sessions after thermal interruption. Completed whole-prefill observations do not isolate causality, establish sustained thermals or independent quality.',
        fixed_benchmark_changed=False,controls_rebuilt_or_rerun=False,independent_quality=False,whole_goal_met=False)
    output=ROOT/'config/q2-full-prefill128-results.json';require(not output.exists(),'Preserve existing report')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    out=ROOT/'docs/figures/q2-full-prefill128';out.mkdir(exist_ok=False)
    with (out/'comparison.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps(dict(points=len(rows),model_artifacts=sum(c['artifacts'] for c in cohorts),cohorts=cohorts)))
    for row in rows:print(f"{row['depth']} #{row['attempt']} tokens{row['tokens']}: Q2 {row['current_prefill_tps']:.3f} ({row['current_prefill_seconds']:.3f}s), UD {row['ud_prefill_tps']:.3f} ({row['ud_prefill_seconds']:.3f}s), {row['current_vs_ud_percent']:+.3f}%")

if __name__=='__main__':main()
