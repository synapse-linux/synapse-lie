#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit all HC cycle outputs and timers after collection and window release."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
require, sha, read = curve.require, curve.sha, curve.read


def coverage():
    cases = {}
    for n in (96, 97, 127, 128, 129, 257):
        for mode in range(3):
            for pattern in range(2):
                cases[f'n{n}-m{mode}-p{pattern}-half'] = (n, mode, True, 1)
    for mode in range(3):
        cases[f'n129-m{mode}-p0-nohalf'] = (129, mode, False, 1)
        cases[f'n2048-m{mode}-p0-half'] = (2048, mode, True, 6)
    outputs, scratch, q8 = {}, {}, set()
    for name, (n, mode, half, rotations) in cases.items():
        fields = {'mixed': (n * 2560 * 4, True),
                  'half': (n * 2560 * 2, half),
                  'inject': (n * 4 * 3 * 4, True)}
        if mode == 1:
            fields['q8'] = (((n + 127) // 128 * 128 // 16) * 80 * 576, False)
        for rotation in range(rotations):
            for field, contract in fields.items():
                outputs[name, field, rotation] = contract
            scratch[name, rotation] = n * 2560 * 4
            if mode == 1:
                q8.add((name, rotation))
        if rotations == 6:
            for field, contract in fields.items():
                outputs[name, 'post-' + field, 5] = contract
    return cases, outputs, scratch, q8


def timing_groups(timings):
    require(len(timings) == 42, 'Missing HC cycle timings')
    require([(r['case'], r['rep'], r['order']) for r in timings] ==
            [(f'n2048-m{mode}-p0-half', rep, order)
             for mode in range(3) for rep in range(7) for order in range(2)],
            'Timing execution order changed')
    groups = []
    all_keys = set()
    for mode in range(3):
        name = f'n2048-m{mode}-p0-half'
        pair = {}
        for candidate in (False, True):
            rows = [r for r in timings if r['case'] == name and r['candidate'] == candidate]
            require([r['rep'] for r in rows] == list(range(7)), 'Timing repetitions changed')
            require([r['warmup'] for r in rows] == [True, True] + [False] * 5,
                    'Warm timing selected as measurement')
            for row in rows:
                require(all(type(row[k]) is bool for k in
                            ('candidate', 'warmup', 'hip_timer_valid')),
                        'Timing boolean fields changed')
                key = (row['case'], row['rep'], row['order'])
                require(key not in all_keys, 'Duplicate timing record')
                all_keys.add(key)
                require(row['order'] in (0, 1) and
                        row['candidate'] == ((row['rep'] + row['order']) % 2 != 0) and
                        row['iterations'] == 6 and row['rotating_weight_bytes'] == 39321600,
                        'Timing order, cycles or cache rotation changed')
                wall = row['wall_us_per_cycle']
                require(type(wall) in (int, float) and math.isfinite(wall) and wall > 0,
                        'Invalid complete-cycle monotonic wall duration')
                bits = row['hip_ms_raw_bits']
                require(type(bits) is int and 0 <= bits <= 0xffffffff,
                        'Invalid raw HIP float identity')
                raw = struct.unpack('<f', struct.pack('<I', bits))[0]
                finite = math.isfinite(raw)
                if finite:
                    value = row['hip_ms_raw']
                    require(type(value) in (int, float) and math.isfinite(value),
                            'Finite HIP duration lost')
                    # cout precision12 preserves a binary32 value but its
                    # parsed binary64 decimal need not equal the exact float.
                    # Recover binary32; the separate raw bits preserve signed
                    # zero even when JSON parses the literal -0 as integer0.
                    recovered = struct.unpack('<f', struct.pack('<f', value))[0]
                    require(recovered == raw, 'Raw HIP duration lost or changed')
                else:
                    require(row['hip_ms_raw'] is None, 'Nonfinite HIP duration is not JSON null')
                require(row['hip_timer_valid'] == (finite and raw > 0),
                        'Invalid HIP duration treated as valid timing')
            measured = [r for r in rows if not r['warmup']]
            values = [r['wall_us_per_cycle'] for r in measured]
            hip_valid = all(r['hip_timer_valid'] for r in measured)
            pair['candidate' if candidate else 'reference'] = dict(
                wall_samples_us=values, wall_min_us=min(values),
                wall_median_us=statistics.median(values), wall_max_us=max(values),
                HIP_measured_valid=hip_valid,
                HIP_raw_ms=[r['hip_ms_raw'] for r in measured],
                HIP_raw_bits=[r['hip_ms_raw_bits'] for r in measured],
                HIP_us_per_cycle=([r['hip_ms_raw'] * 1000 / 6 for r in measured]
                                  if hip_valid else None))
        groups.append(dict(case=name, mode=mode, **pair,
            wall_cycle_time_change_percent=100 *
                (pair['candidate']['wall_median_us'] / pair['reference']['wall_median_us'] - 1),
            wall_scope_includes_host_submission_and_terminal_sync=True,
            pure_GPU_timing_claim=False))
    require(len(all_keys) == 42, 'Incomplete timing shape coverage')
    return groups


def analyze(plan_path):
    plan = read(plan_path)
    require(plan['schema'] == 'synapse-lie.q2-hc-inject-reuse-plan.v1' and
            len(plan['components']) == 1 and plan['arms'] == [], 'Expected component-only HC plan')
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        require(sha(ROOT / name) == digest, 'Frozen identity changed: ' + name)
    release_path = ROOT / plan['release_path']
    release = read(release_path)
    admission = read(ROOT / plan['admission_path'])
    require(release['state'] == 'Q2_HC_INJECT_REUSE_WINDOW_RELEASED' and
            not release['gpu_reserved'] and release['owner'] == 'synapse-lie-q2' and
            release['plan_sha256'] == sha(plan_path) and
            release['previous_release_sha256'] == plan['previous_release_sha256'] and
            release['admission_sha256'] == sha(ROOT / plan['admission_path']) and
            release['at'] > admission['at'] and release['model_stats_unchanged'] and
            not release['kfd'] and not release['owned_group_members'],
            'Expected collected and released HC window')
    arm = plan['components'][0]
    require(arm['mode'] == 'hc-inject-reuse-check' and
            arm['variant'] == 'hc-inject-reuse-draft', 'Wrong HC draft provider')
    path = ROOT / 'evidence' / arm['label']
    result, transport = curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and
            transport['exit_code'] == exits[-1] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete, unsafe or changed component')
    require(result['locks'] == result['postflight_locks'] and
            [(r['device'], r['inode']) for r in result['locks']] ==
                [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)] and
            not result['preflight_kfd'] and not result['postflight_kfd'],
            'Original ownership observations changed')
    require(any(c['label'] == arm['label'] and c['finished_at'] == result['finished_at']
                and c['command_exits'] == exits for c in release['cohorts']),
            'Component not retired in release')
    source = read(ROOT / plan['source_variant_manifest'])['variants'][arm['variant']]
    with tarfile.open(path / 'source.tar.gz') as archive:
        for name, digest in plan['fixtures'].items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Capsule fixture changed: ' + name)
        inventory = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                     for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(inventory == source['files'], 'Retained parent inventory differs')
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    require(all(r['event'] in ('hc_reuse_replay', 'hc_reuse_q8_live', 'hc_reuse_scratch',
                              'hc_reuse_timing', 'hc_reuse_complete') for r in events),
            'Unexpected HC event')
    replay = [r for r in events if r['event'] == 'hc_reuse_replay']
    scratch = [r for r in events if r['event'] == 'hc_reuse_scratch']
    q8 = [r for r in events if r['event'] == 'hc_reuse_q8_live']
    timings = [r for r in events if r['event'] == 'hc_reuse_timing']
    complete = [r for r in events if r['event'] == 'hc_reuse_complete']
    cases, expected_outputs, expected_scratch, expected_q8 = coverage()
    require(len(cases) == 42 and len(replay) == len(expected_outputs) == 200 and
            len(scratch) == len(expected_scratch) == 57 and len(q8) == len(expected_q8) == 19,
            'Incomplete HC output/scratch/Q8 coverage')
    require({(r['case'], r['field'], r['rotation']) for r in replay} == set(expected_outputs) and
            {(r['case'], r['rotation']) for r in scratch} == set(expected_scratch) and
            {(r['case'], r['rotation']) for r in q8} == expected_q8, 'HC case coverage changed')
    for row in replay:
        size, finite_written = expected_outputs[row['case'], row['field'], row['rotation']]
        require(row['bytes'] == size and row['guards_exact'] and
                row['finite_written_checked'] == finite_written and row['nonfinite_values'] >= 0 and
                row['exact'] == (row['reference_sha256'] == row['candidate_sha256'] and
                                 row['nonfinite_values'] == 0), 'HC output verdict or extent changed')
        if not row['exact']:
            for suffix in ('reference', 'candidate'):
                saved = path / 'results' / (row['case'] + '-' + row['field'] + '-' +
                    str(row['rotation']) + '-' + suffix + '.bin')
                require(saved.stat().st_size == size + 128 and
                        sha(saved) == row[suffix + '_sha256'], 'Full numerical failure array lost')
    require(all(r['bytes'] == expected_scratch[r['case'], r['rotation']] and
                r['guarded_written'] and r['nonfinite_values'] >= 0 for r in scratch),
            'Unsafe or incomplete scratch')
    logged_numerical = (all(r['exact'] for r in replay) and
                        all(r['nonfinite_values'] == 0 for r in scratch) and
                        all(r['finite_scales_padding_exact'] for r in q8))
    require(len(complete) == 1 and complete[0]['timing_retained'] and
            not complete[0]['model_inference'] and type(complete[0]['numerical_pass']) is bool,
            'Missing completion or timing retention')
    numerical = complete[0]['numerical_pass']
    # v2 also checks post-timing scratch and both Q8 scale arrays without a
    # separate event. Their safe nonfinite rejection must retain timings even
    # if all separately logged arrays agree. Never promote a rejected finish.
    require((not numerical or logged_numerical) and exits[-1] == (0 if numerical else 1),
            'Numerical failure/exit or timing retention lost')
    groups = timing_groups(timings)
    return dict(schema='synapse-lie.q2-hc-inject-reuse-component-results.v1',
        plan_sha256=sha(plan_path), release_sha256=sha(release_path),
        source_variant=arm['variant'], label=arm['label'], command_exits=exits,
        device_work_safe=True, numerical_exact=numerical,
        separately_logged_numerical_pass=logged_numerical,
        additional_unlogged_post_timing_finite_rejection=logged_numerical and not numerical,
        case_count=42, output_records=replay, scratch=scratch, q8_live=q8,
        timings=timings, summaries=groups, monotonic_cycle_wall_valid=True,
        HIP_timing_valid=all(r['hip_timer_valid'] for r in timings),
        invalid_HIP_samples=sum(not r['hip_timer_valid'] for r in timings),
        capsule_sha256=sha(path / 'source.tar.gz'), archive_sha256=sha(path / 'results.tar.gz'),
        artifact_count=len(result['artifacts']), source_files_verified=len(inventory),
        fixture_files_verified=len(plan['fixtures']), binary_sha256=result['binary_sha256'],
        original_inputs_immutable_at_fixture_completion=True,
        model_inference=False, borrowed_executor_scratch_qualified=False,
        independent_quality=False, pure_GPU_wall_time_claim=False,
        new_model_rate=None, full_model_speedup=False, controls_rerun=False, goal_met=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.plan)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in
        ('command_exits', 'numerical_exact', 'invalid_HIP_samples', 'summaries')}))


if __name__ == '__main__':
    main()
