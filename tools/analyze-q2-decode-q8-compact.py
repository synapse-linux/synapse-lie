#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the Q8 decode component only after collection and verified release."""
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require
PREFIX = 'q2-decode-q8-compact'


def main():
    pp=ROOT/('config/'+PREFIX+'-plan.json')
    rp=ROOT/('config/'+PREFIX+'-window-release.json')
    plan,release=read(pp),read(rp)
    require(release['state']=='Q2_DECODE_Q8_COMPACT_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256']==sha(pp),'Window is not released')
    directory=ROOT/'evidence'/plan['components'][0]['label']
    result,transport=curve.artifact_integrity(directory)
    exits=[c['exit_code'] for c in result['commands']]
    require(result['mode']==transport['mode']=='decode-q8-compact-check' and
            not result['model_access'] and result.get('finished_at') and
            exits in ([0,0,0],[0,0,1]) and transport['exit_code']==exits[-1] and
            result['binary_sha256']==result['binary_sha256_after'] and
            not result['postflight_kfd'] and result['locks']==result['postflight_locks'],
            'Unsafe or incomplete component')
    collection=read(ROOT/('evidence/'+PREFIX+'-runtime-preparation/component-collect-command.json'))
    require(collection['exit_code']==0 and
            datetime.datetime.fromisoformat(collection['finished_at']) <
            datetime.datetime.fromisoformat(release['at']),'Collect before release')
    with tarfile.open(directory/'source.tar.gz') as archive:
        for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest,name)
    events=[json.loads(l) for l in (directory/'results/03.log').read_text().splitlines() if l.startswith('{')]
    rows={k:[r for r in events if r['event']=='q8_compact_'+k] for k in ('case','pair','oracle','timing','complete')}
    require([len(rows[k]) for k in rows]==[8,2038,4076,56,1],'Evidence counts differ')
    require(rows['complete'][0]['safe_completion'] and rows['complete'][0]['timing_retained'] and
            all(r['inputs_unchanged'] and r['guards_finite_written'] for r in rows['case']),
            'Unsafe output or mutated input')
    for r in rows['pair']:
        require((r['reference_sha256']==r['candidate_sha256'])==r['exact'],'Exact replay digest differs')
    numerical=all(r['exact'] for r in rows['pair']) and all(r['pass'] for r in rows['oracle'])
    require(numerical==rows['complete'][0]['numerical_pass'] and exits[-1]==(0 if numerical else 1),
            'Numerical exit lost')
    require(all(r['limit']==2e-5 and r['samples']==64 for r in rows['oracle']),'Oracle contract differs')
    summaries=[]
    for shape in plan['timing_shapes']:
        name,banks=shape['name'],shape['banks']
        iterations=shape['iterations']
        require(sum(r['case'].startswith(name+'-r') for r in rows['pair'])==7*iterations,'Timed output check lost')
        arms=[]
        for candidate in (False,True):
            data=[r for r in rows['timing'] if r['case']==name and r['candidate']==candidate]
            require(len(data)==7 and sorted(r['rep'] for r in data)==list(range(7)) and
                    all(r['iterations']==iterations and r['weight_bytes']>=48*1024*1024 and
                        r['warmup']==(r['rep']<2) and
                        r['order']==(int(candidate)-r['rep'])%2 for r in data),'Timing contract differs')
            wall=[r['completed_wall_us'] for r in data if not r['warmup']]
            require(all(math.isfinite(v) and v>0 for v in wall),'Invalid completed wall time')
            valid=all(r['gpu_event_valid'] and r['gpu_event_us'] is not None and r['gpu_event_us']>0 for r in data)
            arms.append(dict(candidate=candidate,wall_samples_us=wall,wall_mean_us=statistics.mean(wall),
                wall_min_us=min(wall),wall_max_us=max(wall),gpu_event_valid=valid,
                gpu_event_samples_us=[r['gpu_event_us'] for r in data],
                gpu_event_mean_us=statistics.mean(r['gpu_event_us'] for r in data if not r['warmup']) if valid else None))
        summaries.append(dict(**shape,arms=arms,completed_wall_time_change_percent=
                              100*(arms[1]['wall_mean_us']/arms[0]['wall_mean_us']-1)))
    report=dict(schema='synapse-lie.'+PREFIX+'-results.v1',plan_sha256=sha(pp),release_sha256=sha(rp),
        result_sha256=sha(directory/'results/result.json'),commands=exits,verified_artifacts=len(result['artifacts']),
        numerical_pass=numerical,exact_pairs=sum(r['exact'] for r in rows['pair']),
        oracle_passes=sum(r['pass'] for r in rows['oracle']),timing_shapes=summaries,events=events,
        disposition='Component only; evaluate speed and numerical evidence before a separately admitted model trial.',
        aggregation='Arithmetic mean of five completed monotonic wall samples, raw ranges retained. Zero HIP event times are invalid, not zero-cost kernels.',
        model_inference=False,model_promoted=False,reactive_changed=False,fixed_point_goal_paused=True)
    with (ROOT/('config/'+PREFIX+'-results.json')).open('x') as f:
        json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(numerical_pass=numerical,exact_pairs=report['exact_pairs'],
        oracle_passes=report['oracle_passes'],timing_shapes=summaries)))


if __name__=='__main__':
    main()
