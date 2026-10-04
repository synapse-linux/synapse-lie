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


def arm(label, *, library=False, ragged=False):
    path = ROOT / 'evidence' / label
    result = json.loads((path / 'results/result.json').read_text())
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    mode = 'hc-norm-ragged-bench' if ragged else 'hc-library-norm-bench' if library else 'hc-sequence-bench'
    prefix = 'hc-library-norm' if library else 'hc-sequence'
    require(result['mode'] == mode and not result['model_access'],
            'Unexpected runtime scope')
    if library:
        require(transport['source_variant'] == ('hc-norm-ragged' if ragged else 'library-norm-cycle'), 'Wrong library source')
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
        if ragged:
            plan = json.loads((ROOT/'config/q2-norm-ragged-plan.json').read_text())
            manifest = ROOT/'config/q2-norm-ragged-source.json'
            require(sha(manifest.read_bytes()) == plan['source_manifest_sha256'], 'Planned source changed')
            require(label == plan['label'], 'Unexpected component label')
            require({str(p.relative_to(source)): sha(p.read_bytes()) for p in files}
                    == json.loads(manifest.read_text())['files'], 'Provider manifest differs')
            with tarfile.open(ROOT/'evidence'/plan['host']/'source.tar.gz') as host:
                for name, expected in plan['fixtures'].items():
                    require(sha(capsule.extractfile(name).read()) == expected
                            and sha(host.extractfile(name).read()) == expected,
                            'Host-qualified fixture differs: '+name)
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    timing_event = 'hc_library_norm_microbench' if library else 'hc_sequence_microbench'
    timings = [x for x in events if x['event'] == timing_event]
    replays = [x for x in events if x['event'] == 'hc_sequence_replay']
    norms = [x for x in events if x['event'] == 'hc_sequence_norm_oracle']
    require((len(timings), len(replays), len(norms)) ==
            ((40, 34, 14) if ragged else (20, 20, 10) if library else (20, 16, 6)), 'Incomplete experiment')
    cases = [(96, 0), (97, 1), (129, 2)] + ([(2048, 0), (2048, 1)] if library else [])
    if ragged:
        cases += [(2040, 0), (2047, 1)]
    wanted = {f'{prefix}-n{n}-p{p}-moe{m}' for n, p in cases for m in (0, 1)}
    if ragged or any(x['label'].startswith(prefix+'-bench-n') for x in replays):
        wanted |= {f'{prefix}-bench-n{n}-moe{m}-rep{r}'
                   for n in ((2040, 2048) if ragged else (2048,))
                   for m in (0, 1) for r in range(5)}
    else:
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
    require(len(pairs) == (30 if ragged else 18), 'Missing saved pairs')
    failures = [x for x in replays + norms if not x['pass']]
    require(result['commands'][-1]['exit_code'] == int(bool(failures)), 'Numerical exit differs')
    require(transport['exit_code'] == int(bool(failures)), 'Transport exit differs')
    summaries = []
    for tokens, moe in ((n, m) for n in ((2040, 2048) if ragged else (2048,))
                        for m in (False, True)):
        medians = []
        for paired in (False, True):
            rows = [x for x in timings if x['moe'] == moe and x['paired'] == paired and x['tokens'] == tokens]
            require({x['rep'] for x in rows} == set(range(5)), 'Missing timing repetition')
            require(len(rows) == 5 and all(x['iterations'] == 16 and
                        x['weight_bytes'] == 104857600 for x in rows), 'Timing scope differs')
            if library:
                require(all(x['consumer'] == 'hipblaslt-7526' for x in rows), 'Wrong consumer')
            values = [x['microseconds_per_iteration'] for x in rows]
            require(all(x > 0 for x in values), 'Invalid duration')
            medians.append(statistics.median(values))
            summaries.append({'tokens': tokens, 'moe': moe, 'paired': paired, 'samples_us': values,
                              'median_us': medians[-1], 'min_us': min(values), 'max_us': max(values)})
        summaries[-1]['time_change_percent'] = 100 * (medians[1] / medians[0] - 1)
        summaries[-1]['faster_paired_repetitions'] = sum(
            b < a for a, b in zip(summaries[-2]['samples_us'], summaries[-1]['samples_us']))
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
    parser.add_argument('--ragged', action='store_true', help='Validate the frozen two-shape paired norm component')
    args = parser.parse_args()
    if args.ragged:
        args.library = True
    require(not args.output.exists(), 'Refusing to overwrite retained evidence')
    arms = [arm(label, library=args.library, ragged=args.ragged) for label in args.labels]
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
    if args.ragged:
        report['plan_sha256'] = sha((ROOT/'config/q2-norm-ragged-plan.json').read_bytes())
        useful = all(s['time_change_percent'] < -1 and s['faster_paired_repetitions'] >= 4
                     for a in arms for s in a['summaries'] if s['paired'] and s['tokens'] == 2040)
        norms_pass = all(n['pass'] for a in arms for n in a['norm_oracles'])
        report['disposition'] = ('SELECT_ONE_CANONICAL_POINT_WITH_QUALITY_OPEN' if useful and norms_pass
                                 else 'NO_MODEL_RUN_FROM_THIS_COMPONENT')
        report['model_inference'] = report['goal_met'] = False
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('validation_pass', 'numerical_qualification_pass', 'promoted')}))
    for item in arms:
        print(json.dumps({'label': item['label'], 'summaries': item['summaries']}))


if __name__ == '__main__':
    main()
