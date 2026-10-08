#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit exact and nonexact Q2 down results without suppressing performance."""
import csv
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-decode-down-rows-component-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    collected = json.loads((EVIDENCE / 'collection.json').read_text())
    for name, digest in collected.items():
        assert sha(EVIDENCE / name) == digest, name
    plan = json.loads((EVIDENCE / 'plan.json').read_text())
    assert sha(EVIDENCE / 'plan.json') == sha(ROOT / 'config/q2-decode-down-rows-plan.json')
    for name, digest in {**plan['staged_sha256'], **plan['cpu_check_sha256']}.items():
        assert sha(EVIDENCE / name) == digest, name
    result = json.loads((EVIDENCE / 'result.json').read_text())
    release = json.loads((EVIDENCE / 'release.json').read_text())
    registry = json.loads((EVIDENCE / 'release-registry.json').read_text())
    assert sha(EVIDENCE / 'release.json') == registry['receipt_sha256']
    assert release['component_result_sha256'] == sha(EVIDENCE / 'result.json')
    assert release['component_exit_code'] == result['exit_code']
    assert result['stop_reason'] is None and result['exit_code'] in (0, 1)
    assert release['kfd'] == [] and release['leases_free'] == 5
    assert release['models_unchanged'] == 7 and not release['remote_cleanup']
    assert {'pid': result['pid'], 'start_ticks': result['start_ticks']} in release['retired_identities']
    assert result['process_group'] in release['retired_groups']
    rows = [json.loads(line) for line in (EVIDENCE / 'component.stdout').read_text().splitlines()
            if line.startswith('{')]
    replay = [r for r in rows if r['event'] == 'down_rows_replay']
    oracle = [r for r in rows if r['event'] == 'down_rows_oracle']
    timing = [r for r in rows if r['event'] == 'down_rows_timing']
    complete = [r for r in rows if r['event'] == 'down_rows_complete']
    assert len(replay) == 906 and len(oracle) == 1359 and len(timing) == 21
    assert len(complete) == 1 and complete[0]['safe_completion']
    assert all(r['guards_exact'] for r in replay)
    assert all(r['limit'] == 0.002 for r in oracle)
    numerical_pass = all(r['exact'] for r in replay) and all(r['pass'] for r in oracle)
    assert complete[0]['numerical_pass'] == numerical_pass
    assert result['exit_code'] == (0 if numerical_pass else 1)
    assert all(r['calls'] == 64 and r['weight_bytes'] == 82575360 and
               r['complete_cycle_us'] > 0 for r in timing)
    arms = {}
    for arm in (2, 4, 8):
        samples = [r['complete_cycle_us'] for r in timing if r['arm'] == arm and not r['warmup']]
        assert len(samples) == 5
        pairs = []
        for rep in range(2, 7):
            group = {r['arm']: r['complete_cycle_us'] for r in timing if r['rep'] == rep}
            assert len(group) == 3
            pairs.append(100 * (group[arm] / group[2] - 1))
        arms[str(arm)] = {'samples_us': samples, 'median_us': statistics.median(samples),
                          'mean_us': statistics.mean(samples), 'paired_changes_percent': pairs}
    for arm in (4, 8):
        total_error, total_norm, maximum, changed, cells, buffers = 0., 0., 0., 0, 0, 0
        for path in sorted((EVIDENCE / 'results').glob(f'*-{arm}-original.f32')):
            candidate = path.with_name(path.name.replace('-original.f32', '-candidate.f32'))
            original = np.fromfile(path, dtype='<f4')
            new = np.fromfile(candidate, dtype='<f4')
            assert original.shape == new.shape
            assert np.isfinite(original).all() and np.isfinite(new).all()
            delta = original.astype(np.float64) - new.astype(np.float64)
            total_error += float(delta @ delta)
            total_norm += float(original.astype(np.float64) @ original.astype(np.float64))
            maximum = max(maximum, float(np.max(np.abs(delta))))
            changed += int(np.count_nonzero(original.view('<u4') != new.view('<u4')))
            cells += len(original)
            buffers += 1
        arms[str(arm)]['preserved_difference'] = {
            'buffer_pairs': buffers, 'cells': cells, 'changed_cells': changed,
            'relative_l2': (total_error / max(total_norm, 1e-30)) ** .5,
            'maximum_absolute': maximum,
            'scope': 'Final saved pair per input step; repeated replays share a filename.'}
        arms[str(arm)]['median_latency_change_percent'] = 100 * (
            arms[str(arm)]['median_us'] / arms['2']['median_us'] - 1)
    report = {'schema': 'synapse-lie.q2-decode-down-rows-results.v1',
              'source_commit': plan['source_commit'], 'plan_sha256': sha(EVIDENCE / 'plan.json'),
              'binary_sha256': result['binary_sha256'], 'artifact_count': len(collected),
              'raw_artifacts_sha256': collected, 'actual_exit_code': result['exit_code'],
              'full_replays': len(replay), 'exact_replays': sum(r['exact'] for r in replay),
              'oracle_checks': len(oracle), 'oracle_passes': sum(r['pass'] for r in oracle),
              'max_oracle_relative_rms': max(r['relative_rms'] for r in oracle),
              'max_oracle_peak_scaled': max(r['peak_scaled'] for r in oracle),
              'measured': arms, 'all_timings': timing,
              'timer': 'Completed host wall time per native quantizer plus Q2_K down call',
              'release_sha256': sha(EVIDENCE / 'release.json'), 'released_at': release['at'],
              'retired_identities': len(release['retired_identities']),
              'retired_groups': len(release['retired_groups']),
              'decision': 'Retain four rows for model evaluation; eight rows is slower. No model promotion.',
              'limits': ['Small finite differences are real, not an oracle failure.',
                         'Passing operator tolerance establishes neither original-model task quality nor throughput.',
                         'Every timed replay is checked; only final failed buffers per step are saved.'],
              'new_quantization': False, 'model_trial': False, 'goal_met': False}
    with (ROOT / 'config/q2-decode-down-rows-results.json').open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    with (ROOT / 'docs/figures/q2-decode-down-rows-samples.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(timing[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(timing)
    print(json.dumps({k: report[k] for k in ('actual_exit_code', 'full_replays', 'exact_replays',
        'oracle_checks', 'oracle_passes', 'max_oracle_relative_rms', 'measured', 'decision')}))


if __name__ == '__main__':
    main()
