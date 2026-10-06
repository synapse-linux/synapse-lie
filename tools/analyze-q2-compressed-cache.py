#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Analyze the bounded compressed-cache experiment against unchanged saved models."""
import argparse
import importlib.util
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ssm',ROOT/'tools/analyze-q2-ssm-followup.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
hc=base.hc
read,sha,require=base.read,base.sha,base.require
PLAN=ROOT/'config/q2-compressed-cache-plan.json'


def bound():
    plan=read(PLAN)
    for name,digest in {**plan['fixtures'],**plan['manifests'],plan['window_helper']:plan['window_helper_sha256']}.items():
        require(sha(ROOT/name)==digest,'Frozen identity changed: '+name)
    source=read(ROOT/plan['source_manifest'])['variants']['compressed-cache']
    for name,digest in source['files'].items():
        require(sha(ROOT/source['source']/name)==digest,'Source changed: '+name)
    return plan,source


def analyze_events(events,exit_code):
    groups={kind:[r for r in events if r.get('event')=='compressed_cache_'+kind]
            for kind in ('format','replay','timing','complete')}
    require(sum(map(len,groups.values()))==len(events),'Unexpected component event')
    require([len(groups[k]) for k in groups]==[117,216,56,1],'Incomplete component coverage')
    complete=groups['complete'][0]
    require(all(complete[k] is True for k in ('guards_exact','all_written','immutable','timing_retained')),
            'Unsafe or incomplete component')
    require(all(r['guards_exact'] and r['all_written'] for r in groups['replay']),'Missing writes/guards')
    numeric=all(r['exact'] and r['changed']==0 for r in groups['replay']) and all(
        r['pass'] and r['changed']==0 for r in groups['format'])
    require(complete['numerical_pass']==numeric and exit_code==(0 if numeric else 1),'Numeric exit mismatch')
    expected={'iq2-n2048-m640-e64-w0','iq2-n2048-m640-e512-w0',
              'q2-n2048-m2560-e64-w48-half','q2-n2048-m2560-e512-w48-half'}
    require({r['case'] for r in groups['timing']}==expected,'Changed timed shapes')
    summaries={}
    for name in sorted(expected):
        pair={}
        for cached in (False,True):
            rows=[r for r in groups['timing'] if r['case']==name and r['cached']==cached]
            require([r['rep'] for r in rows]==list(range(7)) and
                    [r['warmup'] for r in rows]==[True,True]+[False]*5,'Changed timing repetitions')
            require(all(r['cached']==bool((r['rep']+r['order'])%2) and r['rotations']==3 and
                r['weight_bytes']>32*1024**2 and r['cache_bytes']>32*1024**2 and r['us']>0 for r in rows),
                'Changed rotation/timing scope')
            values=[r['us'] for r in rows if not r['warmup']]
            pair['cached' if cached else 'original']=dict(samples=values,min=min(values),median=statistics.median(values),max=max(values))
        pair['cache_time_change_percent']=100*(pair['cached']['median']/pair['original']['median']-1)
        summaries[name]=pair
    return dict(numerical_pass=numeric,device_work_safe=True,format=groups['format'],replay=groups['replay'],
        timings=groups['timing'],summaries=summaries,format_samples=sum(r['samples'] for r in groups['format']),
        limits='Complete encoded-byte preservation and original/slotted numerical output comparisons; address indirection only. No independent task-quality qualification.')


def component(plan,source):
    path=ROOT/'evidence'/plan['component']
    receipt,transport=hc.curve.artifact_integrity(path)
    exits=[c['exit_code'] for c in receipt['commands']]
    require(exits in ([0,0,0],[0,0,1]) and transport['exit_code']==exits[-1] and
        receipt['mode']=='compressed-cache-check' and not receipt['model_access'] and
        transport['source_variant']=='compressed-cache' and not transport['rebuild_mmq'],'Unsafe component receipt')
    require(receipt['binary_sha256']==receipt['binary_sha256_after'] and
        receipt['locks']==receipt['postflight_locks'] and len(receipt['locks'])==4 and
        not receipt['preflight_kfd'] and not receipt['postflight_kfd'],'Changed device ownership/binary')
    events=[json.loads(line) for line in (path/'results/03.log').read_text().splitlines() if line.startswith('{"event"')]
    return dict(schema='synapse-lie.q2-compressed-cache-component.v1',**analyze_events(events,exits[-1]),
        **hc.capsule(path,plan['fixtures'],source['files']),plan_sha256=sha(PLAN),
        command_exits=exits,artifact_count=len(receipt['artifacts']),binary_sha256=receipt['binary_sha256'],
        model_inference=False,goal_met=False)


def model(plan,source):
    cpath=ROOT/'config/q2-compressed-cache-component-results.json'
    require(read(cpath)==component(plan,source),'Component report differs from raw evidence')
    path=ROOT/'evidence'/plan['model']
    root,arm=hc.prior.shared.arm(path,'compressed-cache')
    receipt=hc.curve.artifacts(path)
    require(receipt['mode']=='q2-counting-compressed-cache' and receipt['model_access'] and
        len(receipt['commands'])==4 and all(c['exit_code']==0 for c in receipt['commands']) and
        receipt['commands'][-1]['argv'][-1]=='bench2k' and
        '-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'],'Changed original tester')
    require(sha(root/'pp2048-input.i32')==plan['input_sha256'],'Changed original prompt')
    arm.update(hc.capsule(path,plan['fixtures'],source['files']))
    references,replay={},{}
    for key,info in plan['references'].items():
        cohort=ROOT/'evidence'/info['label']
        refroot,references[key]=hc.prior.shared.arm(cohort,info['variant'])
        hc.curve.artifacts(cohort)
        replay[key]=hc.prior.comparison(refroot,root)
        require(replay[key]['input_exact'],'Different historical input')
        saved=read(ROOT/info['report'])
        expected=saved['model']['measurements'] if key=='best_parent' else saved['arms'][info['reference_key']]['measurements']
        require(references[key]['measurements']==expected,'Historical measurements changed')
    events=[json.loads(line) for line in (root/'04.log').read_text().splitlines() if line.startswith('{"event"')]
    cache=[r for r in events if r['event']=='q2_compressed_cache_ready']
    loaded=[r for r in events if r['event']=='loaded']
    stats=[r for r in events if r['event']=='q2_compressed_cache_stats']
    require(len(cache)==len(loaded)==len(stats)==1,'Missing compressed cache telemetry')
    require(cache[0]['slots']==23061 and cache[0]['total_experts']==24576 and
        cache[0]['weight_bytes']==34359057408 and cache[0]['budget_bytes']==32*1024**3 and
        cache[0]['gate_bytes_per_expert']==422400 and cache[0]['down_bytes_per_expert']==645120,
        'Changed compressed cache budget/format')
    require(loaded[0]['resident_bytes']==40898208304 and loaded[0]['max_context']==9216 and
        loaded[0]['prefill_chunk']==2048 and not loaded[0]['mtp'],'Changed memory/model protocol')
    stats=stats[0]
    require(stats['hits']>0 and stats['misses']>0 and stats['loads']==stats['misses'] and
        stats['failed_loads']==0 and stats['slots']==cache[0]['slots'] and
        stats['weight_bytes']==cache[0]['weight_bytes'] and
        stats['read_bytes']==stats['loads']*(2*422400+645120) and
        stats['dynamic_id_bytes']==20480*4,'Incomplete cache transactions/accounting')
    release=read(ROOT/plan['release_path'])
    require(release['state']=='Q2_COMPRESSED_CACHE_WINDOW_RELEASED' and not release['gpu_reserved'] and
        not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'],
        'Window not released')
    checks={k:dict(input_exact=v['input_exact'],output_tokens_exact=v['output_tokens_exact'],changed_files=v['changed'],
        max_matched_history_kl=max((f['kl_p_to_candidate'] for f in v['frontiers'] if f['matched_history']),default=None))
        for k,v in replay.items()}
    return dict(schema='synapse-lie.q2-compressed-cache-model.v1',plan_sha256=sha(PLAN),source_variant='compressed-cache',
        model=arm,references=references,replay=replay,checks=checks,cache=cache[0],cache_stats=stats,loaded=loaded[0],
        candidate_median_change_percent=base.measurement_changes(arm,references),
        within_arm_exact=arm['within_arm_replay']==dict(checks=9,exact=9),
        original_tester_unchanged=True,controls_rerun=False,component_rerun=False,
        release_sha256=sha(ROOT/plan['release_path']),goal_met=False,independent_model_quality=False,
        limits='One new original exact2048/tg128 model; saved fixed Q2/UD and retained1585 reused. '
        'Original compressed weights, 32GiB slots and protected LRU. Miss transfers and GPU waits remain inside PP/TG. '
        'Inherited F16 task quality and full-curve equality remain open.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('component','model'));args=parser.parse_args()
    plan,source=bound();output=ROOT/('config/q2-compressed-cache-'+args.phase+'-results.json')
    require(not output.exists(),'Refusing to overwrite results')
    report=(component if args.phase=='component' else model)(plan,source)
    hc.write(output,report)
    summary={k:report[k] for k in (('numerical_pass','summaries','format_samples') if args.phase=='component' else
        ('candidate_median_change_percent','checks','cache','cache_stats','loaded'))}
    print(json.dumps(dict(output=str(output.relative_to(ROOT)),**summary)))
