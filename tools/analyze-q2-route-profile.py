#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate canonical routing observations; estimate geometry, never speedup."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def geometry(counts, tokens, used):
    require(type(tokens) is int and tokens > 0 and type(used) is int and
            0 < used <= len(counts) <= 4096, 'Invalid routing dimensions')
    require(all(type(n) is int and 0 <= n <= tokens for n in counts) and
            sum(counts) == tokens*used, 'Invalid per-expert counts')
    widths = {w:sum((n+w-1)//w for n in counts) for w in (16,48,64,128)}
    down = 48 if tokens*used >= 16*len(counts) else 16
    gate = down
    if tokens >= 1024 and down == 48:
        gate = 128 if widths[128]*4 <= widths[64]*3 else 64
    groups = [(n+63)//64 for n in counts]
    paired = sum(n//2 for n in groups)
    tails = sum(n%2 for n in groups)
    return dict(down_rows=down, down_tiles=widths[down], gate_rows=gate,
        gate_tiles=widths[gate], live_16_row_fragments=widths[16],
        reserved_16_row_fragments=widths[gate]*(gate//16),
        mixed_128_tiles=paired, mixed_64_tiles=tails,
        mixed_reserved_16_row_fragments=paired*8+tails*4,
        mixed_launches=int(paired>0)+int(tails>0),
        active_experts=sum(n>0 for n in counts), max_expert_rows=max(counts),
        count_bands={str(hi):sum(lo < n <= hi for n in counts)
                     for lo,hi in ((-1,0),(0,16),(16,32),(32,48),(48,64),
                                   (64,128),(128,tokens)) if hi>lo})


def records(text):
    spans, pending = [], []
    last_end = 0
    for line in text.splitlines():
        if '"event":"q2_route_' not in line:
            continue
        row = json.loads(line)
        require(row.get('schema') == 1 and row.get('diagnostic_only') is True,
                'Invalid or failed routing observation')
        if row['event'] == 'q2_route_counts':
            pending.append(row)
            continue
        require(row['event'] == 'q2_route_forward' and row.get('completed') is True and
                row.get('valid') is True and type(row.get('prefill')) is bool,
                'Incomplete or unknown routing span')
        for key in ('id','position','tokens','expected_layers','observed_layers','started_ns','ended_ns'):
            require(type(row.get(key)) is int and row[key] >= 0, 'Invalid span integer')
        require(row['id'] == len(spans) and row['tokens'] > 0 and
                row['expected_layers'] > 0 and last_end <= row['started_ns'] < row['ended_ns'],
                'Noncontiguous or overlapping C1 spans')
        require(len(pending) == row['observed_layers'] ==
                (row['expected_layers'] if row['prefill'] else 0),
                'Missing or extra layer observations')
        require(row['prefill'] or row['tokens'] == 1, 'Non-AR decode span')
        for layer, event in enumerate(pending):
            require(event.get('forward_id') == row['id'] and event.get('layer') == layer and
                    type(event.get('at_ns')) is int and
                    row['started_ns'] <= event['at_ns'] <= row['ended_ns'] and
                    (layer == 0 or event['at_ns'] >= pending[layer-1]['at_ns']) and
                    event.get('tokens') == row['tokens'] and event.get('iq2_wmma') is True,
                    'Routing observation belongs to a different span/layer/path')
            require(type(event.get('experts')) is int and isinstance(event.get('counts'),list) and
                    event['experts'] == len(event['counts']), 'Invalid count array')
            derived = geometry(event['counts'], event['tokens'], event.get('used'))
            require(all(type(event.get(k)) is int and event[k] == derived[k]
                        for k in ('down_rows','down_tiles','gate_rows','gate_tiles')),
                    'Reported routing differs from actual selector geometry')
            event['geometry'] = derived
        row['layers'] = pending
        spans.append(row)
        pending = []
        last_end = row['ended_ns']
    require(spans and not pending, 'Missing or unterminated Forward observations')
    return spans


def attribute(events, request, sample):
    start, end = request['started_ns'], request['ended_ns']
    require(type(start) is int and type(end) is int and start < end, 'Invalid request interval')
    spans = [r for r in events if r['started_ns'] < end and r['ended_ns'] > start]
    require(spans and all(start <= r['started_ns'] < r['ended_ns'] <= end for r in spans),
            'Forward crosses HTTP request boundary')
    position, decode = sample.cached_prompt_tokens, False
    for row in spans:
        require(row['position'] == position and not (decode and row['prefill']),
                'Wrong prefix frontier or phase order')
        position += row['tokens']
        decode = decode or not row['prefill']
    pp, tg = [[r for r in spans if r['prefill'] == p] for p in (True,False)]
    require(sum(r['tokens'] for r in pp) == sample.prefill_tokens and
            len(tg) == sample.decode_calls == sample.completion_tokens == 128,
            'Profile does not cover complete accepted HTTP work')
    layers = [dict(forward_id=r['id'], position=r['position'], tokens=r['tokens'],
                   layer=event['layer'], **event['geometry']) for r in pp for event in r['layers']]
    totals = {k:sum(l[k] for l in layers) for k in (
        'gate_tiles','live_16_row_fragments','reserved_16_row_fragments',
        'mixed_128_tiles','mixed_64_tiles','mixed_reserved_16_row_fragments')}
    return dict(prefill_calls=len(pp), prefill_tokens=sample.prefill_tokens,
                decode_calls=len(tg), layers=layers, totals=totals)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('profile','host','control','output'):
        p.add_argument('--'+name, required=True, type=Path)
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite a routing report')
    common, client, iq2 = [load(n) for n in ('analyze-q2-curve.py','q2-canonical-http.py','analyze-q2-iq2-curve.py')]
    host, receipt = [common.artifacts(r) for r in (args.host,args.profile)]
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'],
            'Missing isolated host qualification')
    for name in ('03.log','06.log'):
        log = (args.host/'results'/name).read_text()
        require('100% tests passed out of 20' in log and 'q2_route_profile' in log,
                'Missing routing Debug/ASan checks')
    require(receipt['mode'] == 'q2-curve-routes' and receipt['state'] ==
            'CANONICAL_ROUTE_PROFILE_COMPLETE_NOT_BENCHMARK' and receipt['model_access'] and
            receipt['models_before'] == receipt['models_after'] and
            receipt['binary_sha256'] == receipt['binary_sha256_after'] and
            not receipt['preflight_kfd'] and not receipt['postflight_kfd'] and
            receipt['locks'] == receipt['postflight_locks'], 'Invalid diagnostic run identity/state')
    require([(x['device'],x['inode']) for x in receipt['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)], 'Different lease identities')
    manifest = common.read(ROOT/'config/q2-route-profile-source.json')
    parent = common.read(ROOT/'config/q2-iq2-signs-ordered-asm-source.json')
    require(manifest['parent_manifest_sha256'] == common.sha(ROOT/'config/q2-iq2-signs-ordered-asm-source.json'),
            'Ordered parent changed')
    changed = [k for k in parent['files'] if manifest['files'].get(k) != parent['files'][k]]
    require(changed == ['src/models/qwen38_flash_next/kernels/rocm/executor.cpp'] and
            manifest['files'].keys()-parent['files'].keys() == {'q2_route_profile.hpp'},
            'Diagnostic changes more than host observation')
    core = common.read(ROOT/'config/q2-curve-source.json')
    extra = ('experiments/q2_route_profile.hpp','tests/q2_route_profile.cpp',
             'tests/q2_route_profile_test.py','tools/analyze-q2-route-profile.py')
    with tarfile.open(args.profile/'source.tar.gz') as archive, tarfile.open(args.host/'source.tar.gz') as host_archive:
        for name in common.FIXTURES+extra:
            require(archive.extractfile(name).read() == host_archive.extractfile(name).read(),
                    'Host/model instrumentation differs: '+name)
        for prefix, expected in [('source',manifest['files']),('curve-core',core['core_files'])]:
            actual = {m.name[len(prefix)+1:]:hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                      for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix+'/')}
            require(actual == expected, 'Source composition differs: '+prefix)
    directory = args.profile/'results/canonical-curve'
    curve = common.read(directory/'curve.json')
    session = common.read(args.profile/'results/curve-session.json')
    require(curve['state'] == 'MEASURED_NOT_PARITY_OR_QUALITY_VERDICT' and
            curve['variant'] == session['variant'] == 'q2' and curve['full_grid'] is True and
            curve['context_capacity'] == 133760 and curve['new_prompt_target'] == 2048 and
            curve['output_tokens'] == 128 and curve['timing_scope'] == client.TIMING_SCOPE and
            curve['instrumentation'] == session['instrumentation'] == 'routing-counts' and
            curve['provider_experiment'] is session['provider_experiment'] is None and
            curve['headline_eligible'] is False and curve['depths'] == client.DEPTHS and
            [r['depth'] for r in curve['rows']] == client.DEPTHS and
            session['state'] == 'CANONICAL_ROUTE_PROFILE_COMPLETE_NOT_BENCHMARK' and
            session['server_binary_sha256'] == receipt['binary_sha256'] and
            session['server_exit_code'] == session['client_exit_code'] == 0, 'Incomplete or different profile')
    client.check_backend(curve['backend_before'], profile_routes=True)
    events = records((args.profile/'results/curve-server.log').read_text())
    upstream,_ = client.load_upstream(ROOT/'.deps/gufo-base')
    rows = []
    for row in curve['rows']:
        request = common.read(directory/f'request-{row["accepted_request"]:04d}.json')
        require(hashlib.sha256(json.dumps(request['payload']).encode()).hexdigest() == request['payload_sha256'],
                'Request payload identity changed')
        common.validate_recipe(request,curve,row,directory,client,upstream)
        sample,_ = client.parse_reply(request['response'],True)
        require(all(row[k] == v for k,v in vars(sample).items()), 'Recorded sample differs from HTTP response')
        rows.append(dict(depth=row['depth'], **attribute(events,request,sample)))
    control = common.artifacts(args.control)
    require(control['mode'] == 'q2-curve-iq2' and control['state'] ==
            'CANONICAL_HTTP_WORKLOAD_COMPLETE_NOT_PARITY_VERDICT',
            'History control is not the measured ordered-IQ2 curve')
    with tarfile.open(args.control/'source.tar.gz') as archive:
        for prefix, expected in [('source',parent['files']),('curve-core',core['core_files'])]:
            actual = {m.name[len(prefix)+1:]:hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                      for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix+'/')}
            require(actual == expected, 'History control source differs: '+prefix)
    replay = iq2.history(args.control/'results/canonical-curve',directory,client)
    report = dict(schema='synapse-lie.q2-route-profile.v1', rows=rows,
        forward_observations=len(events), routing_observations=sum(len(r['layers']) for r in events),
        history_replay=replay, headline_eligible=False, performance_gain_established=False,
        scope='Existing host counts on canonical HTTP curve; reserved tile geometry is not executed WMMA work or predicted time.',
        numerical_qualified=False, promoted=False, goal_met=False)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('forward_observations','routing_observations','headline_eligible')}))
    print(json.dumps({'history_exact':replay['exact'],'totals':[{'depth':r['depth'],**r['totals']} for r in rows]}))
    raise SystemExit(0 if replay['exact'] else 1)


if __name__ == '__main__':
    main()
