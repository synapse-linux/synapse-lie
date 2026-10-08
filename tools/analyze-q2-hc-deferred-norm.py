#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the saved, rejected deferred-normalization component experiment."""
import collections
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('q2-hc-deferred-norm-host-r1', 'q2-hc-deferred-norm-micro-r1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def receipt(label):
    path = ROOT / 'evidence' / label
    result = json.loads((path / 'results/result.json').read_text())
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    require(result.get('finished_at') and not result['model_access'], 'Incomplete or model arm')
    for name, meta in result['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
        data = (path / 'results' / name).read_bytes()
        require(len(data) == meta['bytes'] and sha(data) == meta['sha256'], 'Artifact differs: ' + name)
    require(collection['verified_artifacts'] == len(result['artifacts']), 'Collection differs')
    require(sha((path / 'source.tar.gz').read_bytes()) == transport['capsule_sha256'], 'Capsule differs')
    require(sha((path / 'results.tar.gz').read_bytes()) == collection['sha256'], 'Result archive differs')
    thermal = {}
    for line in (path / 'results/telemetry.jsonl').read_text().splitlines():
        for sensor in json.loads(line)['thermal']:
            require(not sensor['over_limit'], 'Thermal stop')
            thermal[sensor['device']] = max(thermal.get(sensor['device'], -273), sensor['temperature_mc'] / 1000)
    return path, result, transport, thermal


def main():
    hp, host, ht, hthermal = receipt(LABELS[0])
    gp, gpu, gt, gthermal = receipt(LABELS[1])
    require(host['mode'] == 'cpu' and gpu['mode'] == 'hc-deferred-bench', 'Unexpected modes')
    require([c['exit_code'] for c in host['commands']] == [0] * 6 and ht['exit_code'] == 0,
            'Host validation failed')
    require(sum((hp / 'results' / name).read_text().count('100% tests passed out of 12')
                for name in host['artifacts'] if name.endswith('.log')) == 2, 'Incomplete CTest cohorts')
    require([c['exit_code'] for c in gpu['commands']] == [0, 0, 1] and gt['exit_code'] == 1,
            'Actual failed numerical exit not preserved')
    require(gpu['binary_sha256'] == gpu['binary_sha256_after'], 'Binary changed')
    fixtures = {}
    with tarfile.open(gp / 'source.tar.gz') as capsule:
        for name in ('tests/q2_hc_deferred_norm.cpp', 'tests/q2_hc_sequence.cpp',
                     'tests/q2_hc_norm_half.cpp', 'tests/q2_hc_moe_fused.cpp',
                     'cmake/hip/CMakeLists.txt'):
            fixtures[name] = sha(capsule.extractfile(name).read())
            require(fixtures[name] == sha((ROOT / name).read_bytes()), 'Fixture differs: ' + name)
        source = ROOT / gt['source_path']
        files = [p for p in source.rglob('*') if p.is_file()]
        for file in files:
            member = 'source/' + str(file.relative_to(source))
            require(sha(capsule.extractfile(member).read()) == sha(file.read_bytes()), 'Source differs: ' + member)
    events = [json.loads(line) for line in (gp / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    counts = collections.Counter(x['event'] for x in events)
    require(counts == {'hc_deferred_buffer': 130, 'hc_deferred_replay': 26,
                       'hc_deferred_microbench': 20, 'hc_deferred_consumer_oracle': 18,
                       'hc_sequence_norm_oracle': 8, 'hc_sequence_replay': 8}, 'Incomplete events')
    cases = {f'hc-deferred-n{n}-p{p}-moe{m}-i{i}' for n, p, i in
             ((96, 0, 1), (97, 1, 1), (129, 2, 1), (257, 0, 0)) for m in (0, 1)}
    benches = {f'hc-deferred-bench-moe{m}-rep{r}' for m in (0, 1) for r in range(5)}
    labels = cases | {x + '-after-refusal' for x in cases} | benches
    buffers = [x for x in events if x['event'] == 'hc_deferred_buffer']
    replays = [x for x in events if x['event'] == 'hc_deferred_replay']
    require({x['label'] for x in replays} == labels, 'Replay coverage differs')
    for label in labels:
        require({x['buffer'] for x in buffers if x['label'] == label} ==
                {'residual', 'norm', 'silu_down', 'mixed', 'inject'}, 'Buffer coverage differs')
    for event in buffers:
        require(event['exact'] == (event['reference_sha256'] == event['candidate_sha256']), 'Hash/exact contradiction')
    for event in replays:
        for name in ('half', 'low'):
            require(event[name + '_exact'] == (event['reference_' + name + '_sha256'] ==
                    event['candidate_' + name + '_sha256']), 'Half hash/exact contradiction')
    prefix = [x for x in events if x['event'] == 'hc_sequence_replay']
    require({x['label'] for x in prefix} == cases, 'Prefix coverage differs')
    require(all(x['res_exact'] and x['half_exact'] and x['scalar_half_exact'] and x['down_exact']
                and not x['norm_exact'] for x in prefix), 'Observed prefix behavior changed')
    oracles = [x for x in events if x['event'] in ('hc_sequence_norm_oracle', 'hc_deferred_consumer_oracle')]
    require(all(x['pass'] for x in oracles), 'Oracle result differs')
    require(all(not x['exact'] for x in replays), 'Recorded complete replay changed')
    timings = [x for x in events if x['event'] == 'hc_deferred_microbench']
    summaries = []
    for moe in (False, True):
        medians = []
        for deferred in (False, True):
            group = [x for x in timings if x['moe'] == moe and x['deferred'] == deferred]
            require(len(group) == 5 and {x['rep'] for x in group} == set(range(5)), 'Timing coverage differs')
            require(all(x['tokens'] == 2048 and x['iterations'] == 16 and x['weight_bytes'] == 209715200
                        and x['allocation'] == ((x['rep'] % 2) ^ int(deferred)) for x in group),
                    'Timing contract differs')
            values = [x['microseconds_per_iteration'] for x in group]
            require(all(x > 0 for x in values), 'Invalid duration')
            median = statistics.median(values)
            medians.append(median)
            summaries.append(dict(moe=moe, deferred=deferred, samples_us=values,
                                  median_us=median, min_us=min(values), max_us=max(values)))
        summaries[-1]['time_change_percent'] = 100 * (medians[1] / medians[0] - 1)
    saved = []
    for name, meta in gpu['artifacts'].items():
        if '-reference-' not in name:
            continue
        other = name.replace('-reference-', '-candidate-')
        if other not in gpu['artifacts']:
            other = name.replace('-reference-', '-paired-')
        require(other in gpu['artifacts'], 'Missing paired capture')
        saved.append(dict(reference=name, candidate=other, exact=meta == gpu['artifacts'][other]))
    require(len(saved) == 22, 'Incomplete saved captures')
    report = dict(scope='Synthetic complete HC cycle; no model throughput or reactive gain',
                  validation_pass=True, numerical_qualification_pass=False, promoted=False,
                  source_files_verified=len(files), fixture_hashes=fixtures,
                  source_capsules={LABELS[0]: ht['capsule_sha256'], LABELS[1]: gt['capsule_sha256']},
                  binary_sha256=gpu['binary_sha256'],
                  command_exits={LABELS[0]: [c['exit_code'] for c in host['commands']],
                                 LABELS[1]: [c['exit_code'] for c in gpu['commands']]},
                  artifact_counts={LABELS[0]: len(host['artifacts']), LABELS[1]: len(gpu['artifacts'])},
                  temperature_max_c={LABELS[0]: hthermal, LABELS[1]: gthermal},
                  summaries=summaries, saved_pairs=saved, event_counts=counts, events=events)
    (ROOT / 'config/q2-hc-deferred-norm-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('validation_pass', 'numerical_qualification_pass',
                                          'promoted', 'source_files_verified', 'artifact_counts',
                                          'temperature_max_c', 'summaries')}))


if __name__ == '__main__':
    main()
