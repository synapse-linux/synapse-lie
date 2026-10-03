#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate saved sequence receipts and report all paired component samples."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def arm(label, *, library=False):
    path = ROOT / 'evidence' / label
    result = json.loads((path / 'results/result.json').read_text())
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    mode = 'hc-library-norm-bench' if library else 'hc-sequence-bench'
    prefix = 'hc-library-norm' if library else 'hc-sequence'
    require(result['mode'] == mode and not result['model_access'],
            'Unexpected runtime scope')
    if library:
        require(transport['source_variant'] == 'library-norm-cycle', 'Wrong library source')
        require(result['preflight_kfd'] == result['postflight_kfd'] == [], 'GPU clients remain')
        require([(x['device'], x['inode']) for x in result['locks']] ==
                [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)], 'Lease identity differs')
    require(len(result['commands']) == 3 and
            [c['exit_code'] for c in result['commands'][:2]] == [0, 0],
            'Build did not finish successfully')
    require(result['binary_sha256'] == result['binary_sha256_after'], 'Binary changed')
    for name, meta in result['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                'Unsafe artifact path')
        data = (path / 'results' / name).read_bytes()
        require(len(data) == meta['bytes'] and sha(data) == meta['sha256'],
                'Artifact mismatch: ' + name)
    require(collection['verified_artifacts'] == len(result['artifacts']), 'Collection count differs')
    require(sha((path / 'source.tar.gz').read_bytes()) == transport['capsule_sha256'],
            'Capsule differs')
    require(sha((path / 'results.tar.gz').read_bytes()) == collection['sha256'],
            'Results archive differs')
    frozen = {}
    with tarfile.open(path / 'source.tar.gz') as capsule:
        fixtures = ['tests/q2_hc_sequence.cpp', 'tests/q2_hc_norm_half.cpp',
                    'tests/q2_hc_moe_fused.cpp', 'cmake/hip/CMakeLists.txt']
        if library:
            fixtures += ['tests/q2_hc_library_norm.cpp']
        for name in fixtures:
            frozen[name] = sha(capsule.extractfile(name).read())
            require(frozen[name] == sha((ROOT / name).read_bytes()), 'Fixture changed: ' + name)
        source = ROOT / transport['source_path']
        files = [p for p in source.rglob('*') if p.is_file()]
        for file in files:
            member = 'source/' + str(file.relative_to(source))
            require(sha(capsule.extractfile(member).read()) == sha(file.read_bytes()),
                    'Source differs: ' + member)
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    timing_event = 'hc_library_norm_microbench' if library else 'hc_sequence_microbench'
    timings = [x for x in events if x['event'] == timing_event]
    replays = [x for x in events if x['event'] == 'hc_sequence_replay']
    norms = [x for x in events if x['event'] == 'hc_sequence_norm_oracle']
    require((len(timings), len(replays), len(norms)) ==
            ((20, 20, 10) if library else (20, 16, 6)), 'Incomplete experiment')
    cases = [(96, 0), (97, 1), (129, 2)] + ([(2048, 0), (2048, 1)] if library else [])
    wanted = {f'{prefix}-n{n}-p{p}-moe{m}' for n, p in cases for m in (0, 1)}
    wanted |= {f'{prefix}-bench-moe{m}-rep{r}' for m in (0, 1) for r in range(5)}
    require({x['label'] for x in replays} == wanted, 'Missing replay case')
    for replay in replays:
        for field in ('res', 'norm', 'half', 'down'):
            require(replay[field + '_exact'] and
                    replay['reference_' + field + '_sha256'] == replay['paired_' + field + '_sha256'],
                    'Complete output mismatch: ' + replay['label'])
        require(replay['scalar_half_exact'], 'Scalar rounding differs')
    pairs = []
    for name, meta in result['artifacts'].items():
        if '-reference-' in name:
            other = name.replace('-reference-', '-paired-')
            require(other in result['artifacts'] and result['artifacts'][other] == meta,
                    'Saved pair differs: ' + name)
            pairs.append([name, other])
    require(len(pairs) == 18, 'Missing saved pairs')
    failures = [x for x in replays + norms if not x['pass']]
    require(result['commands'][-1]['exit_code'] == int(bool(failures)), 'Numerical exit differs')
    require(transport['exit_code'] == int(bool(failures)), 'Transport exit differs')
    summaries = []
    for moe in (False, True):
        medians = []
        for paired in (False, True):
            rows = [x for x in timings if x['moe'] == moe and x['paired'] == paired]
            require({x['rep'] for x in rows} == set(range(5)), 'Missing timing repetition')
            require(all(x['tokens'] == 2048 and x['iterations'] == 16 and
                        x['weight_bytes'] == 104857600 for x in rows), 'Timing scope differs')
            if library:
                require(all(x['consumer'] == 'hipblaslt-7526' for x in rows), 'Wrong consumer')
            values = [x['microseconds_per_iteration'] for x in rows]
            require(all(x > 0 for x in values), 'Invalid duration')
            medians.append(statistics.median(values))
            summaries.append({'moe': moe, 'paired': paired, 'samples_us': values,
                              'median_us': medians[-1], 'min_us': min(values), 'max_us': max(values)})
        summaries[-1]['time_change_percent'] = 100 * (medians[1] / medians[0] - 1)
    telemetry = [json.loads(line) for line in (path / 'results/telemetry.jsonl').read_text().splitlines()]
    temperatures = {}
    for event in telemetry:
        for sensor in event['thermal']:
            require(not sensor['over_limit'], 'Thermal stop occurred')
            temperatures[sensor['device']] = max(temperatures.get(sensor['device'], -273),
                                                 sensor['temperature_mc'] / 1000)
    return {'label': label, 'source_variant': transport['source_variant'],
            'binary_sha256': result['binary_sha256'], 'source_capsule_sha256': transport['capsule_sha256'],
            'fixture_hashes': frozen, 'source_files_verified': len(files),
            'artifact_count': len(result['artifacts']), 'saved_pairs': pairs,
            'complete_hash_pairs_verified': len(replays) * 4,
            'temperature_max_c': temperatures,
            'command_exits': [x['exit_code'] for x in result['commands']],
            'summaries': summaries, 'timings': timings, 'replays': replays,
            'norm_oracles': norms, 'numerical_failures': failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('labels', nargs='+')
    parser.add_argument('--library', action='store_true', help='Validate the distinct HC library cycle protocol')
    args = parser.parse_args()
    arms = [arm(label, library=args.library) for label in args.labels]
    baseline = {x['label']: x for x in arms[0]['replays']}
    for other in arms[1:]:
        for replay in other['replays']:
            for field in ('res', 'norm', 'half', 'down'):
                require(replay['reference_' + field + '_sha256'] ==
                        baseline[replay['label']]['reference_' + field + '_sha256'],
                        'Geometry changed complete output: ' + replay['label'])
    report = {'scope': ('Synthetic HC library producer/consumer cycle' if args.library else
                        'Synthetic HC sequence') + '; no model throughput or reactive gain',
              'validation_pass': True, 'numerical_qualification_pass': all(not x['numerical_failures'] for x in arms),
              'arms': arms, 'promoted': False}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('validation_pass', 'numerical_qualification_pass', 'promoted')}))
    for item in arms:
        print(json.dumps({'label': item['label'], 'summaries': item['summaries']}))


if __name__ == '__main__':
    main()
