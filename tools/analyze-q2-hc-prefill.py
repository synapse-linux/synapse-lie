#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Summarize isolated F16 HC prefill operators and matched model samples."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

import importlib.util
spec = importlib.util.spec_from_file_location('hc_analysis', Path(__file__).with_name('analyze-q2-hc.py'))
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def read_micro(path):
    root = path / 'results'
    receipt = json.loads((root / 'result.json').read_text())
    for name, meta in receipt['artifacts'].items():
        data = (root / name).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact changed: ' + name)
    events = [json.loads(line) for p in sorted(root.glob('*.log'))
              for line in p.read_text().splitlines() if line.startswith('{')]
    summaries = [e for e in events if e.get('event') == 'pp_operator_summary']
    if len(summaries) != 1 or summaries[0]['cases'] != 22:
        raise ValueError('Missing complete operator summary')
    failures = summaries[0]['numerical_failures']
    expected = 'FAILED' if failures else 'SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
    if (receipt['state'] != expected or receipt.get('thermal_stop') or
            any(c['exit_code'] for c in receipt['commands'][:-1]) or
            receipt['commands'][-1]['exit_code'] != int(bool(failures)) or
            receipt['binary_sha256'] != receipt['binary_sha256_after']):
        raise ValueError('Incomplete, changed or unexpected failed micro arm')
    temperatures = {}
    for line in (root / 'telemetry.jsonl').read_text().splitlines():
        for sensor in json.loads(line)['thermal']:
            name = sensor['device']
            temperatures[name] = max(temperatures.get(name, -100000), sensor['temperature_mc'])
    command = receipt['commands'][-1]
    wall = (datetime.datetime.fromisoformat(command['finished_at']) -
            datetime.datetime.fromisoformat(command['started_at'])).total_seconds()
    return root, events, {'path': str(path), 'binary_sha256': receipt['binary_sha256'],
        'runner_state': receipt['state'], 'numerical_failures': failures,
        'performance_samples_complete': True, 'command_exit': command['exit_code'],
        'thermal_max_mc': temperatures, 'command_wall_s': wall}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--models', nargs=2, type=Path, metavar=('HC', 'HC_PP'))
    parser.add_argument('--ud', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'scope': 'HC prefill component; Q2/UD PP and TG parity remains the goal',
              'promotion': False, 'micro': {}, 'model': {}}
    roots = []
    for label, path in [('reference', args.reference), ('candidate', args.candidate)]:
        root, events, meta = read_micro(path)
        operators = [e for e in events if e.get('event') == 'pp_operator']
        samples = [e for e in events if e.get('event') == 'pp_microbench']
        if len(operators) != 22 or len(samples) != 10 or sum(
                e['relative_rms'] > 2e-5 or e['error_over_peak'] > 2e-5 for e in operators) != meta['numerical_failures']:
            raise ValueError('Incomplete or inconsistent predeclared operators')
        if any(e['n'] != 2048 or e['matrices'] != 16 or e['launches'] != 16 for e in samples):
            raise ValueError('Changed microbenchmark scope')
        shapes = {}
        for m, k in [(320, 10240), (10240, 320)]:
            rows = [e for e in samples if e['m'] == m and e['k'] == k]
            if sorted(e['rep'] for e in rows) != list(range(5)):
                raise ValueError('Incomplete repetitions')
            shapes[f'{m}x{k}'] = {key: hc.stats([e[key] for e in rows])
                                   for key in ('us_per_launch', 'tflops')}
        report['micro'][label] = dict(meta, operators=operators, shapes=shapes)
        roots.append(root)
    ref, candidate = (report['micro'][arm] for arm in ('reference', 'candidate'))
    report['micro']['speedups'] = {shape: ref['shapes'][shape]['us_per_launch']['median'] /
        candidate['shapes'][shape]['us_per_launch']['median'] for shape in ref['shapes']}
    report['micro']['sample_differences'] = hc.frontiers(*roots)
    hashes = {r['label']: r['full_output_sha256'] for r in ref['operators']}
    if set(hashes) != {r['label'] for r in candidate['operators']}:
        raise ValueError('Operator inventory differs')
    report['micro']['changed_full_output_hashes'] = [r['label'] for r in candidate['operators']
        if hashes[r['label']] != r['full_output_sha256']]
    for p in roots[0].glob('*.u32'):
        if p.read_bytes() != (roots[1] / p.name).read_bytes():
            raise ValueError('Sampled oracle coordinates differ')
    if args.models:
        arms = list(zip(('reference', 'candidate'), args.models))
        if args.ud:
            arms.append(('ud', args.ud))
        model_roots = []
        for label, path in arms:
            root, events, meta = hc.read(path, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
            samples = [e for e in events if e.get('event') == 'sample' and e['label'] == 'pp2048']
            idle = [e for e in events if e.get('event') == 'cooldown']
            if len(idle) != 4 or any(e['seconds'] != 15 or e['before_rep'] != i for i, e in enumerate(idle)):
                raise ValueError('Different idle protocol')
            if len(samples) != 4 or sum(e['warmup'] for e in samples) != 1 or any(
                    e['prompt_tokens'] != 2048 or e['decode_steps'] != 127 or
                    e['output_tokens'] != 128 or e['eos'] for e in samples):
                raise ValueError('Incomplete or changed model timing scope')
            report['model'][label] = dict(meta, measurements={key: hc.stats([
                e[key] for e in samples if not e['warmup']]) for key in
                ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')})
            model_roots.append(root)
        report['model']['within_arm_replay'] = {}
        for (label, _), root in zip(arms, model_roots):
            checks = [((root / f'pp2048-0-{suffix}').read_bytes() ==
                       (root / f'pp2048-{rep}-{suffix}').read_bytes())
                      for suffix in ('prefill.f32', 'last.f32', 'output.u32')
                      for rep in (1, 2, 3)]
            report['model']['within_arm_replay'][label] = {'checks': len(checks), 'exact': sum(checks)}
        report['model']['frontiers'] = hc.frontiers(*model_roots[:2], logits=True)
        names = sorted(p.name for p in model_roots[0].iterdir() if p.suffix in ('.i32', '.u32'))
        report['model']['token_files'] = names
        report['model']['changed_tokens'] = [name for name in names if
            (model_roots[0] / name).read_bytes() != (model_roots[1] / name).read_bytes()]
        report['model']['relative_medians'] = {label: {key:
            report['model']['candidate']['measurements'][key]['median'] /
            report['model'][label]['measurements'][key]['median']
            for key in ('prefill_tok_s', 'decode_steps_s')}
            for label in ('reference', 'ud') if label in report['model']}
        report['model']['limit'] = 'Sequential C1 2K/128 with15s idle outside timing; no continuous serving, long context or quality qualification. Historical UD arm, if supplied, is labeled by path/time.'
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'micro_speedups': report['micro']['speedups'],
                      'model_relative_medians': report['model'].get('relative_medians')}, indent=2))


if __name__ == '__main__':
    main()
