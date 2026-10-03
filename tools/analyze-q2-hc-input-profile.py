#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute HC input-fusion cost with fresh marked traces and model replay."""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('profile_pair', Path(__file__).with_name('analyze-q2-profile-pair.py'))
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)


def group(name):
    if 'NarrowKernel<__half>' in name:
        return 'activation_narrowing'
    if ('DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>' in name or
            'DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true,' in name):
        return 'hc_down'
    if ('DenseF16GEMMKernel<128, 64, 1, 4, 2, 8, true, false, false, true>' in name or
            'DenseF16GEMMKernel<128, 64, 1, 4, 2, 8, true, false, false, true,' in name):
        return 'hc_up'
    if 'HcCombineMoeF32Kernel' in name or 'HcCombineVec4Kernel<float>' in name:
        return 'hc_combine'
    if 'RoutedF16GEMMKernel<' in name:
        return 'routed_experts'
    return 'other'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'reference-model', 'candidate-model', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = dict(scope='Fresh diagnostic pp2048/tg16 kernel profiles; not unprofiled request rates',
                  goal_met=False, promotion=False, arms={})
    for label in ('reference', 'candidate'):
        path, baseline = getattr(args, label), getattr(args, label + '_model')
        result = pair.expert.read(path, 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK')
        model = pair.expert.read(baseline, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        if result['models_before'] != model['models_before']:
            raise ValueError('Model witness differs')
        replay = pair.replay(path, baseline)
        if not all(row['exact'] for row in replay):
            raise ValueError('Profile does not replay its unprofiled model')
        phases = json.loads((path / 'results/profile-phases.json').read_text())['phases']
        for phase in phases.values():
            groups = defaultdict(lambda:dict(calls=0, ns=0))
            for kernel in phase['kernels']:
                entry = groups[group(kernel['kernel'])]
                entry['calls'] += kernel['calls']
                entry['ns'] += kernel['total_ns']
            if sum(row['ns'] for row in groups.values()) != phase['kernel_sum_ns']:
                raise ValueError('Kernel attribution does not reconcile')
            phase['groups'] = dict(groups)
        report['arms'][label] = dict(path=str(path), baseline=str(baseline), replay=replay,
            binary_sha256=result['binary_sha256'], phases=phases,
            trace_sha256=hashlib.sha256((path / 'results/profile/q2_results.db').read_bytes()).hexdigest())
    report['deltas'] = {}
    for phase in ('prefill', 'decode'):
        a, b = (report['arms'][arm]['phases'][phase] for arm in ('reference', 'candidate'))
        groups = sorted(set(a['groups']) | set(b['groups']))
        rows = [dict(group=name, reference=a['groups'].get(name, dict(calls=0, ns=0)),
                     candidate=b['groups'].get(name, dict(calls=0, ns=0))) for name in groups]
        for row in rows:
            row['delta_ns'] = row['candidate']['ns'] - row['reference']['ns']
        total = b['kernel_sum_ns'] - a['kernel_sum_ns']
        if sum(row['delta_ns'] for row in rows) != total:
            raise ValueError('Phase attribution does not reconcile')
        report['deltas'][phase] = dict(kernel_sum_delta_ns=total, groups=rows)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['deltas'], indent=2))


if __name__ == '__main__':
    main()
