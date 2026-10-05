#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain all SSM row-tile outputs, actual exits and rotated-weight timings."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, read, sha = hc.require, hc.read, hc.sha


def main():
    output = ROOT / 'config/q2-ssm-row128-component-results.json'
    csv_path = ROOT / 'docs/figures/q2-ssm-row128-component.csv'
    require(not output.exists() and not csv_path.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT / 'config/q2-ssm-row128-plan.json'
    plan = read(plan_path)
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT / name) == expected, 'Frozen bytes changed: ' + name)
    arm = plan['component']
    path = ROOT / 'evidence' / arm['label']
    receipt, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in receipt['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and receipt['finished_at'] and
            receipt['mode'] == transport['mode'] == arm['mode'] and transport['source_variant'] == arm['variant'] and
            not transport['rebuild_mmq'] and not receipt['model_access'] and
            receipt['binary_sha256'] == receipt['binary_sha256_after'], 'Changed or incomplete component scope')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
            not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Component ownership changed')
    source = read(ROOT / plan['source_variant_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    replay = [r for r in events if r['event'] == 'ssm_row128_replay']
    timings = [r for r in events if r['event'] == 'ssm_row128_timing']
    complete = [r for r in events if r['event'] == 'ssm_row128_complete']
    require(len(replay) == 24 and len(timings) == 14 and len(complete) == 1 and
            complete[0]['timing_retained'] and not complete[0]['model_inference'], 'Incomplete output/timing evidence')
    for shape, coverage in plan['component_raw_live_counts'].items():
        rows = [r for r in replay if r['shape'] == shape]
        require([(r['rotation'], r['field']) for r in rows] ==
                [(i, f) for i in range(3) for f in ('projection', 'convolution')], 'Shape replay incomplete')
        for row in rows:
            raw = row['field'] == 'projection'
            values = coverage['tokens'] * (16384 if raw else 10240)
            require(row['bytes'] == values * 4 and row['guards_exact'] and
                    row['required_values'] == (coverage['required_values'] if raw else values) and
                    row['expected_unused_values'] == (coverage['expected_unused_values'] if raw else 0),
                    'Required raw/complete convolution coverage changed')
            exact = all(row[k] == 0 for k in ('changed_values', 'nonfinite_values', 'unwritten_values', 'unexpected_unused_values'))
            require(row['exact'] == exact and (row['changed_values'] == 0) ==
                    (row['reference_sha256'] == row['candidate_sha256']), 'Raw replay verdict changed')
    numerical = all(r['exact'] for r in replay)
    require(complete[0]['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Original verdict or actual command exit lost')
    pair = {}
    for candidate in (False, True):
        rows = [r for r in timings if r['candidate'] == candidate]
        require([r['rep'] for r in rows] == list(range(7)) and
                [r['warmup'] for r in rows] == [True, True] + [False] * 5 and
                all(r['shape'] == 'ssm2048' and r['tokens'] == 2048 and r['output_rows'] == 16384 and
                    r['inner'] == 2560 and r['iterations'] == 3 and r['weight_bytes'] == 133693440 and
                    r['candidate'] == (((r['rep'] + r['order']) % 2) != 0) and r['us_per_iteration'] > 0
                    for r in rows), 'Timing scope/order/rotation changed')
        pair['candidate' if candidate else 'reference'] = hc.shared.common.stats(
            [r['us_per_iteration'] for r in rows if not r['warmup']])
    summary = dict(shape='ssm2048', **pair, candidate_time_change_percent=
                   100 * (pair['candidate']['median'] / pair['reference']['median'] - 1))
    report = dict(schema='synapse-lie.q2-ssm-row128-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(receipt['artifacts']),
        binary_sha256=receipt['binary_sha256'], numerical_exact=numerical, replay=replay, timings=timings,
        summaries=[summary], original_inputs_immutable_at_fixture_completion=True,
        live_raw_projection_mask_checked=True, complete_convolution_checked=True, model_inference=False,
        control_scope='Literal parent numerical control in this new fixture; no qualified control/cohort rerun',
        independent_model_quality_qualification=False, full_model_speedup=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    with csv_path.open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(timings[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(timings)
    print(json.dumps(dict(command_exits=exits, numerical_exact=numerical, whole_buffer_pairs=24,
                         timing_samples=14, summary=summary)))


if __name__ == '__main__':
    main()
