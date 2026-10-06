#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit complete RMS owner outputs and timings only after collection/release."""
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
    cases = [(n, mode != 0, p, 10, 3, 4 if mode == 2 else 0, True, True, False)
             for n in (1, 17, 97, 129, 257) for mode in range(3) for p in range(2)]
    cases += [(129, False, 0, 10, 3, 0, False, False, False),
              (129, True, 0, 10, 3, 0, False, False, False),
              (129, True, 0, 10, 3, 0, True, False, False),
              (129, True, 0, 1, 3, 0, True, True, False),
              (129, True, 0, 16, 3, 0, True, True, False),
              (129, False, 0, 10, 10, 0, True, True, False),
              (2048, False, 0, 10, 3, 0, True, True, True),
              (2048, True, 0, 10, 3, 0, True, True, True)]
    outputs, inputs, timed = {}, [], []
    for n, moe, p, used, parts, offset, gamma, half, timing in cases:
        name = (f'n{n}-moe{int(moe)}-p{p}-used{used}-parts{parts}-offset{offset}'
                f'-gamma{int(gamma)}-half{int(half)}')
        inputs.append(name)
        fields = {'residual': (n * 4 * 2560 * 4, 4, True),
                  'scales' if moe else 'norm': (n * 4 * (1 if moe else 2560) * 4, 4, gamma),
                  'half': (n * 4 * 2560 * 2, 2, gamma and half)}
        for field, contract in fields.items():
            outputs[name, field] = contract
        if timing:
            timed.append(name)
            for field, contract in fields.items():
                outputs[name + '-post', field] = contract
    require(len(inputs) == len(set(inputs)) == 38 and len(outputs) == 120,
            'RMS coverage changed')
    return outputs, inputs, timed


def timing_groups(rows):
    _, _, timed = coverage()
    require(len(rows) == 28 and [(r['case'], r['rep'], r['order']) for r in rows] ==
            [(name, rep, order) for name in timed for rep in range(7) for order in range(2)],
            'Missing, duplicate or reordered RMS timing')
    groups = []
    for name in timed:
        pair = {}
        for candidate in (False, True):
            samples = [r for r in rows if r['case'] == name and r['candidate'] == candidate]
            require([r['rep'] for r in samples] == list(range(7)), 'RMS arm history changed')
            for r in samples:
                require(all(type(r[k]) is bool for k in ('candidate', 'warmup', 'hip_timer_valid')) and
                        r['warmup'] == (r['rep'] < 2) and
                        r['candidate'] == ((r['rep'] + r['order']) % 2 != 0) and
                        r['iterations'] == 6 and r['residual_payload_bytes'] == 83886080,
                        'RMS arm, warmup or complete cycle changed')
                wall, bits = r['wall_us_per_cycle'], r['hip_ms_raw_bits']
                require(type(wall) in (int, float) and math.isfinite(wall) and wall > 0,
                        'Invalid complete-cycle RMS wall duration')
                require(type(bits) is int and 0 <= bits <= 0xffffffff, 'Invalid raw HIP identity')
                raw = struct.unpack('<f', struct.pack('<I', bits))[0]
                if math.isfinite(raw):
                    require(type(r['hip_ms_raw']) in (int, float) and
                            math.isfinite(r['hip_ms_raw']) and
                            struct.unpack('<f', struct.pack('<f', r['hip_ms_raw']))[0] == raw,
                            'Raw HIP value differs from bits')
                else:
                    require(r['hip_ms_raw'] is None, 'Nonfinite HIP value must be null')
                require(r['hip_timer_valid'] == (math.isfinite(raw) and raw > 0),
                        'Invalid HIP value treated as valid')
            measured = [r for r in samples if not r['warmup']]
            values = [r['wall_us_per_cycle'] for r in measured]
            pair['candidate' if candidate else 'reference'] = dict(
                wall_samples_us=values, wall_min_us=min(values),
                wall_median_us=statistics.median(values), wall_max_us=max(values),
                HIP_measured_valid=all(r['hip_timer_valid'] for r in measured),
                HIP_raw_ms=[r['hip_ms_raw'] for r in measured],
                HIP_raw_bits=[r['hip_ms_raw_bits'] for r in measured])
        groups.append(dict(case=name, **pair, wall_cycle_time_change_percent=100 *
            (pair['candidate']['wall_median_us'] / pair['reference']['wall_median_us'] - 1),
            wall_scope_includes_host_submission_and_terminal_sync=True,
            pure_GPU_timing_claim=False))
    return groups


def analyze(plan_path):
    plan = read(plan_path)
    require(plan['schema'] == 'synapse-lie.q2-hc-norm-owner-plan.v1' and
            plan['arms'] == [] and len(plan['components']) == 1, 'Expected component-only RMS plan')
    release_path = ROOT / plan['release_path']
    release, admission = read(release_path), read(ROOT / plan['admission_path'])
    require(release['state'] == 'Q2_HC_NORM_OWNER_WINDOW_RELEASED' and
            not release['gpu_reserved'] and release['owner'] == 'synapse-lie-q2' and
            release['plan_sha256'] == sha(plan_path) and
            release['previous_release_sha256'] == plan['previous_release_sha256'] and
            release['admission_sha256'] == sha(ROOT / plan['admission_path']) and
            release['at'] > admission['at'] and release['model_stats_unchanged'] and
            not release['kfd'] and not release['owned_group_members'], 'RMS window not released')
    arm = plan['components'][0]
    require(arm['mode'] == 'hc-norm-owner-check' and arm['variant'] == 'hc-norm-owner-draft',
            'Unexpected RMS component')
    path = ROOT / 'evidence' / arm['label']
    result, transport = curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and
            transport['exit_code'] == exits[-1] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete or unsafe RMS component')
    require(result['locks'] == result['postflight_locks'] and
            [(r['device'], r['inode']) for r in result['locks']] ==
            [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)] and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'RMS ownership changed')
    require(any(c['label'] == arm['label'] and c['finished_at'] == result['finished_at'] and
                c['command_exits'] == exits for c in release['cohorts']), 'RMS cohort not retired')
    source = read(ROOT / plan['source_variant_manifest'])['variants'][arm['variant']]
    with tarfile.open(path / 'source.tar.gz') as archive:
        for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Frozen RMS capsule differs: ' + name)
        inventory = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                     for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(inventory == source['files'], 'RMS retained parent differs')
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    require(all(r['event'] in ('hc_norm_owner_replay', 'hc_norm_owner_inputs',
                'hc_norm_owner_timing', 'hc_norm_owner_complete') for r in events),
            'Unexpected RMS event')
    outputs, inputs, _ = coverage()
    replay = [r for r in events if r['event'] == 'hc_norm_owner_replay']
    immutable = [r for r in events if r['event'] == 'hc_norm_owner_inputs']
    timings = [r for r in events if r['event'] == 'hc_norm_owner_timing']
    complete = [r for r in events if r['event'] == 'hc_norm_owner_complete']
    require(len(replay) == 120 and {(r['case'], r['field']) for r in replay} == set(outputs) and
            len(immutable) == 38 and {r['case'] for r in immutable} == set(inputs),
            'Incomplete whole RMS coverage')
    for r in replay:
        size, width, written = outputs[r['case'], r['field']]
        require(r['bytes'] == size and r['width'] == width and r['guards_exact'] and
                r['written_checked'] == written and r['unused_untouched'] == (not written) and
                r['nonfinite_values'] >= 0 and
                r['exact'] == (r['reference_sha256'] == r['candidate_sha256'] and
                               r['nonfinite_values'] == 0), 'RMS output verdict changed')
        if not r['exact']:
            for suffix in ('reference', 'candidate'):
                saved = path / 'results' / (r['case'] + '-' + r['field'] + '-' + suffix + '.bin')
                require(saved.stat().st_size == size + 128 and sha(saved) == r[suffix + '_sha256'],
                        'Full RMS difference array lost')
    require(all(r['immutable'] and r['unused_output_untouched'] for r in immutable),
            'RMS immutable or unused output changed')
    numerical = all(r['exact'] for r in replay)
    require(len(complete) == 1 and complete[0]['cases'] == 38 and
            complete[0]['output_records'] == 120 and complete[0]['timing_samples'] == 28 and
            complete[0]['timing_retained'] and not complete[0]['model_inference'] and
            complete[0]['numerical_pass'] == numerical and
            exits[-1] == (0 if numerical else 1), 'RMS completion differs')
    return dict(schema='synapse-lie.q2-hc-norm-owner-component-results.v1',
        plan_sha256=sha(plan_path), release_sha256=sha(release_path),
        source_variant=arm['variant'], label=arm['label'], command_exits=exits,
        device_work_safe=True, numerical_exact=numerical, case_count=38,
        output_records=replay, inputs=immutable, timings=timings,
        summaries=timing_groups(timings), monotonic_cycle_wall_valid=True,
        invalid_HIP_samples=sum(not r['hip_timer_valid'] for r in timings),
        capsule_sha256=sha(path / 'source.tar.gz'), archive_sha256=sha(path / 'results.tar.gz'),
        artifact_count=len(result['artifacts']), source_files_verified=len(inventory),
        fixture_files_verified=len(plan['fixtures']), binary_sha256=result['binary_sha256'],
        model_inference=False, independent_quality=False, controls_rerun=False,
        full_model_speedup=False, new_model_rate=None, goal_met=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.plan)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(cases=38, outputs=120, numerical_exact=report['numerical_exact'],
        summaries=report['summaries'], model_rate=None)))


if __name__ == '__main__':
    main()
