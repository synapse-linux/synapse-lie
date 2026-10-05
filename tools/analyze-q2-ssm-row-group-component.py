#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain complete SSM replay, independent operator checks and cycle timings."""
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def analyze_events(events, plan, exit_code):
    replay = [e for e in events if e['event'] == 'ssm_row_group_replay']
    oracle = [e for e in events if e['event'] == 'ssm_row_group_oracle']
    timings = [e for e in events if e['event'] == 'ssm_row_group_timing']
    complete = [e for e in events if e['event'] == 'ssm_row_group_complete']
    require(len(replay) == plan['component_expected_output_pairs'] and
            len(oracle) == plan['component_expected_oracle_checks'] and
            len(timings) == plan['component_expected_timing_samples'] and
            len(complete) == 1 and complete[0]['timing_retained'] and
            not complete[0]['model_inference'], 'Missing complete component evidence')
    cases = {'ssm' + str(n): n for n in plan['component_shapes']}
    expected = {(name, rotation, field) for name in cases
                for rotation in range(3) for field in ('projection', 'convolution')}
    require({(e['shape'], e['rotation'], e['field']) for e in replay} == expected,
            'Changed complete-output coverage')
    for row in replay:
        tokens = cases[row['shape']]
        projection = row['field'] == 'projection'
        width = 16384 if projection else 10240
        # Only raw QKV interior rows are intentionally absent; all convolution
        # and all nonconvolved projected channels must be written.
        unused_tokens = sum(t % 32 >= 3 and t % 32 < 29 and t + 3 < tokens
                            for t in range(tokens)) if projection else 0
        unused = unused_tokens * 10240
        require(row['bytes'] == tokens * width * 4 and
                row['required_values'] == tokens * width - unused and
                row['expected_unused_values'] == unused,
                'Projection/convolution ownership or output size changed')
        require(row['guards_exact'] and row['unwritten_values'] == 0 and
                row['unexpected_unused_values'] == 0, 'Unsafe or missing output writes')
        require(0 <= row['changed_values'] <= tokens * width and
                0 <= row['nonfinite_values'] <= row['required_values'],
                'Invalid numerical counters')
        exact = row['changed_values'] == 0 and row['nonfinite_values'] == 0
        require(row['exact'] == exact and
                (row['reference_sha256'] == row['candidate_sha256']) ==
                (row['changed_values'] == 0), 'Inconsistent replay verdict')
    require({(e['shape'], e['rotation'], e['field'], e['arm']) for e in oracle} ==
            {(*key, arm) for key in expected for arm in ('reference', 'candidate')},
            'Changed independent operator coverage')
    for row in oracle:
        finite = all(math.isfinite(row[k]) and row[k] >= 0
                     for k in ('relative_rms', 'scaled_error'))
        require(row['samples'] == 24 and row['limit'] == 0.002 and
                row['pass'] == (finite and row['relative_rms'] <= 0.002 and
                                row['scaled_error'] <= 0.002),
                'Independent operator limit or verdict changed')
    numerical = all(e['exact'] for e in replay) and all(e['pass'] for e in oracle)
    require(complete[0]['numerical_pass'] == numerical and
            exit_code == (0 if numerical else 1), 'Lost numeric rejection or actual exit')
    pair = {}
    for candidate in (False, True):
        rows = [t for t in timings if t['candidate'] == candidate]
        require([r['rep'] for r in rows] == list(range(7)) and
                [r['warmup'] for r in rows] == [True, True] + [False] * 5 and
                all(r['shape'] == 'ssm2048' and r['tokens'] == 2048 and
                    r['output_rows'] == 16384 and r['inner'] == 2560 and
                    r['order'] in (0, 1) and
                    r['candidate'] == (((r['rep'] + r['order']) % 2) != 0) and
                    r['iterations'] == 3 and
                    r['weight_bytes'] == plan['component_weight_rotation_bytes'] and
                    r['weight_bytes'] > 32 * 1024 * 1024 and
                    math.isfinite(r['us_per_iteration']) and r['us_per_iteration'] > 0
                    for r in rows), 'Changed timed shape, order, rotations or samples')
        pair['candidate' if candidate else 'reference'] = hc.shared.common.stats(
            [r['us_per_iteration'] for r in rows if not r['warmup']])
    summary = dict(case='ssm2048', scope='projection-convolution', **pair,
                   candidate_time_change_percent=100 *
                   (pair['candidate']['median'] / pair['reference']['median'] - 1))
    return dict(replay=replay, oracle=oracle, timings=timings, summaries=[summary],
                parent_exact=all(e['exact'] for e in replay),
                independent_operator_pass=all(e['pass'] for e in oracle),
                numerical_pass=numerical)


def main():
    output = ROOT / 'config/q2-ssm-row-group-component-results.json'
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT / name) == digest, 'Frozen identity changed: ' + name)
    arm = plan['components'][0]
    path = ROOT / 'evidence' / arm['label']
    result, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete or changed component')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Component ownership changed')
    source = read(ROOT / plan['source_variant_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    events = [json.loads(line) for line in (path / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    analysis = analyze_events(events, plan, exits[-1])
    report = dict(schema='synapse-lie.q2-ssm-row-group-component.v1', **capsule, **analysis,
                  plan_sha256=sha(plan_path), source_variant=arm['variant'], device_work_safe=True,
                  command_exits=exits, artifact_count=len(result['artifacts']),
                  binary_sha256=result['binary_sha256'], model_inference=False,
                  original_inputs_immutable_at_fixture_completion=True,
                  control_scope='Literal saved1580 SSM projection and convolution; sampled '
                  'independent FP64 synthetic operator. Inherited F16 task quality remains separate.',
                  independent_model_quality_qualification=False, full_model_speedup=False,
                  goal_met=False, timing_scope=plan['component_time_scope'])
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(command_exits=exits, parent_exact=analysis['parent_exact'],
                          independent_operator_pass=analysis['independent_operator_pass'],
                          output_pairs=len(analysis['replay']), oracle_checks=len(analysis['oracle']),
                          timings=len(analysis['timings']), summaries=analysis['summaries'])))


if __name__ == '__main__':
    main()
