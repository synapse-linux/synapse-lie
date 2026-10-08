#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit collected HC up outputs and timings after verified GPU release."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import tarfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
sha, read, require = curve.sha, curve.read, curve.require


def main():
    pp = ROOT / 'config/q2-hc-up-short-chain-plan.json'
    rp = ROOT / 'config/q2-hc-up-short-chain-window-release.json'
    plan, release = read(pp), read(rp)
    require(release['state'] == 'Q2_HC_UP_SHORT_CHAIN_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'] and
            release['plan_sha256'] == sha(pp), 'Window is not released')
    label = plan['components'][0]['label']
    directory = ROOT / 'evidence' / label
    result, transport = curve.artifact_integrity(directory)
    exits = [c['exit_code'] for c in result['commands']]
    require(result['mode'] == transport['mode'] == 'hc-up-short-chain-check' and
            not result['model_access'] and result.get('finished_at') and
            exits in ([0, 0, 0], [0, 0, 1]) and transport['exit_code'] == exits[-1] and
            not result['postflight_kfd'] and result['locks'] == result['postflight_locks'],
            'Component unsafe, incomplete or transport lost')
    collection = read(ROOT / 'evidence/q2-hc-up-short-chain-preparation/component-collect-command.json')
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
    kinds = {name: [e for e in events if e['event'] == 'hc_short_' + name]
             for name in ('case', 'pair', 'oracle', 'timing', 'complete')}
    require([len(kinds[k]) for k in ('case', 'pair', 'oracle', 'timing', 'complete')] ==
            [12, 702, 468, 28, 1], 'Component evidence scope differs')
    complete = kinds['complete'][0]
    require(complete['safe_completion'] and complete['all_timings_retained'] and
            not complete['model_inference'] and
            all(c['guards_finite_written'] and c['inputs_unchanged'] for c in kinds['case']),
            'Unsafe outputs or inputs')
    require(complete['exact'] == all(p['exact'] for p in kinds['pair']) and
            complete['independent_pass'] == all(o['pass'] for o in kinds['oracle']) and
            exits[-1] == (0 if complete['exact'] and complete['independent_pass'] else 1),
            'Finite failure exit or completion contract differs')
    saved, half_values, repeated_values = 0, 0, 0
    for case in kinds['case']:
        base = case['label'] + '-r0'
        rows = [p for p in kinds['pair'] if p['label'] == base and p['bank'] == 0]
        require(len(rows) == 3, 'Representative output metadata missing')
        for pair in rows:
            if not pair['enabled']:
                continue
            for arm in ('parent', 'candidate'):
                path = data / (base + '-' + pair['buffer'] + '-' + arm + '.bin')
                require(path.stat().st_size == pair['bytes'] and sha(path) == pair[arm + '_sha256'],
                        'Representative buffer differs')
                require(np.isfinite(np.fromfile(path, dtype='<f2' if pair['buffer'] == 'half' else '<f4')).all(),
                        'Saved buffer is nonfinite')
                saved += 1
        for arm in ('parent', 'candidate'):
            mixed = np.fromfile(data / (base + '-mixed-' + arm + '.bin'), dtype='<f4')
            half_path = data / (base + '-half-' + arm + '.bin')
            if half_path.exists():
                require(mixed.astype('<f2').tobytes() == half_path.read_bytes(),
                        'Saved half conversion differs from its own mixed output')
                half_values += len(mixed)
            if '-p3-' in base:
                matrix = mixed.reshape(-1, 2560)
                require(np.array_equal(matrix, np.broadcast_to(matrix[0], matrix.shape)),
                        'Repeated input rows produced different mixed rows')
                repeated_values += matrix.size
    cases = []
    for deferred in (False, True):
        base = f'hc-short-n2048-p0-d{int(deferred)}-h1-i1'
        arms = []
        for candidate in (False, True):
            rows = [r for r in kinds['timing'] if r['label'] == base and r['candidate'] == candidate]
            require(len(rows) == 7 and sorted(r['rep'] for r in rows) == list(range(7)) and
                    all(r['warmup'] == (r['rep'] < 2) and r['iterations'] == 16 and
                        r['weight_bytes'] == 104857600 and r['order'] == (int(candidate) - r['rep']) % 2
                        for r in rows), 'Timing schedule or cache footprint differs')
            samples = [r['us_per_iteration'] for r in rows if not r['warmup']]
            wall = [r['wall_us_per_iteration'] for r in rows if not r['warmup']]
            require(all(np.isfinite(x) and x > 0 for x in wall), 'Invalid completed wall timing')
            gpu_valid = all(np.isfinite(x) and x > 0 for x in samples)
            arms.append(dict(candidate=candidate, gpu_event_samples_us=samples,
                gpu_event_warmups_us=[r['us_per_iteration'] for r in rows if r['warmup']],
                gpu_event_valid=gpu_valid,
                gpu_event_mean_us=statistics.mean(samples) if gpu_valid else None,
                wall_samples_us=wall, wall_mean_us=statistics.mean(wall),
                wall_min_us=min(wall), wall_max_us=max(wall)))
        cases.append(dict(deferred=deferred, arms=arms,
            gpu_event_time_change_percent=(100 * (arms[1]['gpu_event_mean_us'] /
                arms[0]['gpu_event_mean_us'] - 1)) if all(a['gpu_event_valid'] for a in arms) else None,
            completed_wall_time_change_percent=100 * (arms[1]['wall_mean_us'] / arms[0]['wall_mean_us'] - 1)))
    errors = []
    for candidate in (False, True):
        rows = [r for r in kinds['oracle'] if r['candidate'] == candidate]
        errors.append(dict(candidate=candidate, records=len(rows), passing=sum(r['pass'] for r in rows),
            limit=0.00002, **{k: max(r[k] for r in rows) for k in
                ('mix_rrms', 'mix_scaled_max', 'inject_rrms', 'inject_scaled_max')}))
    pairs = []
    for name in ('mixed', 'half', 'inject'):
        rows = [p for p in kinds['pair'] if p['buffer'] == name and p['enabled']]
        pairs.append(dict(buffer=name, comparisons=len(rows), exact=sum(p['exact'] for p in rows),
            max_abs=max(p['max_abs'] for p in rows), max_relative_l2=max(p['relative_l2'] for p in rows),
            changed_values=sum(p['changed_values'] for p in rows)))
    report = dict(schema='synapse-lie.q2-hc-up-short-chain-results.v1', label=label,
        result_sha256=sha(data / 'result.json'), plan_sha256=sha(pp), release_sha256=sha(rp),
        commands=exits, verified_artifacts=len(result['artifacts']), completion=complete,
        representative_buffers=saved, half_conversion_values=half_values,
        repeated_row_values=repeated_values, oracle=errors, pair_summary=pairs,
        timing_cases=cases, timing_records=kinds['timing'],
        aggregation='Arithmetic means of five measured samples per distinct timer; all raw samples retained. Invalid GPU events remain null for aggregates and are never replaced by wall values.',
        retained_model_PP=1587.893545, retained_model_TG=25.12414406,
        fixed_UD_PP=1685.777092, fixed_UD_TG=24.34174251,
        disposition='Component evidence only; independent model quality and matched original-model timing remain unmeasured.',
        model_inference=False, controls_rebuilt_or_rerun=False, goal_met=False)
    output = ROOT / 'config/q2-hc-up-short-chain-results.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(commands=exits, completion=complete, oracle=errors,
                         pair_summary=pairs, timing_cases=cases, goal_met=False)))


if __name__ == '__main__':
    main()
