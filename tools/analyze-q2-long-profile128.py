#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute the original 130925-token trace using completed host intervals."""
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'evidence/q2-long-profile128-r1/results'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((BASE/'result.json').read_text())
    session = json.loads((BASE/'curve-session.json').read_text())
    for name, binding in receipt['artifacts'].items():
        assert sha(BASE/name) == binding['sha256'], name
    release = ROOT/'config/q2-long-profile128-window-release.json'
    closure = json.loads(release.read_text())
    assert (closure['state'] == 'Q2_LONG_PROFILE128_WINDOW_RELEASED' and
            not closure['gpu_reserved'] and not closure['kfd'] and
            closure['model_stats_unchanged'])
    assert (receipt['state'] == 'PREFIX128K_PROFILE_COMPLETE_NOT_BENCHMARK' and
            receipt['profile_prefix128k'] and receipt['diagnostic_only'] and
            [c['exit_code'] for c in receipt['commands']] == [0]*4)
    assert (session['state'] == 'PREFIX128K_PROFILE_COMPLETE_NOT_BENCHMARK' and
            session['full_prefill_validation']['original_inputs_exact'] and
            session['full_prefill_validation']['physical_tokens'] == 130925 and
            session['full_prefill_validation']['cached_tokens'] == 0 and
            session['client_exit_code'] == 0)
    database = BASE/'profile/prefix128k_results.db'
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
        durations = {}
        for table in ('rocpd_kernel_dispatch', 'rocpd_memory_copy'):
            total, invalid = db.execute(f'SELECT COUNT(*),SUM(end<=start) FROM {table}').fetchone()
            durations[table] = dict(total=total, invalid_duration=invalid)
    preparation = [13,1,2048,1465,1,2048,7]+[1]*16
    expected = preparation+[2048]*63+[1901]+[1]*8
    assert [x['tokens'] for x in embeds] == expected
    for embed in embeds:
        embed['api'] = by_stack[embed['stack']]
        assert embed['api']['name'] in ('hipLaunchKernel', 'hipGraphLaunch')
    start, end = len(preparation), len(preparation)+64
    prefill = []
    for index in range(start, end):
        first = embeds[index]['api']
        low, high, tid = first['start'], embeds[index+1]['api']['start'], first['tid']
        window = sorted((x for x in cpu if x['tid'] == tid and low <= x['start'] < high),
                        key=lambda x: x['start'])
        waits = [x for x in window if x['name'] == 'hipEventSynchronize']
        assert len(waits) == 48
        completed = next(x for x in window if x['name'] == 'hipStreamSynchronize'
                         and x['start'] >= waits[-1]['end'])
        segments = [(x['end']-(low if i == 0 else waits[i-1]['end']))/1e6
                    for i,x in enumerate(waits)]
        gaps, last = [], low
        for x in window:
            if x['start'] > completed['end']:
                break
            if x['start'] > last:
                gaps.append(dict(start=last, end=x['start'],
                                 ms=(x['start']-last)/1e6, before=x['name']))
            last = max(last, x['end'])
        prefill.append(dict(chunk=index-start, tokens=embeds[index]['tokens'],
            start_position=(index-start)*2048,
            embed_submission_to_completion_ms=(completed['end']-low)/1e6,
            expert_count_wait_api_ms=sum((x['end']-x['start'])/1e6 for x in waits),
            full_attention_completion_intervals_ms=sum(t for i,t in enumerate(segments) if i%4 == 3),
            linear_completion_intervals_except_first_two_ms=sum(t for i,t in enumerate(segments)
                                                                 if i%4 != 3 and i > 1),
            ple_layer1_completion_interval_ms=segments[1],
            largest_cpu_api_gaps=sorted(gaps,key=lambda x:x['ms'],reverse=True)[:2],
            layer_completion_intervals_ms=segments))
    decode = []
    for index in range(end, end+8):
        first = embeds[index]['api']
        low, tid = first['start'], first['tid']
        high = embeds[index+1]['api']['start'] if index < end+7 else low+100000000
        window = sorted((x for x in cpu if x['tid'] == tid and low <= x['start'] < high),
                        key=lambda x: x['start'])
        completed = next(x for x in window if x['name'] == 'hipStreamSynchronize')
        graphs = [dict(offset_ms=(x['start']-low)/1e6,
                       api_ms=(x['end']-x['start'])/1e6) for x in window
                  if x['name'] == 'hipGraphLaunch' and x['end'] <= completed['start']]
        decode.append(dict(token=index-end, graphs=graphs,
            embed_submission_to_completion_ms=(completed['end']-low)/1e6,
            final_sync_cpu_wait_ms=(completed['end']-completed['start'])/1e6,
            next_embed_submission_after_completion_ms=(high-completed['end'])/1e6
            if index < end+7 else None))
    quartiles = []
    for offset in (0,16,32,48):
        rows = prefill[offset:offset+16]
        quartiles.append(dict(chunks=[offset,offset+15],
            mean_completion_ms=statistics.mean(x['embed_submission_to_completion_ms'] for x in rows),
            mean_full_attention_boundary_ms=statistics.mean(
                x['full_attention_completion_intervals_ms'] for x in rows),
            mean_ple_layer1_boundary_ms=statistics.mean(
                x['ple_layer1_completion_interval_ms'] for x in rows)))
    result = dict(schema='synapse-lie.q2-long-profile128.v1',
        database=str(database.relative_to(ROOT)), database_sha256=sha(database),
        receipt_sha256=sha(BASE/'result.json'), release_sha256=sha(release),
        state='HOST_API_ATTRIBUTION_ONLY', original_inputs_exact=True,
        headline_eligible=False, numerical_or_performance_promotion=False,
        command_exits=[0]*4, client_exit_code=session['client_exit_code'],
        server_exit_code=session['server_exit_code'],
        device_duration_validation=durations,
        device_durations_usable=all(v['total'] > 0 and v['invalid_duration'] == 0
                                    for v in durations.values()),
        matched_embed_calls=len(embeds), prefill=prefill, quartiles=quartiles,
        decode=decode,
        attribution_limit='Completion intervals include previous-layer MoE/shared work and current attention/HC work. HIP waits include device work and are not removable CPU overhead. Instrumented time cannot replace saved unprofiled 128K rates.',
        next='Rank actual late-context boundary growth and PLE readiness before selecting a complete-chain or attention candidate; keep original inputs and controls.')
    output = ROOT/'config/q2-long-profile128-results.json'
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('state','device_duration_validation',
                                             'matched_embed_calls','server_exit_code','quartiles')},indent=2))


if __name__ == '__main__':
    main()
