#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare retained Q2 frontiers and unprofiled timings; never update goldens."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics

import numpy as np


def load_reader():
    spec = importlib.util.spec_from_file_location('q2_summary', Path(__file__).with_name('analyze-q2.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'ud', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--exact-frontiers', action='store_true',
                        help='Require exact original Q2 bytes under the integer scheduling protocol')
    args = parser.parse_args()
    read = load_reader()
    runs = {name: read(getattr(args, name)) for name in ('baseline', 'candidate', 'ud')}
    baseline, candidate = runs['baseline'][0], runs['candidate'][0]
    protocol_name = 'q2-register-protocol.json' if args.exact_frontiers else 'q2-down-wmma-protocol.json'
    protocol = json.loads((Path(__file__).resolve().parents[1] / 'config' / protocol_name).read_text())
    report = {'scope': 'Bounded Q2 replay, not independent full-model teacher parity',
              'protocol': protocol, 'arms': {name: str(getattr(args, name)) for name in runs},
              'different_token_files': [], 'frontiers': [], 'measurements': []}
    for src in sorted(baseline.iterdir()):
        if src.suffix in ('.i32', '.u32') and src.read_bytes() != (candidate / src.name).read_bytes():
            report['different_token_files'].append(src.name)
        if src.suffix != '.f32':
            continue
        p_logits = np.frombuffer(src.read_bytes(), dtype='<f4').astype(np.float64)
        q_logits = np.frombuffer((candidate / src.name).read_bytes(), dtype='<f4').astype(np.float64)
        if p_logits.shape != q_logits.shape or not p_logits.size:
            raise ValueError('Different frontier geometry: ' + src.name)
        if not np.isfinite(p_logits).all() or not np.isfinite(q_logits).all():
            raise ValueError('Nonfinite frontier: ' + src.name)
        lp = p_logits - p_logits.max()
        lq = q_logits - q_logits.max()
        lp -= np.log(np.exp(lp).sum())
        lq -= np.log(np.exp(lq).sum())
        delta = q_logits - p_logits
        report['frontiers'].append({'name': src.name, 'values': int(p_logits.size),
            'exact': src.read_bytes() == (candidate / src.name).read_bytes(),
            'kl_p_to_candidate': float(np.dot(np.exp(lp), lp - lq)),
            'relative_l2': float(np.linalg.norm(delta) / max(np.linalg.norm(p_logits), 1e-30)),
            'max_absolute_error': float(np.abs(delta).max())})
    for arm, (_, rows, _) in runs.items():
        for size in (512, 2048, 8192):
            selected = [r for r in rows if r['prompt_tokens'] == size and not r['warmup']]
            if len(selected) != 3 or any(r['output_tokens'] != 128 or r['decode_steps'] != 127 or r['eos'] for r in selected):
                raise ValueError('Incomparable token count or timing scope')
            row = {'arm': arm, 'prompt_tokens': size}
            for metric in ('prefill_tok_s', 'decode_steps_s'):
                values = [r[metric] for r in selected]
                row[metric] = {'min': min(values), 'median': statistics.median(values), 'max': max(values)}
            report['measurements'].append(row)
    if args.exact_frontiers:
        numerical_pass = all(r['exact'] for r in report['frontiers'])
    else:
        threshold = protocol['model_screen_gate']['saved_frontier_kl_p_to_candidate_max']
        numerical_pass = all(r['kl_p_to_candidate'] <= threshold for r in report['frontiers'])
    if not report['frontiers']:
        raise ValueError('Missing model frontiers')
    report['bounded_numerical_gate_pass'] = not report['different_token_files'] and numerical_pass
    report['relative_medians'] = {}
    def median(arm, size, metric):
        return next(r[metric]['median'] for r in report['measurements'] if r['arm'] == arm and r['prompt_tokens'] == size)
    for control in ('baseline', 'ud'):
        report['relative_medians'][control] = {str(size): {metric: median('candidate', size, metric) / median(control, size, metric)
            for metric in ('prefill_tok_s', 'decode_steps_s')} for size in (512, 2048, 8192)}
    report['all_medians_at_least_ud'] = all(ratio >= 1 for row in report['relative_medians']['ud'].values() for ratio in row.values())
    report['statistical_limit'] = 'Three samples per shape and noninterleaved arms are not a zero-margin confidence bound.'
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('bounded_numerical_gate_pass', 'different_token_files', 'relative_medians', 'all_medians_at_least_ud')}, indent=2))
    print('Maximum saved-frontier KL:', max(r['kl_p_to_candidate'] for r in report['frontiers']))


if __name__ == '__main__':
    main()
