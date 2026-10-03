#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare completed original Terminal-Bench exports without rewriting scores."""
import argparse
import csv
import json
from pathlib import Path


def read_arm(path, tasks):
    summary = json.loads((path / 'summary.json').read_text())
    if summary['suite']['id'] != 'core19' or summary['quant'] != 'Q2':
        raise ValueError('Unexpected suite or quantization')
    rows = {}
    for name in summary['results']:
        if Path(name).name != name:
            raise ValueError('Unsafe result filename')
        result = json.loads((path / name).read_text())
        task = result['task']
        if task not in tasks or task in rows or not result['completed']:
            raise ValueError('Unexpected, repeated or incomplete task')
        attempts = result['attempts']
        if [x['attempt'] for x in attempts] not in ([1], [1, 2]):
            raise ValueError('Different attempt policy')
        if len(attempts) == 1 and attempts[0]['reward'] != 1:
            raise ValueError('Conditional second attempt is still missing')
        if len(attempts) == 2 and attempts[0]['reward'] == 1:
            raise ValueError('Successful first attempt was repeated')
        passed = any(x['reward'] == 1 for x in attempts)
        if passed != result['passed']:
            raise ValueError('Exported pass flag disagrees with exact reward')
        rows[task] = {
            'pass_at_1': attempts[0]['reward'] == 1, 'pass_at_2': passed,
            'attempts': [{'attempt': x['attempt'], 'reward': x['reward'],
                          'exception': x.get('exception'), 'duration_ms': x['duration_ms'],
                          'tokens': x.get('tokens'), 'transcript': x.get('transcript')}
                         for x in attempts],
            'profile': result['evaluation_profile'],
            'provenance': result['task_provenance'],
        }
    if set(rows) != set(tasks) or summary['total_tasks'] != len(tasks):
        raise ValueError('The complete selected denominator is required')
    if summary['passed_tasks'] != sum(x['pass_at_2'] for x in rows.values()):
        raise ValueError('Aggregate disagrees with task rewards')
    return {'path': str(path), 'tasks': rows,
            'pass_at_1': sum(x['pass_at_1'] for x in rows.values()),
            'pass_at_2': sum(x['pass_at_2'] for x in rows.values()),
            'denominator': len(tasks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('qualified', type=Path)
    parser.add_argument('retained', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--tier', choices=['smoke', 'full'], default='full')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parents[1] /
                       'config/q2-terminal-bench-plan.json').read_text())
    tasks = plan['tiers'][args.tier]
    arms = {name: read_arm(getattr(args, name), tasks)
            for name in ['qualified', 'retained', 'candidate']}
    matrix = []
    for task in tasks:
        expected = None
        for name, arm in arms.items():
            profile = dict(arm['tasks'][task]['profile'])
            profile.pop('tag', None)  # Arm label only; no behavior field is ignored.
            identity = (profile, arm['tasks'][task]['provenance'])
            if expected is not None and identity != expected:
                raise ValueError('Mismatched task/agent/serving protocol: ' + task)
            expected = identity
        matrix.append({'task': task, **{
            name + '_' + metric: arm['tasks'][task][metric]
            for name, arm in arms.items() for metric in ['pass_at_1', 'pass_at_2']}})
    pairs = {}
    for baseline in ['qualified', 'retained']:
        pairs[baseline] = {}
        for metric in ['pass_at_1', 'pass_at_2']:
            pairs[baseline][metric] = {
                'baseline_only': [t for t in tasks if arms[baseline]['tasks'][t][metric]
                                  and not arms['candidate']['tasks'][t][metric]],
                'candidate_only': [t for t in tasks if arms['candidate']['tasks'][t][metric]
                                   and not arms[baseline]['tasks'][t][metric]],
            }
    report = {'scope': 'Completed paired real-task results; no numerical-equivalence proof',
              'tier': args.tier, 'arms': arms, 'paired_outcomes': pairs, 'matrix': matrix,
              'numerical_gates_waived': False, 'promoted': False, 'goal_met': False}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matrix[0]))
        writer.writeheader()
        writer.writerows(matrix)
    print(json.dumps({name: {k: arm[k] for k in ['pass_at_1', 'pass_at_2', 'denominator']}
                      for name, arm in arms.items()}))


if __name__ == '__main__':
    main()
