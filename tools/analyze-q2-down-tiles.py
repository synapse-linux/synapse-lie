#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and summarize saved Q2 down tile comparisons; no GPU execution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    return dict(samples=values, min=min(values), median=statistics.median(values), max=max(values))


def analyze(path):
    root = path / 'results'
    result = json.loads((root / 'result.json').read_text())
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    if result['mode'] not in ('packed-tiles-bench', 'packed-tiles16-bench'):
        raise ValueError('Unexpected component mode')
    if (result.get('model_access') or result.get('thermal_stop') or
            result['binary_sha256'] != result['binary_sha256_after']):
        raise ValueError('Model access, thermal stop or changed binary')
    if digest(path / 'source.tar.gz') != transport['capsule_sha256'] or \
            digest(path / 'results.tar.gz') != collection['sha256']:
        raise ValueError('Changed capsule or collection')
    for name, meta in result['artifacts'].items():
        artifact = root / name
        if artifact.stat().st_size != meta['bytes'] or digest(artifact) != meta['sha256']:
            raise ValueError('Changed artifact: ' + name)
    events = [json.loads(line) for line in (root / '03.log').read_text().splitlines()
              if line.startswith('{')]
    geometry = [row for row in events if row['event'] == 'tile_geometry']
    if [row['active_experts'] for row in geometry] != [512, 128, 64] or len(events) != 36:
        raise ValueError('Incomplete routing cases or samples')
    candidate = 16 if result['mode'] == 'packed-tiles16-bench' else 64
    cases = []
    for shape in geometry:
        active = shape['active_experts']
        expected = dict(tokens=2048, experts=512, used=10, rows=2560,
                        logical_k=640, stored_k=768, tile=48, candidate_tile=candidate,
                        weight_bytes=330301440, active_weight_bytes=active * 2560 * 252)
        if any(shape[key] != value for key, value in expected.items()):
            raise ValueError('Changed benchmark shape')
        if shape['active_weight_bytes'] <= 32 * 1024 * 1024:
            raise ValueError('Active weights fit the device cache')
        padded_rows = ((20480 // active) + 15) // 16 * 16
        ref_tiles = active * ((padded_rows + 47) // 48)
        candidate_tiles = active * ((padded_rows + candidate - 1) // candidate)
        if shape['tiles'] != ref_tiles or shape['candidate_tiles'] != candidate_tiles:
            raise ValueError('Unexpected tile-map size')
        samples = {}
        for tile in (48, candidate):
            rows = [row for row in events if row['event'] == 'tile_microbench'
                    and row['active_experts'] == active and row['tile'] == tile]
            if [row['rep'] for row in rows] != list(range(5)) or any(
                    row['launches'] != 8 or row['position'] != ((row['rep'] & 1) ^ int(tile == candidate))
                    or not math.isfinite(row['us_per_launch']) or row['us_per_launch'] <= 0 for row in rows):
                raise ValueError('Incomplete timing or changed alternating order')
            samples[str(tile)] = stats([row['us_per_launch'] for row in rows])
        replays = [row for row in events if row['event'] == 'tile_replay' and row['active_experts'] == active]
        if len(replays) != 1:
            raise ValueError('Missing complete replay')
        replay = replays[0]
        if replay['values'] != 52428800 or replay['independent_samples'] != 1024:
            raise ValueError('Changed replay scope')
        sample_files = list(root.glob('packed-tiles*samples-' + str(active) + '.jsonl'))
        if len(sample_files) != 1:
            raise ValueError('Missing independent oracle samples')
        oracle = [json.loads(line) for line in sample_files[0].read_text().splitlines()]
        if len(oracle) != 1024 or any(row['slot'] != (i * 7919 + 17) % 20480
                                   or row['row'] != (i * 101 + 127) % 2560
                                   or not all(math.isfinite(row[key]) for key in ('value', 'reference'))
                                   for i, row in enumerate(oracle)):
            raise ValueError('Changed oracle coordinates or invalid values')
        error2 = sum((row['value'] - row['reference']) ** 2 for row in oracle)
        norm2 = sum(row['reference'] ** 2 for row in oracle)
        maximum = max(abs(row['value'] - row['reference']) for row in oracle)
        peak = max(abs(row['reference']) for row in oracle)
        for key, value in (('relative_rms', math.sqrt(error2 / max(norm2, 1e-30))),
                           ('error_over_peak', maximum / max(peak, 1e-20))):
            if not math.isclose(value, replay[key], rel_tol=1e-8, abs_tol=1e-12):
                raise ValueError('Oracle summary disagrees with saved samples')
        exact = replay['exact'] and replay['reference_sha256'] == replay['candidate_sha256']
        passed = exact and replay['relative_rms'] <= .002 and replay['error_over_peak'] <= .002
        cases.append(dict(active_experts=active, geometry=shape, microseconds=samples,
                          time_ratio=samples[str(candidate)]['median'] / samples['48']['median'],
                          complete_replay=replay, numerical_pass=passed,
                          oracle_file=str(sample_files[0]), oracle_sha256=digest(sample_files[0])))
    passed = all(row['numerical_pass'] for row in cases)
    expected_exits = [0, 0, int(not passed)]
    state = 'SYNTHETIC_Q2_TILE_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT' if passed else 'FAILED'
    if ([row['exit_code'] for row in result['commands']] != expected_exits
            or transport['exit_code'] != expected_exits[-1] or result['state'] != state):
        raise ValueError('Unexpected runtime exit or state')
    return dict(path=str(path), mode=result['mode'], candidate_tile=candidate,
                source_variant=transport['source_variant'], binary_sha256=result['binary_sha256'],
                started_at=result['started_at'], finished_at=result['finished_at'],
                command_exits=expected_exits, numerical_pass=passed, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    runs = [analyze(path) for path in args.runs]
    identities = {(row['geometry']['weight_sha256'], row['geometry']['input_sha256'])
                  for run in runs for row in run['cases']}
    if len(identities) != 1:
        raise ValueError('Different synthetic weights or activations')
    report = dict(scope='Alternating synthetic Q2 tile timings on .157; no complete-model throughput claim',
                  goal_met=False, qualified_runtime_promoted=False, runs=runs)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([dict(candidate=run['candidate_tile'], numerical_pass=run['numerical_pass'],
                           time_ratios={row['active_experts']: row['time_ratio'] for row in run['cases']})
                      for run in runs]))
    if not all(run['numerical_pass'] for run in runs):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
