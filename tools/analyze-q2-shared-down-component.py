#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the four shared-down paths and retain safe numerical rejections."""
import importlib.util
import json
import math
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read
ARMS = ('original-q8', 'generic-f16', 'fixed-q8', 'fixed-f16')
SHAPES = (96, 97, 127, 129, 1025, 2048, 2049)


def analyze_events(events, exit_code):
    records = {name: [r for r in events if r['event'] == 'shared_down_mirror_' + name]
               for name in ('format', 'pair', 'oracle', 'timing', 'complete')}
    formats, pairs, oracles, timings, complete = (records[k] for k in records)
    cases = {(n, r) for n in SHAPES for r in range(24 if n == 2048 else 3)}
    require(len(formats) == 42 and {(r['tokens'], r['rotation']) for r in formats} == cases,
            'Incomplete mirror format coverage')
    for r in formats:
        require(r['values'] == 2560 * 640 and r['guards_exact'] and r['unwritten'] == 0,
                'Unsafe or incomplete mirror writes')
        require(0 <= r['changed'] <= r['values'] and r['pass'] == (r['changed'] == 0),
                'Inconsistent mirror format verdict')
    require(len(pairs) == 126 and
            {(r['tokens'], r['rotation'], r['arm']) for r in pairs} ==
            {(*case, arm) for case in cases for arm in ARMS[1:]}, 'Incomplete output coverage')
    for r in pairs:
        require(r['guards_exact'] and r['unwritten'] == 0, 'Unsafe or missing output writes')
        require(0 <= r['changed'] <= r['tokens'] * 2560 and
                0 <= r['nonfinite'] <= r['tokens'] * 2560, 'Invalid output counters')
        require(r['exact'] == (r['changed'] == r['nonfinite'] == 0) and
                (r['reference_sha256'] == r['candidate_sha256']) == (r['changed'] == 0),
                'Inconsistent output comparison')
    require(len(oracles) == 168 and
            {(r['tokens'], r['rotation'], r['arm']) for r in oracles} ==
            {(*case, arm) for case in cases for arm in ARMS}, 'Incomplete independent checks')
    for r in oracles:
        bounded = all(isinstance(r[k], (float, int)) and math.isfinite(r[k]) and 0 <= r[k] <= .002
                      for k in ('relative_rms', 'scaled_error'))
        require(r['samples'] == 24 and r['limit'] == .002 and r['pass'] == (r['finite'] and bounded),
                'Changed independent operator limit or verdict')
    numerical = all(r['pass'] for r in formats + oracles) and all(r['exact'] for r in pairs)
    require(len(complete) == 1 and complete[0]['numerical_pass'] == numerical and
            complete[0]['timing_retained'] and not complete[0]['model_inference'] and
            exit_code == (0 if numerical else 1), 'Lost actual numerical result or completion')
    require(len(timings) == 28, 'Incomplete timings')
    summaries = {}
    for arm in ARMS:
        rows = [r for r in timings if r['arm'] == arm]
        require([r['rep'] for r in rows] == list(range(7)) and
                all(r['warmup'] == (r['rep'] < 2) and r['tokens'] == 2048 and
                    0 <= r['order'] < 4 and ARMS[(r['rep'] + r['order']) % 4] == arm and
                    r['iterations'] == 24 and r['q8_weight_bytes'] == 41779200 and
                    r['mirror_weight_bytes'] == 78643200 and
                    math.isfinite(r['us_per_iteration']) and r['us_per_iteration'] > 0
                    for r in rows), 'Changed timed scope, order or weight rotations')
        summaries[arm] = hc.shared.common.stats([r['us_per_iteration'] for r in rows if not r['warmup']])
    changes = {arm: 100 * (summaries[arm]['median'] / summaries[ARMS[0]]['median'] - 1)
               for arm in ARMS[1:]}
    return dict(formats=formats, replay=pairs, oracle=oracles, timings=timings,
                summaries=summaries, time_change_percent=changes, numerical_pass=numerical,
                format_pass=all(r['pass'] for r in formats),
                parent_exact=all(r['exact'] for r in pairs),
                independent_operator_pass=all(r['pass'] for r in oracles))


def main(prefix='q2-shared-down-component'):
    plan_path = ROOT / 'config' / (prefix + '-plan.json')
    plan = read(plan_path)
    for path, digest in {**plan['fixtures'], **plan['manifests'],
                         plan['window_helper']: plan['window_helper_sha256']}.items():
        require(sha(ROOT/path) == digest, 'Frozen identity changed: ' + path)
    host_path = ROOT/'evidence'/plan['host']
    host, _ = hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']),
            'Host qualification incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 27' in (host_path/'results'/name).read_text(),
                'Host test count changed')
    host_binding = hc.capsule(host_path, plan['fixtures'])
    arm = plan['component']
    path = ROOT/'evidence'/arm['label']
    result, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete or changed component')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Component ownership changed')
    source = read(ROOT/plan['source_manifest'])['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    events = [json.loads(line) for line in (path/'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    analysis = analyze_events(events, exits[-1])
    report = dict(schema='synapse-lie.q2-shared-down-component.v1', **capsule, **analysis,
                  plan_sha256=sha(plan_path), source_variant=arm['variant'], device_work_safe=True,
                  command_exits=exits, artifact_count=len(result['artifacts']),
                  binary_sha256=result['binary_sha256'], host=host_binding,
                  model_inference=False, original_inputs_immutable_at_fixture_completion=True,
                  control_scope='Original Q8 shared down from saved1580; its production kernel is also '
                      'unchanged in saved1585. Three candidate paths are component-only. '
                      'Independent FP64 is synthetic operator evidence, not task-quality qualification.',
                  full_model_speedup=False, goal_met=False, timing_scope=plan['timing_scope'])
    hc.write(ROOT/'config'/(prefix + '-results.json'), report)
    print(json.dumps({k: report[k] for k in ('command_exits', 'parent_exact', 'independent_operator_pass',
                                            'format_pass', 'summaries', 'time_change_percent')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign', nargs='?', default='q2-shared-down-component',
                        choices=('q2-shared-down-component', 'q2-shared-down-n64-component'))
    main(parser.parse_args().campaign)
