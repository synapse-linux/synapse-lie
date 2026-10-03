#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute host PLE costs inside the complete canonical HTTP workload."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
METRICS = ('hash_ns','start_ns','wait_ns','blocked_ns','copies_ns','decode_ns','pread_ns',
           'gathers','rows','unique_rows','cache_hits','io_rows','pread_calls','requested_bytes','returned_bytes')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def records(text):
    out = []
    last_end = 0
    for line in text.splitlines():
        if 'q2_curve_profile_error' in line:
            raise ValueError('Profiler failed to write a complete observation')
        if '"event":"q2_curve_forward"' not in line:
            continue
        r = json.loads(line)
        require(r.get('schema') == 1 and r.get('diagnostic_only') is True and
                r.get('completed') is True and r.get('valid') is True and
                r.get('process_io_valid') is True and type(r.get('prefill')) is bool,
                'Incomplete or invalid Forward profile')
        for key in ('position','tokens','started_ns','ended_ns','process_read_bytes',
                    'cache_slots','cache_bytes','workers'):
            require(type(r.get(key)) is int and r[key] >= 0, 'Invalid integer: '+key)
        require(r['tokens'] > 0 and r['cache_slots'] > 0 and r['workers'] > 0 and
                last_end <= r['started_ns'] < r['ended_ns'], 'Overlapping or invalid C1 spans')
        last_end = r['ended_ns']
        s = r['ple']
        require(set(s) == set(METRICS) and all(type(v) is int and v >= 0 for v in s.values()),
                'Invalid PLE counters')
        require(s['gathers'] == 1 and s['cache_hits']+s['io_rows'] == s['unique_rows'] <= s['rows']
                and s['blocked_ns'] <= s['wait_ns'] <= r['ended_ns']-r['started_ns']
                and s['returned_bytes'] <= s['requested_bytes'] and s['pread_calls'] >= s['io_rows'],
                'Incoherent PLE accounting')
        require(r['prefill'] or r['tokens'] == 1, 'Non-AR decode in C1 profile')
        out.append(r)
    require(out, 'Missing Forward observations')
    return out


def attribute(events, request, sample):
    start, end = request['started_ns'], request['ended_ns']
    require(type(start) is int and type(end) is int and start < end, 'Invalid request interval')
    rows = [r for r in events if r['started_ns'] < end and r['ended_ns'] > start]
    require(rows and all(start <= r['started_ns'] < r['ended_ns'] <= end for r in rows),
            'Forward crosses the HTTP request boundary')
    position = sample.cached_prompt_tokens
    decode_started = False
    for r in rows:
        require(r['position'] == position, 'Wrong cached/continuation frontier')
        require(not (decode_started and r['prefill']), 'Prefill after decode')
        decode_started = decode_started or not r['prefill']
        position += r['tokens']
    pp = [r for r in rows if r['prefill']]
    tg = [r for r in rows if not r['prefill']]
    require(sum(r['tokens'] for r in pp) == sample.prefill_tokens and
            len(tg) == sample.decode_calls == sample.completion_tokens == 128,
            'Forward counts differ from completed HTTP work')
    result = {}
    for phase, spans, server_ms in [('prefill',pp,sample.prefill_ms),('decode',tg,sample.decode_ms)]:
        duration = sum(r['ended_ns']-r['started_ns'] for r in spans)
        counters = {k:sum(r['ple'][k] for r in spans) for k in METRICS}
        require(duration <= server_ms*1e6+1, 'Inner Forward time exceeds outer executor time')
        result[phase] = dict(calls=len(spans), tokens=sum(r['tokens'] for r in spans),
            forward_ms=duration/1e6, server_executor_ms=server_ms,
            process_read_bytes=sum(r['process_read_bytes'] for r in spans), ple=counters,
            exposed_wait_fraction=counters['blocked_ns']/duration,
            cache_hit_fraction=counters['cache_hits']/counters['unique_rows'] if counters['unique_rows'] else 0)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('q2','ud','host','output'):
        p.add_argument('--'+key, required=True, type=Path)
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite a profile')
    ordinary = load('curve_analysis', ROOT/'tools/analyze-q2-curve.py')
    client = load('curve_client', ROOT/'tools/q2-canonical-http.py')
    upstream, _ = client.load_upstream(ROOT/'.deps/gufo-base')
    manifest = read(ROOT/'config/q2-curve-profile-source.json')
    core = read(ROOT/'config/q2-curve-source.json')
    host = ordinary.artifacts(args.host)
    require(not host['model_access'] and host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE',
            'Missing CPU validation')
    for name in ('03.log','06.log'):
        log = (args.host/'results'/name).read_text()
        require('100% tests passed out of 19' in log and 'q2_curve_profile' in log,
                'Missing profile Debug/ASan checks')
    result = {}
    for variant in ('q2','ud'):
        root = getattr(args,variant)
        receipt = ordinary.artifacts(root)
        require(receipt['mode'] == variant+'-curve-ple' and receipt['state'] ==
                'CANONICAL_PLE_PROFILE_COMPLETE_NOT_BENCHMARK' and receipt['model_access'] and
                receipt['models_before'] == receipt['models_after'] and
                receipt['binary_sha256'] == receipt['binary_sha256_after'] and
                not receipt['preflight_kfd'] and not receipt['postflight_kfd'] and
                receipt['locks'] == receipt['postflight_locks'], 'Profile identity/state mismatch')
        require([(x['device'],x['inode']) for x in receipt['locks']] ==
                [(52,3232146),(52,3206482),(52,3228451),(55,45067)], 'Different lease identities')
        with tarfile.open(root/'source.tar.gz') as archive, tarfile.open(args.host/'source.tar.gz') as host_archive:
            for name in ordinary.FIXTURES:
                require(archive.extractfile(name).read() == host_archive.extractfile(name).read(),
                        'Host/model fixtures differ: '+name)
            for prefix, expected in [('source',manifest['variants'][variant]['files']),('curve-core',core['core_files'])]:
                actual = {m.name[len(prefix)+1:]:hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                          for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix+'/')}
                require(actual == expected, 'Profile source differs: '+prefix)
        directory = root/'results/canonical-curve'
        curve = read(directory/'curve.json')
        session = read(root/'results/curve-session.json')
        require(curve['state'] == 'MEASURED_NOT_PARITY_OR_QUALITY_VERDICT' and
                curve['instrumentation'] == session['instrumentation'] == 'ple-forward' and
                curve['headline_eligible'] is False and curve['depths'] == client.DEPTHS and
                [r['depth'] for r in curve['rows']] == client.DEPTHS and
                session['state'] == 'CANONICAL_PLE_PROFILE_COMPLETE_NOT_BENCHMARK' and
                session['server_exit_code'] == session['client_exit_code'] == 0, 'Incomplete profile')
        client.check_backend(curve['backend_before'], True)
        events = records((root/'results/curve-server.log').read_text())
        rows = []
        for row in curve['rows']:
            request = read(directory/f'request-{row["accepted_request"]:04d}.json')
            require(hashlib.sha256(json.dumps(request['payload']).encode()).hexdigest() == request['payload_sha256'], 'Request payload identity changed')
            ordinary.validate_recipe(request,curve,row,directory,client,upstream)
            sample, _ = client.parse_reply(request['response'], True)
            require(all(row[k] == v for k,v in vars(sample).items()), 'Response/report mismatch')
            require(abs(sample.prefill_tokens-2048) <= 32 and
                    abs(sample.cached_prompt_tokens-row['depth']) <= max(32,int(row['depth']*.005)),
                    'Different physical workload')
            phases = attribute(events, request, sample)
            timing = next(c['lie_timings'] for c in request['response'] if isinstance(c,dict) and 'lie_timings' in c)
            require(phases['prefill']['calls'] == timing['prefill_calls'], 'Missing prefill calls')
            rows.append(dict(depth=row['depth'], request=row['accepted_request'],
                             completion_sha256=sample.completion_sha256, phases=phases))
        result[variant] = dict(rows=rows, forward_events=len(events),
            cache={k:events[0][k] for k in ('cache_slots','cache_bytes','workers','direct_io')},
            source_capsule_sha256=ordinary.sha(root/'source.tar.gz'), artifacts=len(receipt['artifacts']))
    report = dict(schema='synapse-lie.q2-curve-ple-profile.v1', models=result, diagnostic_only=True,
        scope='Completed host Forward calls aligned to actual HTTP request intervals; inner PLE wait is exposed host blocking. Summed parallel pread/dequant CPU time is not wall time. Process read_bytes includes all process storage reads.',
        headline_eligible=False, promoted=False, goal_met=False)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(rows=len(v['rows']),events=v['forward_events']) for k,v in result.items()}))


if __name__ == '__main__':
    main()
