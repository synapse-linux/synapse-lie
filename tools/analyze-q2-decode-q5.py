#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the closed Q5/Q8 synthetic component and retain matched timings."""

from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
LABEL = 'q2-decode-q5-component-r2'
EVIDENCE = ROOT / 'evidence' / LABEL
PLAN = ROOT / 'config/q2-decode-q5-r2-window-plan.json'
OUTPUT = ROOT / 'config/q2-decode-q5-r2-results.json'
TIMED = ('ssm-in', 'attn-out', 'shared-down', 'gated')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((EVIDENCE / name).read_text())


def main(verify_only=False):
    require(OUTPUT.exists() if verify_only else not OUTPUT.exists(),
            'Analyzed result presence differs from requested mode')
    plan = json.loads(PLAN.read_text())
    admission, result, release = (load(name) for name in
                                  ('admission.json', 'result.json', 'release.json'))
    registry = load('registry-check.json')
    require(plan['label'] == LABEL and admission['plan_sha256'] == sha(PLAN) and
            admission['state'] == 'Q2_DECODE_Q5_WINDOW_ADMITTED' and
            result['binary_sha256'] == plan['staged_sha256']['q2_decode_q5_dense_check'] and
            result['exit_code'] == 0 and result['stop_reason'] is None and
            not result['model_access'] and not result['remote_cleanup'] and
            result['stdout_sha256'] == sha(EVIDENCE / 'component.stdout') and
            result['stderr_sha256'] == sha(EVIDENCE / 'component.stderr') and
            release['state'] == 'Q2_DECODE_Q5_WINDOW_RELEASED' and
            release['admission_sha256'] == sha(EVIDENCE / 'admission.json') and
            release['component_result_sha256'] == sha(EVIDENCE / 'result.json') and
            release['component_exit_code'] == 0 and release['kfd'] == [] and
            release['leases_free'] == 5 and release['models_unchanged'] == 7 and
            len(release['retired_identities']) == 1954 and
            len(release['retired_groups']) == 1560 and
            not release['gpu_reserved'] and not release['model_access'] and
            not release['remote_cleanup'] and
            registry == {'event': 'window_release', 'owner': 'synapse-lie-q2',
                         'receipt_sha256': sha(EVIDENCE / 'release.json'),
                         'actual_sha256': sha(EVIDENCE / 'release.json'),
                         'kfd_clients': 0}, 'Window evidence differs')
    events = [json.loads(line) for line in
              (EVIDENCE / 'component.stdout').read_text().splitlines()]
    counts = Counter(event['event'] for event in events)
    require(counts == {'q5_dense_oracle': 60, 'q5_dense_pair': 30,
                       'q5_dense_case': 6, 'q5_dense_timing': 56,
                       'q5_dense_complete': 1}, 'Component event counts differ')
    require(all(event['pass'] for event in events if event['event'] in
                ('q5_dense_oracle', 'q5_dense_pair', 'q5_dense_case')) and
            events[-1]['event'] == 'q5_dense_complete' and
            events[-1]['numerical_pass'] and not events[-1]['model_inference'],
            'Numerical gate differs')
    timing = [event for event in events if event['event'] == 'q5_dense_timing']
    cases = {}
    for name in TIMED:
        rows = [event for event in timing if event['case'] == name]
        require(len(rows) == 14 and
                {(event['rep'], event['arm']) for event in rows} ==
                {(rep, arm) for rep in range(7) for arm in (0, 1)} and
                all(event['warmup'] == (event['rep'] < 2) and
                    event['iterations'] >= 64 and
                    event['rotated_weight_bytes_q8'] > 48 * 1024 * 1024 and
                    event['rotated_weight_bytes_q5'] > 48 * 1024 * 1024 and
                    event['completed_wall_us'] > 0 and
                    not event['gpu_event_valid'] for event in rows),
                'Timing conditions differ: ' + name)
        samples = {arm: [event['completed_wall_us'] for event in rows
                         if event['arm'] == arm and not event['warmup']]
                   for arm in (0, 1)}
        baseline, candidate = (statistics.median(samples[arm])
                               for arm in (0, 1))
        pair_changes = [100 * (next(e['completed_wall_us'] for e in rows
                                   if e['rep'] == rep and e['arm'] == 1) /
                               next(e['completed_wall_us'] for e in rows
                                    if e['rep'] == rep and e['arm'] == 0) - 1)
                        for rep in range(2, 7)]
        cases[name] = {
            'q8_median_completed_wall_us': baseline,
            'q5_median_completed_wall_us': candidate,
            'candidate_change_percent': 100 * (candidate / baseline - 1),
            'paired_change_percent': pair_changes,
            'paired_median_change_percent': statistics.median(pair_changes),
            'iterations_per_record': rows[0]['iterations'],
            'rotated_weight_bytes_q8': rows[0]['rotated_weight_bytes_q8'],
            'rotated_weight_bytes_q5': rows[0]['rotated_weight_bytes_q5'],
        }
    oracles = [event['relative_rms'] for event in events
               if event['event'] == 'q5_dense_oracle']
    pairs = [event['relative_rms'] for event in events
             if event['event'] == 'q5_dense_pair']
    report = {
        'schema': 'synapse-lie.q2-decode-q5-r2-results.v1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'plan_sha256': sha(PLAN),
        'evidence_sha256': {name: sha(EVIDENCE / name) for name in (
            'preflight.json', 'admission.json', 'result.json', 'release.json',
            'component.stdout', 'component.stderr', 'release-command.stdout',
            'registry-check.json')},
        'event_counts': dict(counts),
        'max_oracle_relative_rms': max(oracles),
        'max_equal_weight_pair_relative_rms': max(pairs),
        'timing_source': 'completed host wall; HIP event durations invalid zero',
        'warmup_repetitions_excluded': 2,
        'measured_repetitions_per_arm': 5,
        'cases': cases,
        'model_inference': False,
        'model_quality': False,
        'full_c1_decode': False,
        'remote_cleanup': False,
    }
    if verify_only:
        saved = json.loads(OUTPUT.read_text())
        report['at'] = saved['at']
        require(saved == report, 'Saved Q5 result differs from raw evidence')
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': cases, 'max_oracle_relative_rms': max(oracles),
                      'max_pair_relative_rms': max(pairs)}, indent=2))


if __name__ == '__main__':
    require(len(sys.argv) == 1 or sys.argv == [sys.argv[0], '--verify'],
            'Expected --verify or no arguments')
    main(len(sys.argv) == 2)
