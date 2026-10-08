#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit collected whole640 outputs and timings only after verified release."""
import datetime
import importlib.util
import json
from pathlib import Path
import statistics
import tarfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require


def main():
    plan_path = ROOT / 'config/q2-iq2-whole640-wave16-plan.json'
    release_path = ROOT / 'config/q2-iq2-whole640-wave16-window-release.json'
    plan, release = read(plan_path), read(release_path)
    require(release['state'] == 'Q2_IQ2_WHOLE640_WAVE16_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256'] == sha(plan_path), 'Window is not released')
    label = plan['components'][0]['label']
    directory = ROOT / 'evidence' / label
    result, transport = curve.artifact_integrity(directory)
    require(result['mode'] == transport['mode'] == 'iq2-whole640-wave16-check' and
            not result['model_access'] and result.get('finished_at') and
            [c['exit_code'] for c in result['commands']] == [0, 0, 0] and
            transport['exit_code'] == 0 and
            result['binary_sha256'] == result['binary_sha256_after'], 'Component incomplete')
    collected = read(ROOT / 'evidence/q2-iq2-whole640-wave16-fixture-preparation/collect-component-command.json')
    require(collected['exit_code'] == 0 and
            datetime.datetime.fromisoformat(collected['finished_at']) <
            datetime.datetime.fromisoformat(release['at']), 'Collection did not precede release')
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
            import hashlib
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Component capsule differs: ' + name)
    data = directory / 'results'
    events = [json.loads(line) for line in (data / '03.log').read_text().splitlines()
              if line.startswith('{')]
    replays = [event for event in events if event['event'] == 'whole640_wave16_replay']
    timings = [event for event in events if event['event'] == 'whole640_wave16_timing']
    complete = [event for event in events if event['event'] == 'whole640_wave16_complete']
    require(len(replays) == 56 and len(timings) == 63 and len(complete) == 1 and
            complete[0]['numeric_mismatches'] == 0 and complete[0]['safe_device_work'],
            'Component evidence scope differs')
    require(sum(row['actual_timed_outputs'] for row in replays) == 21,
            'Actual timed buffers missing')
    pairs, scalar_values = 0, 0
    for row in replays:
        require(row['guards_finite_immutable'] and row['changed_values'] == 0 and
                row['scalar_pack_mismatches'] == 0, 'Device replay differs')
        count = row['rows_per_expert'] * row['experts']
        name = row['label']
        parent = np.fromfile(data / (name + '-parent.f32'), dtype='<f4').reshape(count, 640)
        half = np.fromfile(data / (name + '-arm0.f16'), dtype='<f2').reshape(count, 640)
        inverse = np.fromfile(data / (name + '-arm0-inverse.f32'), dtype='<f4')
        require(len(inverse) == count and np.isfinite(parent).all() and
                np.isfinite(half).all() and np.isfinite(inverse).all(), 'Nonfinite saved output')
        peak = np.max(np.abs(parent), axis=1)
        shift = np.where(peak == 0, 0, np.clip(14 - np.frexp(peak)[1], -120, 120))
        expected_half = np.ldexp(parent, shift[:, None]).astype('<f2')
        expected_inverse = np.ldexp(np.ones(count, dtype='<f4'), -shift)
        require(expected_half.tobytes() == half.tobytes() and
                expected_inverse.tobytes() == inverse.tobytes(), 'Saved scalar packing differs')
        scalar_values += count * 641
        if row['ineligible']:
            require(row['rows_per_expert'] == 17, 'Unexpected ineligible route')
            continue
        for arm in (1, 2):
            require((data / (name + f'-arm{arm}.f16')).read_bytes() == half.tobytes() and
                    (data / (name + f'-arm{arm}-inverse.f32')).read_bytes() == inverse.tobytes(),
                    'Saved candidate output differs')
            pairs += 1
    require(pairs == 104, 'Whole-output pair count differs')
    cases = []
    for live in (4, 8, 16):
        arms = []
        for arm in range(3):
            rows = [row for row in timings if row['label'] == f'timed-{live}' and row['arm'] == arm]
            require(len(rows) == 7 and sorted(row['sample'] for row in rows) == list(range(7)) and
                    all(row['warmup'] == (row['sample'] < 2) and row['rotations'] == 3 for row in rows),
                    'Timing repetitions differ')
            samples = [row['gate_up_pack_wall_us'] for row in rows if not row['warmup']]
            require(all(np.isfinite(value) and value > 0 for value in samples), 'Invalid timing')
            arms.append(dict(arm=plan['timing_arms'][arm], samples_us=samples,
                             warmups_us=[row['gate_up_pack_wall_us'] for row in rows if row['warmup']],
                             mean_us=statistics.mean(samples), min_us=min(samples), max_us=max(samples)))
        for arm in arms:
            arm['time_change_percent'] = 100 * (arm['mean_us'] / arms[0]['mean_us'] - 1)
        cases.append(dict(live_rows=live, experts=64, arms=arms))
    report = dict(schema='synapse-lie.q2-iq2-whole640-wave16-results.v1', label=label,
        result_sha256=sha(data / 'result.json'), plan_sha256=sha(plan_path),
        release_sha256=sha(release_path), commands=[0, 0, 0],
        verified_artifacts=len(result['artifacts']), edge_cases=32, replay_records=56,
        exact_output_pairs=pairs, scalar_packing_values=scalar_values,
        actual_timed_buffer_replays=21, timing_records=63, timing_cases=cases,
        aggregation='Arithmetic mean of five measured component samples; all raw samples retained.',
        retained_model_PP=1587.893545, retained_model_TG=25.12414406,
        fixed_UD_PP=1685.777092, fixed_UD_TG=24.34174251,
        disposition='Component timings only; model integration and fixed-reference measurement remain separate.',
        limitations='Synthetic selected tails, not mixed routing/down/model throughput or independent model quality.',
        model_inference=False, controls_rebuilt_or_rerun=False, goal_met=False)
    output = ROOT / 'config/q2-iq2-whole640-wave16-results.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(exact_output_pairs=pairs, scalar_packing_values=scalar_values,
                         timing_cases=cases, goal_met=False)))


if __name__ == '__main__':
    main()
