#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the four native-C canonical curves without generating benchmark requests."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tarfile

from q2_native_curve import check_backend, client_argv

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
read, sha, require = common.read, common.sha, common.require


def inventory(archive, prefix):
    return {m.name[len(prefix):]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
            for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix)}


def arm(row, key, plan, host, native_host, native_source, core):
    directory = ROOT/'evidence'/row['label']
    result = common.artifacts(directory)
    transport = read(directory/'transport.json')
    point_only = plan.get('point_only', False)
    require(transport.get('point_only', False) == point_only, 'Focused/full workload mismatch')
    require(result['state'] == 'CANONICAL_HTTP_WORKLOAD_COMPLETE_NOT_PARITY_VERDICT'
            and result['mode'] == row['mode'] and result['model_access'] is True
            and len(result['commands']) == 8 and transport['native_curve'] is True
            and transport['rebuild_mmq'] is True and 'mmq_reuse' not in result
            and transport['source_variant'] == row['source_variant'], 'Wrong model run composition')
    require(result['models_before'] == result['models_after'] and
            result['binary_sha256'] == result['binary_sha256_after'] and
            result['native_bench_binary_sha256'] == result['native_bench_binary_sha256_after'] and
            result['native_bench_commit'] == native_source['commit'], 'Model or executable changed')
    require(result['locks'] == result['postflight_locks'] and
            [(r['device'], r['inode']) for r in result['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)] and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Lease/KFD mismatch')
    for command in [result, *result['commands']]:
        require(not any(command.get(k) for k in ('thermal_stop','timeout','postflight_error',
                    'foreign_kfd','lingering_descendants')), 'Runtime or process retirement failure')
    provider = (core['variants']['ud'] if key == 'ud' else
                read(ROOT/'config'/(plan.get('candidate_manifest', 'q2-iq2-prefill-scale-reuse-source.json') if key == plan.get('candidate_key', 'scale')
                                    else 'q2-iq2-signs-ordered-asm-source.json')))
    with tarfile.open(directory/'source.tar.gz') as source, \
         tarfile.open(host/'source.tar.gz') as h, \
         tarfile.open(native_host/'source.tar.gz') as nh:
        for prefix, files in [('source/', provider['files']), ('curve-core/',core['core_files']),
                              ('native-bench-core/', native_source['files'])]:
            require(inventory(source, prefix) == files, 'Frozen source differs: '+prefix)
        require(inventory(nh, 'native-bench-core/') == native_source['files'],
                'Native driver differs from .157 conformance')
        for name, digest in plan['fixtures'].items():
            a, b = source.extractfile(name).read(), h.extractfile(name).read()
            require(a == b and hashlib.sha256(a).hexdigest() == digest,
                    'Host-qualified harness differs: '+name)
    session = read(directory/'results/curve-session.json')
    require(session.get('point_only', False) == point_only, 'Session workload scope differs')
    variant = key if key in ('ud', plan.get('candidate_key', 'scale')) else 'ordered'
    require(session['state'] == 'CANONICAL_WORKLOAD_MEASURED_NOT_PARITY_VERDICT' and
            session.get('client_driver') == 'synapse-lie-bench-native-C' and
            session['client_exit_code'] == session['server_exit_code'] == 0 and
            session['server_binary_sha256'] == result['binary_sha256'] and
            session['client_binary_sha256'] == session['client_binary_sha256_after'] ==
                result['native_bench_binary_sha256'] and len(session['commands']) == 1,
            'Native client/server session did not complete')
    check_backend(session['backend_ready'], variant)
    check_backend(session['backend_after'], variant)
    remote = Path(transport['remote'])
    require(session['commands'][0]['argv'] == client_argv(remote/'build/native-bench/synapse-lie-bench',
            remote/'results/native-curve.jsonl', remote/'results/native-curve-graphs', variant,
            point_only=point_only),
            'Native client arguments changed')
    events = [json.loads(s) for s in (directory/'results/native-curve.jsonl').read_text().splitlines()]
    require(events[0]['schema'] == 'synapse-lie.http-curve-bench.v1' and
            events[-1]['event'] == 'complete' and events[-1]['exit_code'] == 0,
            'Native curve incomplete')
    requests = [e for e in events if e['event'] == 'request']
    points = [e for e in events if e['event'] == 'point']
    expected_points = [(depth, rep) for depth in plan['depths'] for rep in range(plan['repetitions'])]
    require([r['index'] for r in requests] == list(range(len(requests))) and
            events[-1]['requests'] == len(requests) and events[-1]['points'] == len(expected_points) and
            [(p['depth'], p['rep']) for p in points] == expected_points,
            'Incomplete canonical grid/history')
    summary = read(directory/'results/native-curve-graphs/summary.json')['primary']
    require(summary['identity'] == events[0] and
            [p for r in summary['configurations'] for p in r['observations']] == points,
            'C report differs from recorded protocol points')
    history = []
    for request in requests:
        o = request['observation']; timing = o['server_timings']
        require(timing['scope'] == 'synchronous_executor_calls' and timing['valid'] is True and
                timing['decode_mode'] == 'ar' and not timing['ssd_cached_tokens'] and
                not timing['mtp_drafted_tokens'] and not timing['mtp_accepted_tokens'],
                'Different request timing/decoding scope')
        history.append(dict(phase=request['phase'], depth=request['depth'], rep=request['rep'],
            attempt=request['attempt'], request=o['request'], assistant=o['assistant'],
            finish_reason=o['finish_reason'], usage=o['usage'],
            counts={k:timing[k] for k in ('cached_tokens','prefill_tokens','decode_tokens','decode_calls')}))
    for point in points:
        o = requests[point['request_index']]['observation']; timing = o['server_timings']
        require(point['rep'] in range(plan['repetitions']) and point['output_tokens'] == 128 and point['timing_source'] == 'lie' and
                abs(point['cached_tokens']-point['depth']) <= max(32,math.floor(point['depth']*.005)) and
                abs(point['prefill_tokens']-2048) <= 32, 'Invalid accepted physical counts')
        require(point['completion_sha256'] == hashlib.sha256(o['assistant']['content'].encode()).hexdigest(),
                'Completion identity mismatch')
        for metric, count, duration in [('pp_tps','prefill_tokens','prefill_ms'),('tg_tps','output_tokens','decode_ms')]:
            require(math.isfinite(point[metric]) and point[metric] > 0 and timing[duration] > 0 and
                    math.isclose(point[metric],point[count]*1000/timing[duration],rel_tol=1e-12),
                    'Throughput differs from completed executor duration')
        point['prefill_ms'], point['decode_ms'] = timing['prefill_ms'], timing['decode_ms']
    telemetry = [json.loads(s) for s in (directory/'results/telemetry.jsonl').read_text().splitlines()]
    require(telemetry and all(not t['over_limit'] for r in telemetry for t in r['thermal']),
            'Thermal gate failed in retained samples')
    devices = {t['device'] for r in telemetry for t in r['thermal']}
    peaks = {device: max(t['temperature_mc'] for r in telemetry for t in r['thermal']
                        if t['device'] == device)/1000 for device in sorted(devices)}
    cached = re.search(r'^Cached:\s+(\d+) kB$', result['meminfo'], re.M)
    require(cached is not None, 'Missing retained preflight file-cache observation')
    return dict(directory=str(directory.relative_to(ROOT)), command_exits=[c['exit_code'] for c in result['commands']],
        artifacts=len(result['artifacts']), requests=len(requests), rows=points, history=history,
        thermal_peaks_c=peaks, telemetry_samples=len(telemetry),
        preflight_linux_cached_gib=int(cached.group(1))/1048576,
        server_binary_sha256=result['binary_sha256'], client_binary_sha256=result['native_bench_binary_sha256'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--plan', type=Path, default=ROOT/'config/q2-native-scale-curve-plan.json')
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite comparison evidence')
    plan = read(args.plan)
    candidate = plan.get('candidate_key', 'scale')
    host = ROOT/'evidence'/plan['host']
    native_host = ROOT/'evidence'/plan['native_client']['conformance_label']
    for directory, count in ((host,22),(native_host,3)):
        h = common.artifacts(directory)
        require(h['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
                h['model_access'] is False and len(h['commands']) == 6, 'Host qualification missing')
        for name in ('03.log','06.log'):
            require(re.search(r'100% tests passed(?:, 0 tests failed)? out of '+str(count)+r'\b',
                              (directory/'results'/name).read_text()), 'Wrong conformance test count')
    native = read(ROOT/'config/q2-native-bench-source.json')
    require(sha(ROOT/'config/q2-native-bench-source.json') == plan['native_client']['source_manifest_sha256'],
            'Native benchmark source identity changed')
    core = read(ROOT/plan['server_manifest'])
    require(sha(ROOT/plan['server_manifest']) == plan['server_manifest_sha256'], 'Server manifest changed')
    for name, digest in plan['providers'].items():
        require(sha(ROOT/'config'/name) == digest, 'Provider decision changed')
    arms = {key: arm(row,key,plan,host,native_host,native,core)
            for key,row in zip(('before',candidate,'after','ud'),plan['arms'])}
    matches = {k: arms['before']['history'] == arms[k]['history'] for k in (candidate,'after')}
    # Compare actual structures first. Keep full payloads in the verified raw
    # JSONL evidence, and compact their identities in the tracked report.
    for data in arms.values():
        for request in data['history']:
            for key in ('request', 'assistant'):
                encoded = json.dumps(request.pop(key), sort_keys=True,
                                     ensure_ascii=False, separators=(',', ':')).encode()
                request[key+'_semantic_sha256'] = hashlib.sha256(encoded).hexdigest()
    cells = {(str(p['depth']) if plan['repetitions'] == 1 else f"{p['depth']}:{p['rep']}"):
             {k: v['rows'][i] for k,v in arms.items()}
             for i,p in enumerate(arms['before']['rows'])}
    result = dict(schema=plan['schema'].replace('-plan.', '-results.'), arms=arms, cells=cells,
        history_matches=matches, native_bench_commit=native['commit'],
        plan_sha256=sha(args.plan),
        model_inference=True, independent_model_quality='Unresolved; exact replay is not an independent quality certificate',
        promoted=False, goal_met=False)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(history_matches=matches,rows=len(cells),
        artifacts=sum(a['artifacts'] for a in arms.values()),output=str(args.output))))
    raise SystemExit(0 if all(matches.values()) else 1)


if __name__ == '__main__':
    main()
