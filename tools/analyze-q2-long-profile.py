#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute completed host boundaries without treating zero GPU stamps as time."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'evidence/q2-long-profile-r1/results'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((BASE/'result.json').read_text())
    session = json.loads((BASE/'curve-session.json').read_text())
    for name, binding in receipt['artifacts'].items():
        assert sha(BASE/name) == binding['sha256'], name
    release = ROOT/'config/q2-long-profile-window-release.json'
    assert json.loads(release.read_text())['gpu_reserved'] is False
    assert [c['exit_code'] for c in receipt['commands']] == [0]*4
    assert session['full_prefill_validation']['original_inputs_exact']
    database = BASE/'profile/prefix32k_results.db'
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as db:
        cpu = [dict(name=n, start=s, end=e, stack=st, tid=t) for n,s,e,st,t in db.execute('''
            SELECT s.string,r.start,r.end,e.stack_id,r.tid FROM rocpd_region r
            JOIN rocpd_string s ON s.id=r.name_id JOIN rocpd_event e ON e.id=r.event_id''')]
        by_stack = {x['stack']: x for x in cpu}
        embeds = [dict(tokens=n, stack=st) for n,st in db.execute('''
            SELECT k.grid_size_x/k.workgroup_size_x,e.stack_id
            FROM rocpd_kernel_dispatch k JOIN rocpd_info_kernel_symbol s ON s.id=k.kernel_id
            JOIN rocpd_event e ON e.id=k.event_id WHERE s.display_name LIKE '%EmbedKernel(%'
            ORDER BY k.start''')]
        invalid = {}
        for table in ('rocpd_kernel_dispatch','rocpd_memory_copy'):
            total, zero = db.execute(f'SELECT COUNT(*),SUM(end<=start) FROM {table}').fetchone()
            invalid[table] = dict(total=total, invalid_duration=zero)
    expected = [13,1,2048,1465,1,2048,7]+[1]*16+[2048]*15+[1991]+[1]*8
    assert [x['tokens'] for x in embeds] == expected
    # Link dispatches to their CPU API using stack IDs, not the unusable device
    # timestamps/correlation_id=0. The trace contains one inference worker.
    for embed in embeds:
        embed['api'] = by_stack[embed['stack']]
        assert embed['api']['name'] in ('hipLaunchKernel','hipGraphLaunch')
    prefix = []
    for index in range(23,39):
        first = embeds[index]['api']
        low, high, tid = first['start'], embeds[index+1]['api']['start'], first['tid']
        window = sorted((x for x in cpu if x['tid']==tid and low<=x['start']<high),
                        key=lambda x:x['start'])
        waits = [x for x in window if x['name']=='hipEventSynchronize']
        assert len(waits)==48
        completed = next(x for x in window if x['name']=='hipStreamSynchronize'
                         and x['start']>=waits[-1]['end'])
        segments = [(x['end']-(low if i==0 else waits[i-1]['end']))/1e6
                    for i,x in enumerate(waits)]
        gaps=[]
        last = low
        for x in window:
            if x['start']>completed['end']:
                break
            if x['start']>last:
                gaps.append(dict(start=last,end=x['start'],ms=(x['start']-last)/1e6,
                                 before=x['name']))
            last=max(last,x['end'])
        prefix.append(dict(chunk=index-23,tokens=embeds[index]['tokens'],
            start_position=(index-23)*2048,
            embed_submission_to_completion_ms=(completed['end']-low)/1e6,
            expert_count_wait_api_ms=sum((x['end']-x['start'])/1e6 for x in waits),
            full_attention_completion_intervals_ms=sum(t for i,t in enumerate(segments) if i%4==3),
            linear_completion_intervals_except_first_two_ms=sum(t for i,t in enumerate(segments) if i%4!=3 and i>1),
            ple_layer1_completion_interval_ms=segments[1],
            largest_cpu_api_gaps=sorted(gaps,key=lambda x:x['ms'],reverse=True)[:2],
            layer_completion_intervals_ms=segments))
    decode=[]
    for index in range(39,47):
        first=embeds[index]['api']
        low,tid=first['start'],first['tid']
        high=embeds[index+1]['api']['start'] if index<46 else low+100000000
        window=sorted((x for x in cpu if x['tid']==tid and low<=x['start']<high),
                      key=lambda x:x['start'])
        completed=next(x for x in window if x['name']=='hipStreamSynchronize')
        graphs=[dict(offset_ms=(x['start']-low)/1e6,api_ms=(x['end']-x['start'])/1e6)
                for x in window if x['name']=='hipGraphLaunch' and x['end']<=completed['start']]
        decode.append(dict(token=index-39,graphs=graphs,
            embed_submission_to_completion_ms=(completed['end']-low)/1e6,
            final_sync_cpu_wait_ms=(completed['end']-completed['start'])/1e6,
            next_embed_submission_after_completion_ms=(high-completed['end'])/1e6 if index<46 else None))
    result=dict(schema='synapse-lie.q2-long-profile.v1',
        database=str(database.relative_to(ROOT)),database_sha256=sha(database),
        receipt_sha256=sha(BASE/'result.json'),release_sha256=sha(release),
        state='HOST_API_ATTRIBUTION_ONLY_DEVICE_DURATIONS_INVALID',
        original_inputs_exact=True, headline_eligible=False, numerical_or_performance_promotion=False,
        command_exits=[0]*4,client_exit_code=session['client_exit_code'],
        server_exit_code=session['server_exit_code'],
        shutdown='Profiler flushed the database after SIGTERM; chained handler did not retire within30s. Owned server killed by existing supervisor after completed request; no foreign process affected.',
        device_duration_validation=invalid,gpu_busy_fraction=None,gpu_kernel_stage_ms=None,
        matched_embed_calls=len(embeds),prefill=prefix,decode=decode,
        attribution_limit='Completion intervals include previous-layer MoE/shared work and current attention/HC work. They are not isolated GPU-kernel durations. HIP waits include device work; they are not removable CPU overhead. No128K extrapolation or causal gain is measured.',
        reactive_decode_limit='Warm C1 already queues prefix/suffix graphs back-to-back and immediately waits for completion; external scheduling gaps are small. The old diagnostic-harness5.33ms/token gap is not a native-server measurement.',
        next='Measure bounded attention tiles and PLE readiness mechanisms; preserve native input/timer contracts. Zero device stamps cannot rank individual selector versus attention kernels.')
    output=ROOT/'config/q2-long-profile-results.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('state','device_duration_validation','matched_embed_calls','server_exit_code')}))
    for row in prefix:
        print(json.dumps({k:v for k,v in row.items() if k not in ('layer_completion_intervals_ms','largest_cpu_api_gaps')}))
    print(json.dumps(dict(steady_decode=decode[2:])))


if __name__=='__main__':
    main()
