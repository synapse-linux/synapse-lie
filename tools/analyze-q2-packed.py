#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify saved packed-activation operator outputs and exact model replays."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def read(root, expected):
    result = json.loads((root / 'result.json').read_text())
    if result['state'] != expected or any(c['exit_code'] for c in result['commands']):
        raise ValueError('Incomplete run: ' + str(root))
    if result.get('models_before') != result.get('models_after'):
        raise ValueError('Model identity changed')
    if result.get('binary_sha256') != result.get('binary_sha256_after'):
        raise ValueError('Binary identity changed')
    for name, meta in result['artifacts'].items():
        data = (root / name).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact changed: ' + name)
    return result


def exact_files(reference, candidate, names):
    return [{'name': name, 'exact': (reference / name).read_bytes() == (candidate / name).read_bytes()}
            for name in sorted(names)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operators', type=Path, required=True)
    p.add_argument('--iq2-reference', type=Path, required=True)
    p.add_argument('--down-reference', type=Path, required=True)
    p.add_argument('--model-reference', type=Path)
    p.add_argument('--model-candidate', type=Path)
    p.add_argument('--retained-model', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if bool(args.model_reference) != bool(args.model_candidate):
        p.error('Model comparison requires both reference and candidate')
    root = args.operators / 'results'
    state = 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'
    result = read(root, state)
    log = '\n'.join(f.read_text() for f in sorted(root.glob('*.log')))
    errors = re.findall(r'^((?:Q2 routed|IQ2-pair-).*?) rrms=([\deE.+-]+) scaled_max=([\deE.+-]+)$', log, re.M)
    counts = {'independent_down': sum(x[0].startswith('Q2 routed') for x in errors),
              'independent_iq2': sum(x[0].startswith('IQ2-pair-') for x in errors),
              'exact_iq2_packing': len(re.findall(r'^PASS exact packed IQ2 ', log, re.M)),
              'exact_down': len(re.findall(r'^PASS exact packed Q2 down-', log, re.M)),
              'exact_chains': len(re.findall(r'^PASS exact packed Q2 chain-', log, re.M))}
    if list(counts.values()) != [12, 18, 18, 12, 2]:
        raise ValueError('Incomplete operator inventory: ' + str(counts))
    if any(not (0 <= float(a) <= .002 and 0 <= float(b) <= .002) for _, a, b in errors):
        raise ValueError('Independent operator error limit failed')
    replay = []
    for directory, count in ((args.iq2_reference, 18), (args.down_reference, 12)):
        ref = directory / 'results'
        read(ref, state)
        names = [f.name for f in ref.glob('operator-*.f32')]
        if len(names) != count:
            raise ValueError('Unexpected reference inventory')
        replay.extend(exact_files(ref, root, names))
    report = {'scope': 'Packed activation arithmetic replay; independent operators and optional complete saved model outputs. Does not establish task quality.',
              'operators': {'path': str(args.operators), 'counts': counts,
                            'max_rrms': max(float(a) for _, a, _ in errors),
                            'max_scaled_error': max(float(b) for _, _, b in errors),
                            'reference_replay': replay, 'command_exits': [c['exit_code'] for c in result['commands']],
                            'verified_artifacts': len(result['artifacts'])}, 'model_replay': {}}
    if args.model_reference:
        baseline = args.model_reference / 'results'
        candidate = args.model_candidate / 'results'
        state = 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
        read(baseline, state)
        read(candidate, state)
        names = {f.name for f in baseline.iterdir() if f.suffix in ('.f32', '.u32', '.i32')}
        other = {f.name for f in candidate.iterdir() if f.suffix in ('.f32', '.u32', '.i32')}
        if names != other or len(names) != 21:
            raise ValueError('Different or incomplete model inventory')
        report['model_replay']['candidate_vs_fresh_reference'] = exact_files(baseline, candidate, names)
        if args.retained_model:
            retained = args.retained_model / 'results'
            read(retained, state)
            report['model_replay']['fresh_reference_vs_retained'] = exact_files(retained, baseline, names)
    checks = replay + [c for rows in report['model_replay'].values() for c in rows]
    report['all_recorded_replays_exact'] = all(c['exact'] for c in checks)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'operators': counts, 'exact_replays': sum(c['exact'] for c in checks),
                      'total_replays': len(checks), 'all_exact': report['all_recorded_replays_exact']}))
    if not report['all_recorded_replays_exact']:
        raise SystemExit('Numerical replay differs; report retained')


if __name__ == '__main__':
    main()
