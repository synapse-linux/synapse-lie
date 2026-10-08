#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the private token160 component and preserve its bounded decision."""

import collections
import hashlib
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-iq2-token160-component-r1'
OUTPUT = ROOT / 'config/q2-iq2-token160-component-results.json'
CASES = ('uniform-e160', 'uniform-e512', 'skew-e64',
         'real-layer0', 'real-layer3', 'real-layer22')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    require(not OUTPUT.exists(), 'Preserve existing component result')
    plan_path = ROOT / 'config/q2-iq2-token160-window-plan.json'
    plan = json.loads(plan_path.read_text())
    admission = json.loads((EVIDENCE / 'admission.json').read_text())
    result = json.loads((EVIDENCE / 'result.json').read_text())
    release = json.loads((EVIDENCE / 'release.json').read_text())
    require(plan['schema'] == 'synapse-lie.q2-iq2-token160-window-plan.v1' and
            plan['component_only'] and not plan['model_access'] and
            not plan['remote_build'] and not plan['remote_cleanup'],
            'Plan scope changed')
    require(admission['state'] == 'Q2_IQ2_TOKEN160_WINDOW_ADMITTED' and
            admission['plan_sha256'] == sha(plan_path) and
            admission['kfd'] == [] and admission['leases_free'] == 5 and
            admission['models_unchanged'] == 7,
            'Admission is incomplete')
    require(release['state'] == 'Q2_IQ2_TOKEN160_WINDOW_RELEASED' and
            release['plan_sha256'] == sha(plan_path) and
            release['admission_sha256'] == sha(EVIDENCE / 'admission.json') and
            release['component_result_sha256'] == sha(EVIDENCE / 'result.json') and
            release['component_exit_code'] == 0 and release['kfd'] == [] and
            release['leases_free'] == 5 and release['models_unchanged'] == 7 and
            not release['remote_cleanup'], 'Window did not release cleanly')
    require(result['schema'] == 'synapse-lie.q2-iq2-token160-component.v1' and
            result['exit_code'] == 0 and result['stop_reason'] is None and
            not result['model_access'] and not result['remote_cleanup'] and
            result['binary_sha256'] == plan['staged_sha256']['q2_iq2_token160_check'] and
            result['stdout_sha256'] == sha(EVIDENCE / 'component.stdout') and
            result['stderr_sha256'] == sha(EVIDENCE / 'component.stderr') and
            (EVIDENCE / 'component.stderr').read_text() == '',
            'Component result or artifact differs')
    require(result['peak_cpu_mc'] <= 98000, 'CPU thermal limit exceeded')
    rows = [json.loads(line) for line in
            (EVIDENCE / 'component.stdout').read_text().splitlines()]
    kinds = collections.Counter(row['event'] for row in rows)
    require(kinds == {'iq2_token160_map': 15, 'iq2_token160_replay': 51,
                      'iq2_token160_timing': 84, 'iq2_token160_complete': 1},
            'Component record count differs')
    require(rows[-1]['numerical_pass'] and not rows[-1]['model_inference'] and
            rows[-1]['timing_retained'], 'Component did not complete')
    maps = [row for row in rows if row['event'] == 'iq2_token160_map']
    require(all(row['row_coverage_exact'] for row in maps),
            'Route coverage failed')
    replays = [row for row in rows if row['event'] == 'iq2_token160_replay']
    require(all(row['exact'] and row['guards_exact'] and
                row['changed_values'] == 0 and row['unwritten_values'] == 0 and
                row['nonfinite_values'] == 0 and
                row['reference_sha256'] == row['candidate_sha256']
                for row in replays), 'Numerical or guard check failed')
    timing = [row for row in rows if row['event'] == 'iq2_token160_timing']
    require(all(not row['hip_timer_valid'] for row in timing),
            'HIP event validity changed; inspect timers')
    comparison = []
    for case in CASES:
        case_rows = [row for row in timing if row['case'] == case]
        require(len(case_rows) == 14 and
                {(row['rep'], row['order']) for row in case_rows} ==
                {(rep, order) for rep in range(7) for order in range(2)},
                'Missing interleaved case timing: ' + case)
        reference = [row['wall_us_per_iteration'] for row in case_rows
                     if not row['warmup'] and not row['candidate']]
        candidate = [row['wall_us_per_iteration'] for row in case_rows
                     if not row['warmup'] and row['candidate']]
        require(len(reference) == len(candidate) == 5 and
                min(reference + candidate) > 0, 'Invalid completed timing')
        before, after = statistics.median(reference), statistics.median(candidate)
        comparison.append({'case': case, 'reference_median_us': before,
                           'candidate_median_us': after,
                           'candidate_time_change_percent': 100 * (after / before - 1),
                           'reference_samples_us': reference,
                           'candidate_samples_us': candidate})
    require(all(row['candidate_time_change_percent'] > 0.8 for row in comparison
                if row['case'] in ('real-layer3', 'real-layer22')),
            'Saved-layer regression gate changed')
    report = {
        'schema': 'synapse-lie.q2-iq2-token160-component-results.v1',
        'plan_sha256': sha(plan_path),
        'admission_sha256': sha(EVIDENCE / 'admission.json'),
        'result_sha256': sha(EVIDENCE / 'result.json'),
        'release_sha256': sha(EVIDENCE / 'release.json'),
        'stdout_sha256': sha(EVIDENCE / 'component.stdout'),
        'event_counts': dict(kinds), 'guarded_exact_replays': len(replays),
        'hip_event_durations_valid': 0,
        'completed_host_wall_medians': comparison,
        'peak_cpu_mc': result['peak_cpu_mc'],
        'peak_gpu_mc': result['peak_gpu_mc'],
        'decision': 'Reject private token160 prefill tile: two of three saved routing layers regress; no complete-model trial.',
        'original_model_run': False, 'production_dispatch_changed': False,
        'pp128_gain_proven': False, 'decode_gain_proven': False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'exact_replays': len(replays),
                      'saved_layer_time_change_percent':
                      {row['case']: row['candidate_time_change_percent']
                       for row in comparison if row['case'].startswith('real-')},
                      'released': True, 'model_run': False}))


if __name__ == '__main__':
    main()
