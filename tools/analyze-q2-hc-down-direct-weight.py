#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit HC direct-weight projection/activation/consumer after collection and release."""
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require


def main():
    pp = ROOT / 'config/q2-hc-down-direct-weight-plan.json'
    rp = ROOT / 'config/q2-hc-down-direct-weight-window-release.json'
    plan, release = read(pp), read(rp)
    require(release['state'] == 'Q2_HC_DOWN_DIRECT_WEIGHT_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256'] == sha(pp), 'Window is not released')
    label = plan['components'][0]['label']
    directory = ROOT / 'evidence' / label
    result, transport = curve.artifact_integrity(directory)
    exits = [c['exit_code'] for c in result['commands']]
    require(result['mode'] == transport['mode'] == 'hc-down-direct-weight-check' and
            not result['model_access'] and result.get('finished_at') and
            exits in ([0, 0, 0], [0, 0, 1]) and transport['exit_code'] == exits[-1] and
            result['binary_sha256'] == result['binary_sha256_after'] and
            not result['postflight_kfd'] and result['locks'] == result['postflight_locks'],
            'Component unsafe, incomplete or transport lost')
    collection = read(ROOT / 'evidence/q2-hc-down-direct-weight-runtime-preparation/component-collect-command.json')
    require(collection['exit_code'] == 0 and
            datetime.datetime.fromisoformat(collection['finished_at']) <
            datetime.datetime.fromisoformat(release['at']), 'Collection must precede release')
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                    'Component capsule differs: ' + name)
    data = directory / 'results'
    events = [json.loads(line) for line in (data / '03.log').read_text().splitlines()
              if line.startswith('{')]
    kinds = {kind: [e for e in events if e['event'] == 'hc_direct_' + kind]
             for kind in ('case', 'pair', 'oracle', 'timing', 'complete')}
    require([len(kinds[k]) for k in ('case', 'pair', 'oracle', 'timing', 'complete')] ==
            [4, 160, 160, 14, 1], 'Evidence count differs from frozen component')
    complete = kinds['complete'][0]
    require(complete['safe_completion'] and complete['timing_retained'] and
            not complete['model_inference'] and
            all(c['guards_finite_written'] and c['inputs_unchanged'] for c in kinds['case']),
            'Unsafe outputs or inputs')
    for replay in kinds['pair']:
        require((replay['reference_sha256'] == replay['candidate_sha256']) == replay['exact'],
                'Output hashes disagree with exact replay')
    require(sum(r['case'].startswith('n2048-r') for r in kinds['pair']) == 112,
            'Actual timed destination checks missing')
    numerical = all(r['exact'] for r in kinds['pair']) and all(r['pass'] for r in kinds['oracle'])
    require(complete['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Finite numerical failure or actual exit lost')
    oracle = []
    for candidate in (False, True):
        rows = [o for o in kinds['oracle'] if o['candidate'] == candidate]
        require(len(rows) == 80 and all(o['limit'] == 2e-5 and o['samples'] == 64 for o in rows),
                'Independent oracle contract differs')
        oracle.append(dict(candidate=candidate, checks=len(rows), passing=sum(o['pass'] for o in rows),
            max_relative_rms=max(o['relative_rms'] for o in rows),
            max_scaled_error=max(o['scaled_error'] for o in rows), limit=2e-5))
    arms = []
    for candidate in (False, True):
        rows = [t for t in kinds['timing'] if t['candidate'] == candidate]
        require(len(rows) == 7 and sorted(t['rep'] for t in rows) == list(range(7)) and
                all(t['warmup'] == (t['rep'] < 2) and t['iterations'] == 8 and
                    t['weight_bytes'] == 52428800 and
                    t['order'] == (int(candidate) - t['rep']) % 2 for t in rows),
                'Timing scope or schedule differs')
        wall = [t['completed_wall_us'] for t in rows if not t['warmup']]
        require(all(math.isfinite(v) and v > 0 for v in wall), 'Invalid completed wall timing')
        gpu_valid = all(t['gpu_event_valid'] and t['gpu_event_us'] is not None and
                        math.isfinite(t['gpu_event_us']) and t['gpu_event_us'] > 0 for t in rows)
        arms.append(dict(candidate=candidate, wall_samples_us=wall,
            wall_mean_us=statistics.mean(wall), wall_min_us=min(wall), wall_max_us=max(wall),
            gpu_event_valid=gpu_valid, gpu_event_samples_us=[t['gpu_event_us'] for t in rows],
            gpu_event_mean_us=statistics.mean(t['gpu_event_us'] for t in rows if not t['warmup'])
                if gpu_valid else None))
    report = dict(schema='synapse-lie.q2-hc-down-direct-weight-results.v1', label=label,
        result_sha256=sha(data / 'result.json'), plan_sha256=sha(pp), release_sha256=sha(rp),
        commands=exits, verified_artifacts=len(result['artifacts']), completion=complete,
        full_output_pairs=160, exact_output_pairs=sum(r['exact'] for r in kinds['pair']),
        actual_timed_output_pairs=112, oracle=oracle,
        replays=kinds['pair'], timing_records=kinds['timing'], timing_arms=arms,
        completed_wall_time_change_percent=100 * (arms[1]['wall_mean_us'] / arms[0]['wall_mean_us'] - 1),
        measured_active_occupancy=False,
        aggregation='Arithmetic mean of five completed-wall samples, all raw samples retained; raw HIP events remain separate.',
        retained_model_PP=1587.893545, retained_model_TG=25.12414406,
        fixed_UD_PP=1685.777092, fixed_UD_TG=24.34174251,
        model_inference=False, controls_rebuilt_or_rerun=False, goal_met=False)
    with (ROOT / 'config/q2-hc-down-direct-weight-results.json').open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('commands', 'completion', 'exact_output_pairs',
        'oracle', 'timing_arms', 'completed_wall_time_change_percent', 'goal_met')}))


if __name__ == '__main__':
    main()
