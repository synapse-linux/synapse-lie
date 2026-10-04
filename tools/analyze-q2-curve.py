#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify collected paired HTTP depth sweeps before producing parity cells."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ('CMakeLists.txt', 'cmake/curve/CMakeLists.txt', 'tools/q2-remote.py',
            'tools/q2-runner.py', 'tools/q2_process.py', 'tools/q2_thermal.py',
            'tools/q2-canonical-http.py', 'tools/q2-curve-session.py',
            'tests/q2_canonical_http_test.py', 'tests/q2_remote_test.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def artifact_integrity(root):
    """Verify retained bytes independently of whether the command succeeded."""
    receipt = read(root/'results/result.json')
    transport, collection = read(root/'transport.json'), read(root/'collection.json')
    require(sha(root/'source.tar.gz') == transport['capsule_sha256'], 'Source capsule changed')
    require(sha(root/'results.tar.gz') == collection['sha256'], 'Results archive changed')
    for name, expected in receipt['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe evidence path')
        p = root/'results'/name
        require(p.stat().st_size == expected['bytes'] and sha(p) == expected['sha256'], 'Artifact changed: '+name)
    require(collection['verified_artifacts'] == len(receipt['artifacts']), 'Incomplete collection')
    return receipt, transport


def artifacts(root):
    receipt, transport = artifact_integrity(root)
    require(transport['exit_code'] == 0 and all(c['exit_code'] == 0 for c in receipt['commands']),
            'Command failure retained; cannot publish a complete curve')
    return receipt


def validate_recipe(request, curve, row, curve_dir, client, upstream):
    payload = request['payload']
    # Independently rebuild accepted prompts from the pinned recipe and
    # retained calibration/attempt, including the actual prefix reply.
    depth = row['depth']
    requests = row['accepted_request']-row['first_request']
    attempt = (requests-1)//2 if depth else requests
    require(0 <= attempt < 4 and (not depth or requests % 2 == 1), 'Invalid calibration history')
    overhead = curve['initial_calibration']['overhead']
    turn = upstream.turn_prompt(2048-overhead, row['ratio'], task='prose', depth=depth,
                                repetition=0, attempt=attempt)
    messages = [{'role':'user','content':turn}]
    if depth:
        prefix = upstream.synthetic_text(1+depth, max(1,round((depth-overhead-8)/row['ratio'])))
        preparation = read(curve_dir/f'request-{row["accepted_request"]-1:04d}.json')
        require(preparation['payload']['messages'] == [{'role':'user','content':prefix}] and
                preparation['payload']['max_tokens'] == 8 and not preparation['payload']['stream'],
                'Prefix preparation differs from canonical recipe')
        _, reply = client.parse_reply(preparation['response'], False)
        messages = [{'role':'user','content':prefix}, {'role':'assistant','content':reply}, *messages]
    require(payload['messages'] == messages, 'Measured workload differs from canonical recipe')


def model(root, key, host_root, manifest, client, upstream, experiment=None):
    require(experiment in (None, 'iq2-signs-ordered') and
            (experiment is None or key == 'q2'), 'Unknown provider experiment')
    r = artifacts(root)
    require(r['state'] == 'CANONICAL_HTTP_WORKLOAD_COMPLETE_NOT_PARITY_VERDICT' and
            r['mode'] == (key+'-curve-iq2' if experiment else key+'-curve') and
            r['model_access'], 'No completed model curve')
    if experiment:
        transport = read(root/'transport.json')
        require(transport['source_variant'] == 'curve-iq2-q2' and transport['rebuild_mmq']
                and 'mmq_reuse' not in r, 'IQ2 curve needs its full provider build')
    require(r['models_before'] == r['models_after'] and r['binary_sha256'] == r['binary_sha256_after'],
            'Model or binary identity changed')
    expected_leases = [(52,3232146), (52,3206482), (52,3228451), (55,45067)]
    require([(x['device'],x['inode']) for x in r['locks']] == expected_leases and
            r['locks'] == r['postflight_locks'] and not r['preflight_kfd'] and
            not r['postflight_kfd'], 'Ownership observations do not match the admitted run')
    with tarfile.open(root/'source.tar.gz') as archive, tarfile.open(host_root/'source.tar.gz') as host:
        for name in FIXTURES:
            raw = archive.extractfile(name).read()
            require(raw == host.extractfile(name).read(),
                    'Runtime/host fixture differs: '+name)
        for prefix, files in [('source', manifest['variants'][key]['files']),
                              ('curve-core', manifest['core_files'])]:
            actual = {m.name[len(prefix)+1:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                      for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix+'/')}
            require(actual == files, 'Frozen source composition differs: '+prefix)
    session = read(root/'results/curve-session.json')
    require(session['state'] == 'CANONICAL_WORKLOAD_MEASURED_NOT_PARITY_VERDICT' and
            session.get('provider_experiment') == experiment and
            session['variant'] == key and session['server_binary_sha256'] == r['binary_sha256'] and
            session['client_exit_code'] == 0 and session['server_exit_code'] == 0,
            'HTTP children did not complete/retire cleanly')
    curve_dir = root/'results/canonical-curve'
    curve = read(curve_dir/'curve.json')
    require(curve['state'] == 'MEASURED_NOT_PARITY_OR_QUALITY_VERDICT' and curve['variant'] == key and
            curve['depths'] == client.DEPTHS and curve['full_grid'] is True and
            not curve.get('instrumentation') and
            curve.get('provider_experiment') == experiment and
            curve['context_capacity'] == 133760 and curve['new_prompt_target'] == 2048 and
            curve['output_tokens'] == 128 and curve['timing_scope'] == client.TIMING_SCOPE,
            'Different or incomplete curve protocol')
    client.check_backend(curve['backend_before'], iq2_signs=experiment is not None)
    require([row['depth'] for row in curve['rows']] == client.DEPTHS, 'Missing/reordered depth rows')
    for row in curve['rows']:
        request = read(curve_dir/f'request-{row["accepted_request"]:04d}.json')
        require('error' not in request, 'Accepted request has an error')
        payload = request['payload']
        require(hashlib.sha256(json.dumps(payload).encode()).hexdigest() == request['payload_sha256'],
                'Request identity changed')
        sample, _ = client.parse_reply(request['response'], True)
        validate_recipe(request, curve, row, curve_dir, client, upstream)
        require(all(row[k] == v for k,v in vars(sample).items()), 'Reported row differs from raw server response')
        require(sample.completion_tokens == sample.decode_calls == 128 and
                abs(sample.prefill_tokens-2048) <= 32 and
                abs(sample.cached_prompt_tokens-row['depth']) <= max(32, int(row['depth']*.005)),
                'Physical token budget/calibration differs')
        require(sample.prompt_tokens+128 <= 133760 and payload['max_tokens'] == 128 and
                payload['temperature'] == 0 and payload['top_p'] == 1 and
                payload['frequency_penalty'] == payload['presence_penalty'] == 0 and
                payload['chat_template_kwargs'] == {'enable_thinking': False},
                'Sampling or context budget differs')
        timing = next(chunk['lie_timings'] for chunk in request['response']
                      if isinstance(chunk, dict) and 'lie_timings' in chunk)
        row.update({k:timing[k] for k in ('prefill_calls', 'cache_capture_ms',
                                          'cache_restore_ms', 'ssd_read_ms')})
        row['request_wall_ms'] = (request['ended_ns']-request['started_ns'])/1e6
    return dict(rows=curve['rows'], initial_calibration=curve['initial_calibration'],
                binary_sha256=r['binary_sha256'], source_capsule_sha256=sha(root/'source.tar.gz'),
                archive_sha256=sha(root/'results.tar.gz'), artifacts=len(r['artifacts']),
                source_files=len(manifest['core_files'])+len(manifest['variants'][key]['files']),
                command_exits=[x['exit_code'] for x in r['commands']],
                request_scope=curve['comparison_scope'], server_argv=session['server_argv'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('q2','ud','host','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite a result')
    spec = importlib.util.spec_from_file_location('curve_client', ROOT/'tools/q2-canonical-http.py')
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    host = artifacts(args.host)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'],
            'Host fixtures failed or accessed models')
    for name in ('03.log','06.log'):
        log = (args.host/'results'/name).read_text()
        require(any('100% tests passed out of '+str(n) in log for n in (18,19)) and
                'q2_canonical_http' in log, 'Missing Debug/ASan checks')
    manifest = read(ROOT/'config/q2-curve-source.json')
    upstream, _ = client.load_upstream(ROOT/'.deps/gufo-base')
    reports = {k:model(getattr(args,k),k,args.host,manifest,client,upstream) for k in ('q2','ud')}
    cells = []
    for q2, ud in zip(reports['q2']['rows'],reports['ud']['rows']):
        ratios = {metric:q2[metric]/ud[metric] for metric in
                  ('prefill_tokens_per_second','decode_tokens_per_second')}
        cells.append(dict(depth=q2['depth'], ratios=ratios,
                          parity_observed=all(v>=1 for v in ratios.values())))
    report = dict(schema='synapse-lie.q2-ud-canonical-comparison.v1',
                  scope='Pinned Gufo HTTP workload; common C17 completed-executor timers, one warmed observation per point',
                  models=reports, cells=cells, full_curve_parity_observed=all(c['parity_observed'] for c in cells),
                  repetition_needed_before_acceptance=True, numerical_qualified=False,
                  promoted=False, goal_met=False)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'cells':cells,'goal_met':False}))


if __name__ == '__main__':
    main()
