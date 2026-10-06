#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the collected 256K curves after release; retain all phase durations."""
import csv
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tarfile
from q2_curve256 import client_argv, check_backend, server_argv

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
read, sha, require = common.read, common.sha, common.require


def events_at(directory):
    return [json.loads(line) for line in
            (directory/'results/native-curve.jsonl').read_text().splitlines()]


def phase_rows(events, label):
    rows = []
    for e in events:
        if e['event'] != 'request':
            continue
        o = e['observation']
        t = o['server_timings']
        require(t['valid'] is True and t['scope'] == 'synchronous_executor_calls'
                and t['decode_mode'] == 'ar' and not t['ssd_cached_tokens']
                and not t['mtp_drafted_tokens'] and not t['mtp_accepted_tokens'],
                'Request timing or decoding scope differs')
        row = dict(arm=label, **{k:e[k] for k in ('index','phase','depth','rep','attempt')})
        row.update({k:t[k] for k in ('cached_tokens','prefill_tokens','decode_tokens',
            'prefill_calls','decode_calls','prefill_ms','decode_ms','cache_capture_ms','cache_restore_ms')})
        row['pp_tps'] = t['prefill_tokens']*1000/t['prefill_ms'] if t['prefill_ms'] else None
        row['tg_tps'] = t['decode_tokens']*1000/t['decode_ms'] if t['decode_ms'] else None
        row['request_sha256'] = o['request_sha256']
        row['assistant_sha256'] = hashlib.sha256(json.dumps(o['assistant'],
            sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        rows.append(row)
    return rows


def inventory(archive, prefix):
    return {m.name[len(prefix):]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
            for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix)}


def attention_dispatch_audit(provider):
    """Bind the capacity-induced sparse fallback; this is source evidence."""
    findings = {}
    for key, variant in provider['variants'].items():
        base = ROOT/variant['source']/'src/models/qwen38_flash_next'
        paths = {'executor':base/'kernels/rocm/executor.cpp',
                 'kernels':base/'kernels/rocm/kernels.hip.cpp',
                 'config':base/'config.cpp'}
        needles = {
            'executor': ['(c.context_length + c.compress_ratio - 1) / c.compress_ratio',
                         'e->mask_words_ = (max_blocks + 31) / 32',
                         'rocm::Attention(s_.q, s.k_cache, s.v_cache, mask, mask_words_'],
            'kernels': ['kWmmaMaxMaskWords = 2048',
                        '(mask != nullptr && mask_words > kWmmaMaxMaskWords)',
                        'unsigned local_words[8]',
                        'kListCapacity = 4 * 512 + 4'],
            'config': ['c.indexer_top_k != 2048 || c.compress_ratio != 4']}
        files = {}
        for kind, path in paths.items():
            source = path.read_text()
            relative = path.relative_to(ROOT/variant['source']).as_posix()
            require(sha(path) == variant['files'][relative]
                    and all(n in source for n in needles[kind]),
                    'Attention capacity source changed: '+str(path))
            files[str(path.relative_to(ROOT))] = dict(sha256=sha(path),
                lines=[source[:source.index(n)].count('\n')+1 for n in needles[kind]])
        findings[key] = files
    return dict(evidence='source_inference_not_runtime_trace', source_files=findings,
        model_compress_ratio=4, original_declared_context=262144,
        original_mask_words=2048, effective_context=266240, effective_mask_words=2080,
        sparse_wmma_mask_word_limit=2048, sparse_wmma_rejected=True,
        fallback='AttentionKernel followed by SigmoidMul whenever sparse mask is present',
        numerical_device_bodies_changed=False, kernel_selection_changed_by_capacity=True,
        historical_speedup_isolated=False,
        limit='Both new arms share this fallback. Old capacity uses a different sparse '
              'prefill route, so old/new rates do not isolate the retained optimizations. '
              'Removing the guard alone is unsafe beyond262144: eight local words per '
              'thread and2052 shared union entries also bound the existing kernel.')


def arm(key, entry, plan, provider, host, pins):
    directory = ROOT/'evidence'/entry['label']
    result, transport = common.artifact_integrity(directory)
    require(result['state'] == 'CANONICAL_HTTP_WORKLOAD_COMPLETE_NOT_PARITY_VERDICT'
        and result['mode'] == entry['mode'] and result['model_access'] is True
        and len(result['commands']) == 6 and all(c['exit_code'] == 0 for c in result['commands'])
        and transport['exit_code'] == 0 and transport['native_curve'] is True
        and not transport['rebuild_mmq'] and not transport.get('point_only', False)
        and transport['source_variant'] == entry['variant'], 'Incomplete or different curve execution')
    require(result['models_before'] == result['models_after']
        and result['binary_sha256'] == result['binary_sha256_after']
        and result['native_bench_reused'] is True
        and result['native_bench_binary_sha256'] == result['native_bench_binary_sha256_after']
            == pins['native_bench']['binary_sha256'], 'Binary/model identity changed')
    reuse = result['mmq_reuse']
    require(reuse['unchanged_after'] is True and reuse['original_build_unchanged'] is True
        and reuse['changed'] == ['src/models/qwen38_flash_next/engine.cpp']
        and reuse['receipt_sha256'] == pins['providers'][entry['mode']]['receipt_sha256'],
        'Numerical archive reuse differs')
    require(result['locks'] == result['postflight_locks']
        and [(r['device'],r['inode']) for r in result['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)]
        and not result['preflight_kfd'] and not result['postflight_kfd'], 'Ownership mismatch')
    for row in [result, *result['commands']]:
        require(not any(row.get(k) for k in ('thermal_stop','timeout','postflight_error',
            'foreign_kfd','lingering_descendants')), 'Runtime termination failure')
    with tarfile.open(directory/'source.tar.gz') as archive, tarfile.open(host/'source.tar.gz') as h:
        for prefix, files in [('source/',provider['variants'][key]['files']),
                              ('curve-core/',provider['core_files'])]:
            require(inventory(archive,prefix) == files, 'Source inventory changed: '+prefix)
        for name, digest in {**plan['fixtures'],**plan['manifests']}.items():
            payload = archive.extractfile(name).read()
            require(payload == h.extractfile(name).read()
                and hashlib.sha256(payload).hexdigest() == digest, 'Host capsule differs: '+name)
    session = read(directory/'results/curve-session.json')
    require(session['state'] == 'CANONICAL_WORKLOAD_MEASURED_NOT_PARITY_VERDICT'
        and session['client_driver'] == 'synapse-lie-bench-native-C'
        and session['client_exit_code'] == session['server_exit_code'] == 0
        and len(session['commands']) == 1
        and session['client_binary_sha256'] == session['client_binary_sha256_after']
            == result['native_bench_binary_sha256']
        and session['server_binary_sha256'] == result['binary_sha256'], 'HTTP session differs')
    variant = 'ordered' if key == 'q2' else 'ud'
    check_backend(session['backend_ready'],variant)
    check_backend(session['backend_after'],variant)
    remote = Path(transport['remote'])
    command = session['commands'][0]['argv']
    require(command == client_argv(command[0],remote/'results/native-curve.jsonl',
        remote/'results/native-curve-graphs',variant), 'Client recipe changed')
    argv = session['server_argv']
    require(argv == server_argv(argv[0],argv[argv.index('--model')+1],
        argv[argv.index('--management-port')+1]), 'Server recipe changed')
    events = events_at(directory)
    points = [e.copy() for e in events if e['event'] == 'point']
    requests = [e for e in events if e['event'] == 'request']
    require(events[-1]['event'] == 'complete' and events[-1]['exit_code'] == 0
        and events[-1]['requests'] == len(requests) and events[-1]['points'] == len(plan['depths'])
        and [(p['depth'],p['rep']) for p in points] == [(d,0) for d in plan['depths']]
        and [r['index'] for r in requests] == list(range(len(requests))), 'Incomplete canonical history')
    summary = read(directory/'results/native-curve-graphs/summary.json')['primary']
    require(summary['identity'] == events[0]
        and [p for c in summary['configurations'] for p in c['observations']] == points,
        'Native protocol report disagrees')
    phases = phase_rows(events,key)
    for p in points:
        request = requests[p['request_index']]
        o, t = request['observation'], request['observation']['server_timings']
        require(request['phase'] == 'measured' and p['output_tokens'] == 128
            and p['timing_source'] == 'lie'
            and abs(p['cached_tokens']-p['depth']) <= max(32,math.floor(p['depth']*.005))
            and abs(p['prefill_tokens']-2048) <= 32
            and p['prompt_tokens'] + p['output_tokens'] <= plan['context_capacity'],
            'Accepted physical counts differ')
        require(hashlib.sha256(o['assistant']['content'].encode()).hexdigest() == p['completion_sha256'],
                'Completion identity differs')
        for metric, count, duration in [('pp_tps','prefill_tokens','prefill_ms'),
                                        ('tg_tps','output_tokens','decode_ms')]:
            require(math.isfinite(p[metric]) and p[metric] > 0 and t[duration] > 0
                and math.isclose(p[metric],p[count]*1000/t[duration],rel_tol=1e-12),
                'Rate differs from completed executor duration')
        p.update({k:t[k] for k in ('prefill_ms','decode_ms','prefill_calls','decode_calls',
                                   'cache_capture_ms','cache_restore_ms')})
        prefix = [r for r in phases if r['phase'] == 'prefix' and r['depth'] == p['depth']
                  and r['rep'] == p['rep'] and r['attempt'] == p['attempt']]
        require(len(prefix) == (1 if p['depth'] else 0), 'Accepted prefix request missing')
        for field in ('prefill_ms','prefill_tokens','cached_tokens','pp_tps'):
            p['prefix_'+field] = prefix[0][field] if prefix else None
        all_prefixes = [r for r in phases if r['phase'] == 'prefix' and r['depth'] == p['depth']]
        p['prefix_requests'] = len(all_prefixes)
        for field in ('prefill_ms','prefill_tokens'):
            p['prefix_total_'+field] = sum(r[field] for r in all_prefixes)
    telemetry = [json.loads(x) for x in (directory/'results/telemetry.jsonl').read_text().splitlines()]
    require(telemetry and all(not t['over_limit'] for x in telemetry for t in x['thermal']),
            'Thermal gate failed')
    devices = {t['device'] for x in telemetry for t in x['thermal']}
    return dict(label=entry['label'],rows=points,phases=phases,requests=len(requests),
        command_exits=[c['exit_code'] for c in result['commands']],artifacts=len(result['artifacts']),
        server_binary_sha256=result['binary_sha256'],mmq_reuse=reuse,
        thermal_peaks_c={d:max(t['temperature_mc'] for x in telemetry for t in x['thermal']
                             if t['device']==d)/1000 for d in devices})


def main():
    plan_path = ROOT/'config/q2-curve256-v3-plan.json'
    release_path = ROOT/'config/q2-curve256-v3-window-release.json'
    plan, release = read(plan_path), read(release_path)
    require(release['state'] == 'Q2_CURVE256_WINDOW_RELEASED' and not release['gpu_reserved']
        and release['plan_sha256'] == sha(plan_path) and not release['kfd']
        and not release['owned_group_members'], 'Collect and release before analysis')
    for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen runtime changed: '+name)
    host = ROOT/'evidence'/plan['host']
    h = common.artifacts(host)
    require(h['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not h['model_access']
        and sha(host/'results/result.json') == plan['host_result_sha256'], 'Host gate differs')
    provider = read(ROOT/'config/q2-curve256-headroom-source.json')
    dispatch = attention_dispatch_audit(provider)
    pins = read(ROOT/'config/q2-curve256-binaries.json')
    arms = {key:arm(key,entry,plan,provider,host,pins)
            for key,entry in zip(('q2','ud'),plan['arms'])}
    for entry in plan['arms']:
        root = ROOT/'evidence'/entry['label']
        require(read(root/'results/result.json')['finished_at'] < release['at']
            and (root/'collection.json').stat().st_mtime <=
                datetime.datetime.fromisoformat(release['at']).timestamp(),
            'Release preceded terminal collection')
    historical_path = ROOT/'config/q2-native-row-curve-results.json'
    historical = read(historical_path)
    # Keep both unchanged old controls; never pick whichever is favorable.
    history = {key:[r.copy() for r in historical['arms'][key]['rows']] for key in ('before','after')}
    for key in history:
        old_directory = ROOT/historical['arms'][key]['directory']
        common.artifacts(old_directory)
        old_phases = phase_rows(events_at(old_directory),'historical_'+key)
        for row in history[key]:
            prefixes = [r for r in old_phases if r['phase']=='prefix' and r['depth']==row['depth']]
            row['prefix_requests'] = len(prefixes)
            for field in ('prefill_ms','prefill_tokens'):
                row['prefix_total_'+field] = sum(r[field] for r in prefixes)
    cells = []
    for q,u in zip(arms['q2']['rows'],arms['ud']['rows']):
        cell = dict(depth=q['depth'],q2=q,ud=u,
            q2_vs_ud_PP_percent=100*(q['pp_tps']/u['pp_tps']-1),
            q2_vs_ud_TG_percent=100*(q['tg_tps']/u['tg_tps']-1))
        for key, rows in history.items():
            old = next((r for r in rows if r['depth']==q['depth']),None)
            cell['historical_'+key] = old
            cell['q2_vs_historical_'+key+'_PP_percent'] = 100*(q['pp_tps']/old['pp_tps']-1) if old else None
        cells.append(cell)
    report = dict(schema='synapse-lie.q2-curve256-results.v1',plan_sha256=sha(plan_path),
        release_sha256=sha(release_path),arms=arms,cells=cells,historical=history,
        historical_report_sha256=sha(historical_path),historical_capacity=133760,
        new_capacity=266240,model_declared_capacity=262144,
        numerical_kernels_changed=False,capacity_extrapolation_quality_qualified=False,
        attention_dispatch=dispatch,
        comparison='Same canonical recipe, frozen native client and old/new physical counts retained. '
                   'Historical controls have smaller capacity and separate cache history; one accepted point per depth '
                   'does not establish a causal or statistical speedup. Capacity266240 also disables sparse WMMA '
                   'for both new arms, unlike historical capacity. Fixed exact2048 benchmark remains separate.',
        fixed_point_changed=False,independent_quality=False,goal_met=False)
    output = ROOT/'config/q2-curve256-results.json'
    require(not output.exists(), 'Preserve existing report')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    out = ROOT/'docs/figures/q2-curve256';out.mkdir(exist_ok=False)
    columns = ['arm','depth','cached_tokens','prefill_tokens','output_tokens','prefill_ms','decode_ms',
        'pp_tps','tg_tps','prefill_calls','decode_calls','cache_capture_ms','cache_restore_ms',
        'ttft_seconds','wall_seconds','prefix_prefill_tokens','prefix_cached_tokens','prefix_prefill_ms','prefix_pp_tps',
        'prefix_requests','prefix_total_prefill_tokens','prefix_total_prefill_ms',
        'completion_sha256','request_sha256']
    with (out/'points.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');writer.writeheader()
        for key,data in arms.items():
            for row in data['rows']:writer.writerow({c: key if c=='arm' else row[c] for c in columns})
    phases=[p for data in arms.values() for p in data['phases']]
    with (out/'all-requests.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(phases[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(phases)
    print(json.dumps(dict(points=len(cells)*2,requests=len(phases),artifacts=sum(a['artifacts'] for a in arms.values()),
                          output=str(output))))


if __name__ == '__main__':
    main()
