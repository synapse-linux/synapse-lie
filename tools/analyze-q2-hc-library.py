#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and summarize the bounded HC F16 library algorithm screen."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = json.loads((args.run / 'results/result.json').read_text())
    transport = json.loads((args.run / 'transport.json').read_text())
    require(result['mode'] == 'hc-library-bench' and result.get('finished_at'),
            'Expected completed library screen')
    require(not result.get('thermal_stop') and not result['model_access'],
            'Expected uninterrupted synthetic scope')
    require(result['binary_sha256'] == result['binary_sha256_after'], 'Binary changed')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4,
            'Missing matched four-lease receipt')
    require(not result['preflight_kfd'] and not result['postflight_kfd'],
            'Unresolved KFD client')
    for name, meta in result['artifacts'].items():
        payload = (args.run / 'results' / name).read_bytes()
        require(len(payload) == meta['bytes'] and hashlib.sha256(payload).hexdigest() == meta['sha256'],
                'Artifact identity changed: ' + name)
    events = []
    for path in sorted((args.run / 'results').glob('*.log')):
        for line in path.read_text().splitlines():
            if line.startswith('{"event":'):
                events.append(json.loads(line))
    native_cases = [row for row in events if row['event'] == 'pp_operator']
    require(len(native_cases) == 22, 'Missing original independent cases')
    summary = [row for row in events if row['event'] == 'pp_operator_summary']
    require(len(summary) == 1 and summary[0]['numerical_failures'] == 4,
            'Original numerical-control failures changed')
    report = dict(scope='Synthetic HC library screen, original F16 layout; not model throughput or independent full-model quality',
                  run=str(args.run), promotion=False, binary_sha256=result['binary_sha256'],
                  finished_at=result['finished_at'], original_operator_cases=native_cases,
                  original_numerical_failures=4, shapes={})
    for m, k in ((320, 10240), (10240, 320)):
        summaries = [row for row in events if row['event'] == 'library_summary' and row['m'] == m]
        require(len(summaries) == 1, 'Incomplete shape sweep')
        shape_summary = summaries[0]
        arms = [row for row in events if row['event'] == 'library_operator' and row['m'] == m]
        require([row['arm'] for row in arms] == list(range(shape_summary['algorithms'] + 2)),
                'Missing or duplicate algorithm arm')
        require(arms[0]['algorithm'] == arms[-1]['algorithm'] == -1,
                'Native before/after controls missing')
        require(arms[0]['full_output_sha256'] == arms[-1]['full_output_sha256'],
                'Native control does not repeat exactly')
        case = next(row for row in native_cases if row['label'] == f'{m}x{k}-n2048-p0')
        require(case['full_output_sha256'] == arms[0]['full_output_sha256'],
                'Native sweep differs from the existing operator')
        failures = 0
        for arm in arms:
            timings = [row for row in events if row['event'] == 'library_timing'
                       and row['m'] == m and row['arm'] == arm['arm']]
            require([row['rep'] for row in timings] == list(range(5)), 'Missing timing samples')
            require(all(row['algorithm'] == arm['algorithm'] and row['k'] == k
                        and row['n'] == 2048 and row['weight_bytes'] == 100 << 20
                        and row['launches'] == 16 for row in timings), 'Timing scope changed')
            samples = [row['us_per_launch'] for row in timings]
            require(all(math.isfinite(v) and v > 0 for v in samples), 'Invalid timing')
            require(0 <= arm['workspace_bytes'] <= 64 << 20, 'Workspace cap exceeded')
            require(arm['numeric_ok'] == (arm['relative_rms'] <= 2e-5 and arm['error_over_peak'] <= 2e-5),
                    'Independent numerical threshold changed')
            row_checks = [row for row in events if row['event'] == 'library_row_invariance'
                          and row['m'] == m and row['arm'] == arm['arm']]
            require(len(row_checks) == 1, 'Missing position-invariance check')
            arm['row_invariance'] = row_checks[0]
            arm['checks_pass'] = arm['numeric_ok'] and row_checks[0]['inconsistent_values'] == 0
            failures += int(not arm['numeric_ok']) + int(row_checks[0]['inconsistent_values'] != 0)
            arm['timing_us'] = dict(samples=samples, min=min(samples),
                                    median=statistics.median(samples), max=max(samples))
        require(failures == shape_summary['failures'], 'Failure summary mismatch')
        candidates = [arm for arm in arms if arm['algorithm'] >= 0]
        eligible = [arm for arm in candidates if arm['checks_pass']]
        fastest = min(candidates, key=lambda arm: arm['timing_us']['median'])
        best = min(eligible, key=lambda arm: arm['timing_us']['median']) if eligible else None
        records = [row for row in events if row['event'] == 'library_choice' and row['m'] == m]
        zero_first = next(row['algorithm'] for row in records if row['cap_bytes'] == 0 and row['usable'])
        report['shapes'][str(m)] = dict(m=m, k=k, n=2048, arms=arms, choices=records,
            algorithms=len(candidates), failures=failures, zero_workspace_first=zero_first,
            fastest_algorithm=fastest['algorithm'], fastest_checked_algorithm=best['algorithm'] if best else None,
            fastest_time_ratio_before=fastest['timing_us']['median'] / arms[0]['timing_us']['median'],
            fastest_time_ratio_after=fastest['timing_us']['median'] / arms[-1]['timing_us']['median'],
            fastest_checked_time_ratio_before=best['timing_us']['median'] / arms[0]['timing_us']['median'] if best else None,
            fastest_checked_time_ratio_after=best['timing_us']['median'] / arms[-1]['timing_us']['median'] if best else None)
    expected_exit = int(report['original_numerical_failures'] +
                        sum(s['failures'] for s in report['shapes'].values()) > 0)
    require([row['exit_code'] for row in result['commands']] == [0, 0, 0, expected_exit],
            'Unexpected command failure')
    require(transport['exit_code'] == expected_exit, 'Transport did not preserve exit')
    report['actual_exit'] = expected_exit
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({m: {key: value for key, value in shape.items() if key not in ('arms', 'choices')}
                      for m, shape in report['shapes'].items()}, indent=2))


if __name__ == '__main__':
    main()
