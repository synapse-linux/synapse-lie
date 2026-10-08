#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the new collected expert chain only after its verified GPU release."""
import datetime
import importlib.util
import json
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
sha, read, require = hc.sha, hc.read, hc.require
PREFIX = 'q2-iq2-whole640-chain'


def main():
    plan_path = ROOT / ('config/' + PREFIX + '-plan.json')
    plan = read(plan_path)
    release_path = ROOT / plan['release_path']
    release = read(release_path)
    require(release['state'] == 'Q2_IQ2_WHOLE640_CHAIN_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256'] == sha(plan_path), 'Window not released')
    path = ROOT / 'evidence' / plan['components'][0]['label']
    result, transport = hc.curve.artifact_integrity(path)
    exits = [command['exit_code'] for command in result['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and transport['exit_code'] == exits[-1] and
            result['mode'] == transport['mode'] == 'iq2-whole640-chain-check' and
            not result['model_access'] and result.get('finished_at') and
            result['binary_sha256'] == result['binary_sha256_after'], 'Incomplete chain')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Lease scope differs')
    prep = ROOT / 'evidence' / (PREFIX + '-preparation')
    collected = read(prep / 'collect-component-command.json')
    require(collected['exit_code'] == 0 and collected['finished_at'] < release['at'],
            'Collection did not precede release')
    provider = read(ROOT / plan['source_variant_manifest'])['variants']['iq2-whole640-chain']
    binding = hc.capsule(path, {**plan['fixtures'], **plan['manifests']}, provider['files'])
    data = path / 'results'
    events = [json.loads(line) for line in (data / '03.log').read_text().splitlines()
              if line.startswith('{')]
    replay = [e for e in events if e.get('event') == 'whole640_chain_replay']
    times = [e for e in events if e.get('event') == 'whole640_chain_timing']
    complete = [e for e in events if e.get('event') == 'whole640_chain_complete']
    require(len(replay) == 17 and len(times) == 14 and len(complete) == 1 and
            complete[0]['safe_device_work'] and complete[0]['immutable_inputs'] and
            sum(row['actual_timed_outputs'] for row in replay) == 7, 'Chain scope differs')
    edge_counts = [[1, 2, 7, 8, 15, 16, 0], [17, 33, 48, 49, 63, 64],
                   [65, 80, 127, 128], [129, 145, 193, 257, 0, 16]]
    exact_pairs = scalar_values = scalar_errors = changed = 0
    for row in replay:
        name, n = row['label'], row['rows']
        counts = ([129] * 8 + [49] * 16 + [6] * 32 + [5] * 8 if name.startswith('timed-')
                  else edge_counts[int(name.split('-')[1])] if name.startswith('edge-')
                  else edge_counts[-1])
        require(sum(counts) == n and row['guards_finite_written_ownership'], 'Row ownership missing')
        fused = []
        for count in counts:
            tail = count % 128
            fused.extend(bool(tail and tail <= 16 and i >= count - tail) for i in range(count))
        mask = np.array(fused[::-1], dtype=bool)
        gate = [np.fromfile(data / (name + f'-arm{a}-gate.f32.bin'), dtype='<f4').reshape(n, 640) for a in (0, 1)]
        require(np.isfinite(gate[0]).all() and np.isfinite(gate[1][~mask]).all() and
                (gate[1].view('<u4')[mask] == 0x7fc0beef).all(), 'Partial F32 ownership differs')
        ordinary_changed = int(np.any(gate[0].view('<u4')[~mask] != gate[1].view('<u4')[~mask], axis=1).sum())
        peak = np.max(np.abs(gate[0]), axis=1)
        shift = np.where(peak == 0, 0, np.clip(14 - np.frexp(peak)[1], -120, 120))
        expected_half = np.ldexp(gate[0], shift[:, None]).astype('<f2')
        expected_inverse = np.ldexp(np.ones(n, dtype='<f4'), -shift)
        values = []
        errors = 0
        suffix = 'f16' if name.endswith('-half') else 'f32'
        for a in (0, 1):
            half = np.fromfile(data / (name + f'-arm{a}-packed.f16.bin'), dtype='<f2').reshape(n, 640)
            inverse = np.fromfile(data / (name + f'-arm{a}-inverse.f32.bin'), dtype='<f4')
            down = np.fromfile(data / (name + f'-arm{a}-down.{suffix}.bin'), dtype='<f2' if suffix == 'f16' else '<f4').reshape(n, 2560)
            require(len(inverse) == n and np.isfinite(half).all() and
                    np.isfinite(inverse).all() and np.isfinite(down).all(), 'Nonfinite saved output')
            errors += int((half.view('<u2') != expected_half.view('<u2')).sum())
            errors += int((inverse.view('<u4') != expected_inverse.view('<u4')).sum())
            scalar_values += n * 641
            values.append((half.tobytes(), inverse.tobytes(), down.tobytes()))
        pairs = sum(x == y for x, y in zip(*values))
        observed = 3 - pairs + ordinary_changed
        require(observed == row['changed_buffers_or_rows'] and errors == row['scalar_pack_mismatches'],
                'Offline reconstruction differs from device receipt')
        exact_pairs += pairs
        changed += observed
        scalar_errors += errors
    require(complete[0]['numeric_mismatches'] == changed + scalar_errors and
            exits[-1] == (1 if changed + scalar_errors else 0), 'Numerical exit lost')
    timing = []
    for arm in (0, 1):
        rows = [e for e in times if e['arm'] == arm]
        require([e['sample'] for e in rows] == list(range(7)) and
                all(e['rotations'] == 3 and e['warmup'] == (e['sample'] < 2) for e in rows),
                'Timing protocol differs')
        samples = [e['gate_pack_down_wall_us'] for e in rows if not e['warmup']]
        require(all(np.isfinite(value) and value > 0 for value in samples), 'Invalid wall time')
        timing.append(dict(arm='parent' if arm == 0 else 'candidate', samples_us=samples,
            warmups_us=[e['gate_pack_down_wall_us'] for e in rows if e['warmup']],
            mean_us=statistics.mean(samples), min_us=min(samples), max_us=max(samples)))
    change = 100 * (timing[1]['mean_us'] / timing[0]['mean_us'] - 1)
    report = dict(schema='synapse-lie.q2-iq2-whole640-chain-component.v1',
        plan_sha256=sha(plan_path), release_sha256=sha(release_path), **binding,
        command_exits=exits, artifact_count=len(result['artifacts']), device_work_safe=True,
        replay=replay, exact_output_pairs=exact_pairs, scalar_packing_values=scalar_values,
        scalar_packing_mismatches=scalar_errors, numeric_changed_buffers_or_rows=changed,
        actual_timed_buffer_replays=7, timing_samples=times, timing=timing,
        complete_chain_time_change_percent=change,
        aggregation='Arithmetic mean of five measured samples; all raw values and warmups retained.',
        controls_rebuilt_or_rerun=False, model_inference=False, independent_model_quality=False,
        limitations='Synthetic mixed expert routing, not model performance or an independent down-product oracle.',
        goal_met=False)
    output = ROOT / ('config/' + PREFIX + '-component-results.json')
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(exact_output_pairs=exact_pairs, scalar_packing_values=scalar_values,
        scalar_packing_mismatches=scalar_errors, timing=timing, time_change_percent=change)))


if __name__ == '__main__':
    main()
