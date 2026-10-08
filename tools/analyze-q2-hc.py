#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Report measured HC diagnostics without promoting a numerical candidate."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np


def read(path, state, partial=False):
    root = path / 'results'
    result = json.loads((root / 'result.json').read_text())
    complete = result['state'] == state and not any(c['exit_code'] for c in result['commands'])
    if not complete:
        if not (partial and result['state'] == 'FAILED' and result.get('thermal_stop')
                and result.get('model_access') and result['commands'][-1]['exit_code'] == -15
                and not any(c['exit_code'] for c in result['commands'][:-1])):
            raise ValueError('Incomplete arm: ' + str(path))
    for name, meta in result['artifacts'].items():
        data = (root / name).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact changed: ' + name)
    events = []
    for log in sorted(root.glob('*.log')):
        events.extend(json.loads(line) for line in log.read_text().splitlines()
                      if line.startswith('{'))
    temperatures = {}
    for line in (root / 'telemetry.jsonl').read_text().splitlines():
        for sensor in json.loads(line).get('thermal', []):
            name = sensor['device']
            temperatures[name] = max(temperatures.get(name, -100000), sensor['temperature_mc'])
    command = result['commands'][-1]
    wall = (datetime.datetime.fromisoformat(command['finished_at']) -
            datetime.datetime.fromisoformat(command['started_at'])).total_seconds()
    return root, events, {'path': str(path), 'binary_sha256': result['binary_sha256'],
                          'complete': complete, 'runner_state': result['state'],
                          'thermal_stop': result.get('thermal_stop'),
                          'command_wall_s': wall, 'mmq_reuse': result.get('mmq_reuse'),
                          'thermal_max_mc': temperatures, 'finished_at': result['finished_at']}


def stats(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values), samples=values)


def frontiers(a, b, logits=False, subset=False):
    rows = []
    left, right = ({p.name for p in root.glob('*.f32')} for root in (a, b))
    if not right or (not right.issubset(left) if subset else left != right):
        raise ValueError('Different frontier inventory')
    for name in sorted(right):
        raw_p, raw_q = (a / name).read_bytes(), (b / name).read_bytes()
        p, q = (np.frombuffer(v, dtype='<f4').astype(np.float64) for v in (raw_p, raw_q))
        if p.shape != q.shape or not p.size or not np.isfinite(p).all() or not np.isfinite(q).all():
            raise ValueError('Invalid frontier: ' + name)
        delta = q - p
        row = {'name': name, 'exact': raw_p == raw_q,
               'max_absolute_delta': float(np.abs(delta).max()),
               'relative_l2': float(np.linalg.norm(delta) / max(np.linalg.norm(p), 1e-60))}
        if logits:
            lp, lq = p - p.max(), q - q.max()
            lp -= np.log(np.exp(lp).sum())
            lq -= np.log(np.exp(lq).sum())
            row['kl_p_to_candidate'] = float(np.dot(np.exp(lp), lp - lq))
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--models', nargs=3, type=Path, metavar=('Q2', 'HC', 'UD'))
    parser.add_argument('--partial-reference', action='store_true',
                        help='Explicitly report a thermally interrupted reference; never claim a completed comparison')
    parser.add_argument('--frontier-reference', type=Path,
                        help='Completed qualified Q2 arm for numerical replay when the fresh reference is partial')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.partial_reference and (not args.models or not args.frontier_reference):
        parser.error('Partial reference requires model arms and a completed numerical reference')
    report = {'scope': 'HC component exploration; full Q2/UD PP and TG parity remains required',
              'promotion': False, 'micro': {}, 'model': {}}
    runs = []
    for label, path in [('reference', args.reference), ('candidate', args.candidate)]:
        root, events, meta = read(path, 'SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT')
        operators = [r for r in events if r.get('event') == 'operator']
        samples = [r for r in events if r.get('event') == 'microbench']
        if len(operators) != 11 or len(samples) != 5 or any(
                r['matrices'] != 16 or r['launches'] != 128 for r in samples):
            raise ValueError('Unexpected HC diagnostic scope')
        report['micro'][label] = dict(meta, operators=operators,
                                      us_per_launch=stats([r['us_per_launch'] for r in samples]))
        runs.append(root)
    report['micro']['frontiers'] = frontiers(*runs)
    report['micro']['speedup'] = (report['micro']['reference']['us_per_launch']['median'] /
                                  report['micro']['candidate']['us_per_launch']['median'])
    if args.models:
        runs = []
        for label, path in zip(('reference', 'candidate', 'ud'), args.models):
            partial = args.partial_reference and label == 'reference'
            root, events, meta = read(path, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT', partial)
            samples = [r for r in events if r.get('event') == 'sample' and r['label'] == 'pp2048']
            cooldowns = [r for r in events if r.get('event') == 'cooldown']
            if len(cooldowns) != 4 or any(r['seconds'] != 15 or r['before_rep'] != i
                                         for i, r in enumerate(cooldowns)):
                raise ValueError('Unmatched model cooldown protocol')
            if (len(samples) != 4 if meta['complete'] else not 2 <= len(samples) < 4) or sum(r['warmup'] for r in samples) != 1 or any(
                    r['prompt_tokens'] != 2048 or r['decode_steps'] != 127 or
                    r['output_tokens'] != 128 or r['eos'] for r in samples):
                raise ValueError('Incomparable model timing scope')
            report['model'][label] = dict(meta, measured_samples=len(samples)-1, measurements={key: stats([
                r[key] for r in samples if not r['warmup']]) for key in
                ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')})
            runs.append(root)
        numerical_root = runs[0]
        if args.frontier_reference:
            numerical_root, _, numerical_meta = read(args.frontier_reference, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
            report['model']['historical_numerical_reference'] = numerical_meta
            fresh_files = [p for p in runs[0].iterdir() if p.suffix in ('.i32', '.u32', '.f32')]
            if any(p.read_bytes() != (numerical_root / p.name).read_bytes() for p in fresh_files):
                raise ValueError('Fresh Q2 reference differs from qualified numerical replay')
            report['model']['fresh_reference_files_exact_to_historical'] = len(fresh_files)
        report['model']['frontiers'] = frontiers(numerical_root, runs[1], logits=True, subset=bool(args.frontier_reference))
        token_files = sorted(p.name for p in runs[1].iterdir() if p.suffix in ('.i32', '.u32'))
        report['model']['token_files'] = token_files
        report['model']['changed_tokens'] = [name for name in token_files
            if (numerical_root / name).read_bytes() != (runs[1] / name).read_bytes()]
        report['model']['comparison_complete'] = all(report['model'][arm]['complete'] for arm in ('reference', 'candidate', 'ud'))
        report['model']['relative_medians'] = {control: {key:
            report['model']['candidate']['measurements'][key]['median'] /
            report['model'][control]['measurements'][key]['median']
            for key in ('prefill_tok_s', 'decode_steps_s')} for control in ('reference', 'ud')}
        report['model']['limit'] = 'Measured isolated requests with explicit sample counts; 15s idle before warmup/each request excluded from PP/TG but included in command wall. A partial reference retains FAILED and cannot establish a completed comparison. Sequential arms; no sustained-serving, statistical parity or long-context qualification.'
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'micro_speedup': report['micro']['speedup'],
                       'model_relative_medians': report['model'].get('relative_medians')}, indent=2))


if __name__ == '__main__':
    main()
