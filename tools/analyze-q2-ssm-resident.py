#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit SSM resident projection/convolution after collection and release."""
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
    pp = ROOT / 'config/q2-ssm-resident-plan.json'
    rp = ROOT / 'config/q2-ssm-resident-window-release.json'
    plan, release = read(pp), read(rp)
    require(release['state'] == 'Q2_SSM_RESIDENT_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256'] == sha(pp), 'Window is not released')
    label = plan['components'][0]['label']
    directory = ROOT / 'evidence' / label
    result, transport = curve.artifact_integrity(directory)
    exits = [c['exit_code'] for c in result['commands']]
    require(result['mode'] == transport['mode'] == 'ssm-resident-check' and
            not result['model_access'] and result.get('finished_at') and
            exits in ([0, 0, 0], [0, 0, 1]) and transport['exit_code'] == exits[-1] and
            result['binary_sha256'] == result['binary_sha256_after'] and
            not result['postflight_kfd'] and result['locks'] == result['postflight_locks'],
            'Component unsafe, incomplete or transport lost')
    collection = read(ROOT / 'evidence/q2-ssm-resident-runtime-preparation/component-collect-command.json')
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
    kinds = {kind: [e for e in events if e['event'] == 'ssm_resident_' + kind]
             for kind in ('case', 'replay', 'oracle', 'timing', 'resources', 'complete')}
    require([len(kinds[k]) for k in ('case', 'replay', 'oracle', 'timing', 'resources', 'complete')] ==
            [5, 72, 144, 14, 2, 1], 'Evidence count differs from frozen component')
    complete = kinds['complete'][0]
    require(complete['safe_completion'] and complete['timing_retained'] and
            not complete['model_inference'] and
            all(c['guards_finite_written'] and c['inputs_unchanged'] for c in kinds['case']),
            'Unsafe outputs or inputs')
    for replay in kinds['replay']:
        require(replay['guards_exact'] and not replay['nonfinite_values'] and
                not replay['unwritten_values'] and not replay['unexpected_unused_values'] and
                replay['exact'] == (replay['changed_values'] == 0), 'Unsafe replay or incorrect exact flag')
        require(replay['reference_sha256'] == replay['candidate_sha256'] if replay['exact'] else
                replay['reference_sha256'] != replay['candidate_sha256'], 'Output hashes disagree with replay')
    require(sum('-timed-' in r['shape'] for r in kinds['replay']) == 42,
            'Actual timed destination comparisons missing')
    numerical = all(r['exact'] for r in kinds['replay']) and all(r['pass'] for r in kinds['oracle'])
    require(complete['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Finite numerical failure or actual exit lost')
    oracle = []
    for arm in ('reference', 'candidate'):
        for field in ('projection', 'convolution'):
            rows = [o for o in kinds['oracle'] if o['arm'] == arm and o['field'] == field]
            require(len(rows) == 36 and all(o['limit'] == .002 and o['samples'] == 24 for o in rows),
                    'Independent oracle contract differs')
            oracle.append(dict(arm=arm, field=field, checks=len(rows), passing=sum(o['pass'] for o in rows),
                max_relative_rms=max(o['relative_rms'] for o in rows),
                max_scaled_error=max(o['scaled_error'] for o in rows), limit=.002))
    arms = []
    for candidate in (False, True):
        rows = [t for t in kinds['timing'] if t['candidate'] == candidate]
        require(len(rows) == 7 and sorted(t['rep'] for t in rows) == list(range(7)) and
                all(t['warmup'] == (t['rep'] < 2) and t['iterations'] == 3 and
                    t['weight_bytes'] == 133693440 and t['tokens'] == 2048 and
                    t['output_rows'] == 16384 and t['inner'] == 2560 and
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
    report = dict(schema='synapse-lie.q2-ssm-resident-results.v1', label=label,
        result_sha256=sha(data / 'result.json'), plan_sha256=sha(pp), release_sha256=sha(rp),
        commands=exits, verified_artifacts=len(result['artifacts']), completion=complete,
        full_output_pairs=72, exact_output_pairs=sum(r['exact'] for r in kinds['replay']),
        actual_timed_output_pairs=42, oracle=oracle, resources=kinds['resources'],
        replays=kinds['replay'], timing_records=kinds['timing'], timing_arms=arms,
        completed_wall_time_change_percent=100 * (arms[1]['wall_mean_us'] / arms[0]['wall_mean_us'] - 1),
        measured_active_occupancy=False,
        aggregation='Arithmetic mean of five completed-wall samples, all raw samples retained; raw HIP events remain separate.',
        retained_model_PP=1587.893545, retained_model_TG=25.12414406,
        fixed_UD_PP=1685.777092, fixed_UD_TG=24.34174251,
        model_inference=False, controls_rebuilt_or_rerun=False, goal_met=False)
    with (ROOT / 'config/q2-ssm-resident-results.json').open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('commands', 'completion', 'exact_output_pairs',
        'oracle', 'resources', 'timing_arms', 'completed_wall_time_change_percent', 'goal_met')}))


if __name__ == '__main__':
    main()
