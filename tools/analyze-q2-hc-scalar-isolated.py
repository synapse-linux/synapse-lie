#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit collected scalar HC component evidence without accessing the GPU."""

import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-hc-scalar-isolated-component-r1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def main():
    artifacts = read('collection-manifest.json')
    require(len(artifacts) == 25, 'Unexpected artifact count')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected artifact differs: ' + name)
    plan, result, release = read('plan.json'), read('result.json'), read('release.json')
    require(sha(EVIDENCE / 'plan.json') ==
            sha(ROOT / 'config/q2-hc-scalar-isolated-plan.json'), 'Plan differs')
    require(sha(EVIDENCE / 'release.json') ==
            'b0f1cf56a67110f0a96bc11679ada484bbe9abce70c5950c1def9d3a4c87f709',
            'Release differs')
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged file differs: ' + name)
    require(result['stdout_sha256'] == sha(EVIDENCE / 'component.stdout') and
            result['stderr_sha256'] == sha(EVIDENCE / 'component.stderr') and
            result['binary_sha256'] == plan['staged_sha256']['q2_hc_scalar_up_mix_check'],
            'Component binding differs')
    require(result['exit_code'] == 0 and result['stop_reason'] is None and
            all(r['exit_code'] == 0 for r in read('preflight-commands.json') + read('run-commands.json')),
            'A runtime command did not pass')
    require(release['component_result_sha256'] == sha(EVIDENCE / 'result.json') and
            release['plan_sha256'] == sha(EVIDENCE / 'plan.json') and
            release['admission_sha256'] == sha(EVIDENCE / 'admission.json') and
            release['kfd'] == [] and release['leases_free'] == 5 and
            release['models_unchanged'] == 7 and not release['gpu_reserved'],
            'Closure differs')
    rows = [json.loads(line) for line in (EVIDENCE / 'component.stdout').read_text().splitlines()]
    pairs = [r for r in rows if r['event'] == 'hc_scalar_pair']
    oracles = [r for r in rows if r['event'] == 'hc_scalar_oracle']
    times = [r for r in rows if r['event'] == 'hc_scalar_timing']
    require(len(pairs) == 64 and all(r['exact'] and r['changed'] == 0 for r in pairs),
            'Complete output replay did not pass')
    require(len(oracles) == 50 and all(r['pass'] and r['limit'] == 2e-5 for r in oracles),
            'Independent oracle did not pass unchanged limits')
    require(rows[-1] == {'event': 'hc_scalar_complete', 'numerical_pass': True,
                        'safe_completion': True, 'model_access': False},
            'Component did not safely complete')
    require(len(times) == 28 and
            len({(r['injection'], r['rep'], r['candidate']) for r in times}) == 28,
            'Timing sample count differs')
    require(all(r['calls'] == 64 and r['distinct_weights_bytes'] == 104857600 and
                r['captured_graph'] and r['warmup'] == (r['rep'] < 2) and
                r['candidate'] == bool(r['order'] ^ (r['rep'] & 1)) and
                r['completed_wall_us'] > 0 for r in times), 'Timing scope differs')
    modes = []
    for injection in (True, False):
        arms = {arm: [r['completed_wall_us'] for r in times
                      if r['injection'] == injection and r['candidate'] == arm
                      and not r['warmup']] for arm in (False, True)}
        require(all(len(v) == 5 for v in arms.values()), 'Measured sample count differs')
        before, after = (statistics.median(arms[arm]) for arm in (False, True))
        modes.append({'injection': injection, 'reference_wall_us': arms[False],
                      'candidate_wall_us': arms[True], 'reference_median_us': before,
                      'candidate_median_us': after,
                      'latency_change_percent': 100 * (after / before - 1),
                      'all_five_pairs_faster': all(a < b for a, b in
                                                  zip(arms[True], arms[False]))})
    report = {
        'schema': 'synapse-lie.q2-hc-scalar-up-mix-results.v1',
        'artifact_hashes': artifacts, 'release_sha256': sha(EVIDENCE / 'release.json'),
        'release_at': release['at'], 'component_exit_code': result['exit_code'],
        'exact_pairs': len(pairs), 'independent_oracle_checks': len(oracles),
        'maximum_oracle_relative_rms': max(r['relative_rms'] for r in oracles),
        'maximum_oracle_peak_scaled_error': max(r['scaled_error'] for r in oracles),
        'invalid_gpu_event_times': sum(not r['gpu_event_valid'] for r in times),
        'completed_wall_is_primary': True, 'modes': modes,
        'eligible_for_original_model_trial': True, 'model_run': False,
        'model_throughput_gain_established': False,
        'inherited_parent_task_quality_qualified': False,
        'peak_cpu_mc': result['peak_cpu_mc'], 'peak_gpu_mc': result['peak_gpu_mc'],
        'retired_identities': len(release['retired_identities']),
        'retired_groups': len(release['retired_groups']),
    }
    (ROOT / 'config/q2-hc-scalar-isolated-results.json').write_text(
        json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (ROOT / 'docs/figures/q2-hc-scalar-isolated-samples.csv').open('w') as out:
        writer = csv.DictWriter(out, fieldnames=list(times[0]))
        writer.writeheader()
        writer.writerows(times)
    print(json.dumps({key: value for key, value in report.items()
                      if key != 'artifact_hashes'}, indent=2))


if __name__ == '__main__':
    main()
