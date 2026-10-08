#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify saved-array Q8 stream ordering without rerunning inference controls."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def artifacts(folder):
    result = read(folder/'results/result.json')
    for name, row in result['artifacts'].items():
        path = folder/'results'/name
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'Retained artifact changed: '+name)
    return result


def differences(expected, actual, n):
    require(len(expected) == len(actual), 'Output extent changed')
    result = dict(bytes=0, live_codes=0, live_scale_bytes=0, padding=0,
                  overwritten_with_ff=0, code_positions=[0]*32)
    for i, (reference, observed) in enumerate(zip(expected, actual)):
        if reference == observed:
            continue
        result['bytes'] += 1
        result['overwritten_with_ff'] += observed == 255
        tile, offset = divmod(i, 576)
        row = (tile//80)*16 + (offset//16)%16 if offset < 512 else (tile//80)*16 + (offset-512)//4
        if row >= n:
            result['padding'] += 1
        elif offset < 512:
            result['live_codes'] += 1
            result['code_positions'][(offset//256)*16 + offset%16] += 1
        else:
            result['live_scale_bytes'] += 1
    return result


def main():
    output = ROOT/'config/q2-shared-q8-oracle-replay-results.json'
    require(not output.exists(), 'Refusing to overwrite replay results')
    plan_path = ROOT/'config/q2-shared-q8-oracle-replay-r3-plan.json'
    plan = read(plan_path)
    folder = ROOT/'evidence'/plan['label']
    result = artifacts(folder)
    transport = read(folder/'transport.json')
    require(result['state'] == 'SAVED_ARRAY_ORACLE_REPLAY_COMPLETE_NOT_MODEL_QUALITY' and
            [c['exit_code'] for c in result['commands']] == [0, 0, 0] and
            transport['exit_code'] == 0 and not result['model_access'], 'Replay scope or exit changed')
    require(result['binary_sha256'] == result['binary_sha256_after'], 'Binary changed')
    require(result['oracle_replay_data'] == result['oracle_replay_data_after'] and
            result['oracle_replay_data']['plan_sha256'] == sha(plan_path) and
            result['oracle_replay_data']['arrays'] == plan['arrays'], 'Input pre/post receipt differs')
    require(sha(folder/'source.tar.gz') == transport['capsule_sha256'], 'Replay capsule changed')
    host_folder = ROOT/'evidence'/plan['host']
    host = artifacts(host_folder)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            [c['exit_code'] for c in host['commands']] == [0]*6, 'Host gate incomplete')
    require(sha(ROOT/plan['host_receipt']) == plan['host_receipt_sha256'], 'Host receipt changed')
    host_receipt = read(ROOT/plan['host_receipt'])
    require(sha(host_folder/'source.tar.gz') == host_receipt['capsule_sha256'] and
            sha(host_folder/'results.tar.gz') == host_receipt['archive_sha256'] and
            sha(host_folder/'results/result.json') == host_receipt['result_sha256'], 'Host evidence changed')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 23' in (host_folder/'results'/name).read_text(), 'Host tests absent')
    corpus = ROOT/plan['source_results']
    require(sha(corpus/'result.json') == plan['origin_receipt_sha256'], 'Original R3 receipt changed')
    for archive_path in (folder/'source.tar.gz', host_folder/'source.tar.gz'):
        with tarfile.open(archive_path) as archive:
            for name, expected in plan['fixtures'].items():
                require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected,
                        'Frozen fixture changed in capsule: '+name)
            if archive_path == folder/'source.tar.gz':
                for name, row in plan['arrays'].items():
                    data = archive.extractfile('oracle-replay-data/'+name).read()
                    require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'],
                            'Staged array changed: '+name)
    with tarfile.open(corpus.parent/'source.tar.gz') as archive:
        require(hashlib.sha256(archive.extractfile('tests/q2_shared_q8_scalar_oracle.hip').read()).hexdigest() ==
                plan['original_oracle_source_exact_sha256'], 'Independent GPU arithmetic changed')
    require(plan['fixtures']['tests/q2_shared_q8_scalar_oracle.hip'] ==
            plan['original_oracle_source_exact_sha256'], 'Replay GPU arithmetic differs')
    log = (folder/'results/03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    outputs = [e for e in events if e['event'] == 'oracle_replay']
    historical = [e for e in events if e['event'] == 'oracle_historical']
    shapes = ((96, 0), (97, 1), (127, 2), (129, 0), (2048, 0))
    require(len(outputs) == 80 and len(historical) == 5 and 'PASS ordered independent Q8' in log,
            'Incomplete replay matrix')
    identity = {(e['n'], e['pattern'], e['rep'], e['ordered']) for e in outputs}
    require(identity == {(n, p, r, ordered) for n, p in shapes for r in range(8) for ordered in (False, True)},
            'Duplicate or missing replay arm')
    rows, old_rows = [], []
    for n, p in shapes:
        prefix = 'shared-q8-n'+str(n)+'-p'+str(p)
        expected = (corpus/(prefix+'-q8-reference.bin')).read_bytes()
        for suffix in ('mixed-reference.bin', 'q8-reference.bin', 'independent-q8.bin'):
            name = prefix+'-'+suffix
            require(sha(corpus/name) == plan['arrays'][name]['sha256'], 'Retained array changed: '+name)
        old = differences(expected, (corpus/(prefix+'-independent-q8.bin')).read_bytes(), n)
        require(old['bytes'] == next(e['different_bytes'] for e in historical if e['n'] == n),
                'Historical difference count differs')
        old_rows.append(dict(n=n, pattern=p, differences=old))
        for event in (e for e in outputs if e['n'] == n and e['pattern'] == p):
            path = folder/'results'/event['output']
            actual = path.read_bytes()
            delta = differences(expected, actual, n)
            require(delta['bytes'] == event['different_bytes'] and len(actual) == event['bytes'] and
                    event['guard_exact'] and event['ordered'] == bool((event['rep']+event['order']) & 1),
                    'Replay byte/guard/order record differs')
            rows.append(dict(**event, differences=delta, sha256=sha(path)))
    ordered = [r for r in rows if r['ordered']]
    legacy = [r for r in rows if not r['ordered']]
    require(all(r['differences']['bytes'] == 0 for r in ordered), 'Ordered independent oracle differs')
    release_path = ROOT/'config/q2-shared-q8-oracle-replay-r3-window-release.json'
    release = read(release_path)
    require(not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
            release['model_stats_unchanged'] and len(release['leases']) == 4, 'Window still live or mutated')
    inventory_path = ROOT/'config/q2-rejected-test-reaudit.json'
    inventory = read(inventory_path)
    for candidate in inventory['candidates']:
        require(sha(ROOT/candidate['result']) == candidate['source_sha256'], 'Original failed report changed')
    summaries = []
    for n, p in shapes:
        arms = [r for r in legacy if r['n'] == n]
        summaries.append(dict(n=n, pattern=p, ordered_exact=8,
                              legacy_exact=sum(r['differences']['bytes'] == 0 for r in arms),
                              legacy_different_bytes=[r['differences']['bytes'] for r in arms]))
    report = dict(schema='synapse-lie.q2-shared-q8-oracle-replay.v1',
        state='INDEPENDENT_Q8_FIXTURE_STREAM_RACE_CONFIRMED',
        plan_sha256=sha(plan_path), result_sha256=sha(folder/'results/result.json'),
        archive_sha256=sha(folder/'results.tar.gz'), capsule_sha256=transport['capsule_sha256'],
        binary_sha256=result['binary_sha256'], command_exits=[0, 0, 0],
        host_receipt_sha256=plan['host_receipt_sha256'],
        release_sha256=sha(release_path), independent_gpu_math_exact=True,
        saved_arrays_verified=15, fixtures_verified=10, artifacts_verified=len(result['artifacts']),
        ordered_exact=len(ordered), ordered_total=len(ordered),
        legacy_exact=sum(r['differences']['bytes'] == 0 for r in legacy), legacy_total=len(legacy),
        shape_summary=summaries, historical=old_rows, replay=rows,
        false_gpu_format_rejection_confirmed_for='shared-q8 producer R3 at127/2048',
        original_rejected_reports_verified=len(inventory['candidates']),
        confirmed_false_candidate_families=['shared-q8'],
        inference_controls_rerun=False, model_forward=False, new_performance_measurement=False,
        original_failures_preserved=True, numerical_thresholds_changed=False,
        full_curve_admitted=False, goal_met=False,
        limits='Confirms cross-stream fixture initialization corrupts the unchanged independent GPU oracle. All40 same-stream outputs exactly reproduce original production Q8 bytes, while39/40 legacy outputs differ. This does not classify all19 reports as false, qualify unrelated kernels, add another model gain, or establish task quality/context parity.')
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('state', 'ordered_exact', 'legacy_exact', 'shape_summary',
        'artifacts_verified', 'original_rejected_reports_verified', 'release_sha256')}))


if __name__ == '__main__':
    main()
