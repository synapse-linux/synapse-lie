#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the private IQ2 token256 GPU screen without inferring model rates."""
import importlib.util
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)


def main():
    prefix = 'q2-iq2-token256'
    pp = ROOT/('config/'+prefix+'-plan.json')
    rp = ROOT/('config/'+prefix+'-window-release.json')
    plan, release = curve.read(pp), curve.read(rp)
    admission = ROOT/plan['admission_path']
    curve.require(release['state'] == 'Q2_IQ2_TOKEN256_WINDOW_RELEASED' and
                  release['plan_sha256'] == curve.sha(pp) and
                  release['admission_sha256'] == curve.sha(admission) and
                  not release['gpu_reserved'] and not release['kfd'] and
                  release['model_stats_unchanged'] and not release['model_inference'] and
                  not release['remote_cleanup'], 'GPU window is not cleanly closed')
    for name, digest in plan['fixtures'].items():
        curve.require(curve.sha(ROOT/name) == digest, 'Frozen fixture changed: '+name)
    directory = ROOT/'evidence'/(prefix+'-component-r1')
    result, transport = curve.artifact_integrity(directory)
    exits = [x['exit_code'] for x in result['commands']]
    curve.require(exits == [0, 0, 0] and transport['exit_code'] == 0 and
                  result['state'] == 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED' and
                  result['mode'] == 'iq2-token256-check' and not result['model_access'] and
                  not result['preflight_kfd'] and not result['postflight_kfd'],
                  'Component receipt did not pass')
    rows = [json.loads(s) for s in (directory/'results/03.log').read_text().splitlines()
            if s.startswith('{')]
    counts = Counter(x['event'] for x in rows)
    curve.require(counts == dict(iq2_token256_map=15, iq2_token256_replay=51,
                                 iq2_token256_timing=84, iq2_token256_complete=1),
                  'Component event counts differ')
    curve.require(rows[-1]['numerical_pass'] and not rows[-1]['model_inference'],
                  'Numerical summary did not pass')
    maps = [x for x in rows if x['event'] == 'iq2_token256_map']
    replays = [x for x in rows if x['event'] == 'iq2_token256_replay']
    timings = [x for x in rows if x['event'] == 'iq2_token256_timing']
    timed_cases = ('uniform-e160', 'uniform-e512', 'skew-e64',
                   'real-layer0', 'real-layer3', 'real-layer22')
    edge_cases = tuple('fixed-edge-n'+str(n) for n in
                       (1, 17, 65, 145, 255, 256, 257, 409, 512))
    curve.require({x['case'] for x in maps} == set(timed_cases+edge_cases) and
                  len({x['case'] for x in maps}) == 15 and
                  all(x['row_coverage_exact'] for x in maps), 'Route map coverage differs')
    for case in timed_cases+edge_cases:
        case_replays = [x for x in replays if x['case'] == case]
        expected = {(False, r) for r in range(3)}
        if case in timed_cases:
            expected.add((True, 2))
        curve.require({(x['after_timing'], x['rotation']) for x in case_replays} == expected and
                      len(case_replays) == len(expected) and
                      all(x['exact'] and x['guards_exact'] and not x['packed'] and
                          x['changed_values'] == x['nonfinite_values'] ==
                          x['unwritten_values'] == 0 and
                          x['reference_sha256'] == x['candidate_sha256']
                          for x in case_replays), 'Output comparison differs: '+case)
    measurements = {}
    for case in timed_cases:
        case_rows = [x for x in timings if x['case'] == case]
        curve.require(len(case_rows) == 14 and
                      {(x['rep'], x['order']) for x in case_rows} ==
                      {(rep, order) for rep in range(7) for order in range(2)} and
                      all(x['warmup'] == (x['rep'] < 2) and
                          x['candidate'] == bool((x['rep'] + x['order']) % 2) and
                          x['iterations'] == 3 and x['tokens'] == 2048 and
                          x['wall_us_per_iteration'] > 0 for x in case_rows),
                      'Timing schedule differs: '+case)
        arms = {}
        for candidate, name in ((False, 'retained128'), (True, 'candidate256')):
            selected = [x for x in case_rows if x['candidate'] == candidate and
                        not x['warmup']]
            curve.require(len(selected) == 5 and
                          {x['rep'] for x in selected} == set(range(2, 7)),
                          'Measured samples differ: '+case)
            values = [x['wall_us_per_iteration'] for x in selected]
            arms[name] = dict(samples_completed_wall_us=values,
                              median_us=statistics.median(values),
                              range_us=[min(values), max(values)])
        measurements[case] = dict(**arms, time_change_percent=100*(
            arms['candidate256']['median_us']/arms['retained128']['median_us']-1))
    report = dict(schema='synapse-lie.q2-iq2-token256-component-results.v1',
                  plan_sha256=curve.sha(pp), admission_sha256=curve.sha(admission),
                  release_sha256=curve.sha(rp),
                  component_receipt_sha256=curve.sha(directory/'results/result.json'),
                  archive_sha256=curve.sha(directory/'results.tar.gz'),
                  raw_log_sha256=curve.sha(directory/'results/03.log'),
                  command_exits=exits, events=dict(counts),
                  maps_exact=len(maps), replays_exact=len(replays),
                  gpu_event_valid_count=sum(x['hip_timer_valid'] for x in timings),
                  gpu_event_invalid_count=sum(not x['hip_timer_valid'] for x in timings),
                  measurements=measurements, model_inference=False,
                  production_dispatch_changed=False, promoted=False,
                  decision='Reject token256 gate/up producer: all three saved-routing layers '
                           'regress in completed component wall time. Keep the retained128/64 path.',
                  limits=['Synthetic rotating weights with saved routing counts; no original-model inference.',
                          'Completed host wall times include GPU submission and synchronization; all HIP events are invalid zero.',
                          'Gate/up component time cannot be converted to whole-model PP or TG.'])
    output = ROOT/('config/'+prefix+'-component-results.json')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('schema', 'events', 'decision')}, indent=2))


if __name__ == '__main__':
    main()
