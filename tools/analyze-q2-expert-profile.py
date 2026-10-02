#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a current IQ2 trace and compare diagnostic kernel costs with historical UD."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


def read(root, expected):
    result = json.loads((root / 'results/result.json').read_text())
    if result['state'] != expected or any(c['exit_code'] for c in result['commands']):
        raise ValueError('Incomplete run: ' + str(root))
    if result['models_before'] != result['models_after'] or result['binary_sha256'] != result['binary_sha256_after']:
        raise ValueError('Run identities changed')
    for name, meta in result['artifacts'].items():
        data = (root / 'results' / name).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact differs: ' + name)
    return result


def category(name):
    if 'RoutedF16GEMMKernel<' in name:
        match = re.search(r'WeightType\)(\d+),', name)
        if not match:
            raise ValueError('Unrecognized routed format')
        if int(match[1]) in (10, 7, 8):
            return 'routed_down'
        if int(match[1]) in (12, 13, 16):
            return 'routed_gate_up'
    if 'mul_mat_vec_q_moe<' in name:
        match = re.search(r'ggml_type\)(\d+),', name)
        if match and int(match[1]) in (10, 7, 8):
            return 'routed_down'
        if match and int(match[1]) in (12, 13, 16):
            return 'routed_gate_up'
    if 'DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>' in name:
        return 'hc_down_f16_wmma'
    if 'DenseF16GEMMKernel<128, 128, 1, 4, 2, 8, false, false, false, true>' in name:
        return 'hc_up_f16_wmma'
    if 'W8A8BlockedWmmaGEMMKernel<64, 128, 4, 2, 4, true>' in name:
        return 'hc_down_q8_wmma'
    if 'DenseF16GEMMKernel<256, 128, 1, 4, 2, 8, true,' in name:
        return 'hc_up_q8_fused'
    if 'HcDownF16VecKernel' in name:
        return 'hc_down_f16_gemv'
    if 'qfn_q8_hc_down_kernel' in name:
        return 'hc_down_q8_gemv'
    if 'SmallGemmKernel<' in name and 'WeightType)1,' in name:
        return 'other_f16_gemv'
    if 'mul_mat_vec_q8<' in name:
        return 'q8_dense_gemv'
    if any(part in name for part in ('Quantize', 'quantize_', 'NarrowKernel')):
        return 'explicit_activation_packing'
    return 'other'


def grouped(root):
    raw = json.loads((root / 'results/profile-phases.json').read_text())
    phases = {}
    for phase, data in raw['phases'].items():
        groups = defaultdict(lambda: {'calls': 0, 'ns': 0})
        for kernel in data['kernels']:
            item = groups[category(kernel['kernel'])]
            item['calls'] += kernel['calls']
            item['ns'] += kernel['total_ns']
        assert sum(v['ns'] for v in groups.values()) == data['kernel_sum_ns']
        phases[phase] = {k: v for k, v in data.items() if k != 'kernels'}
        phases[phase]['groups'] = dict(sorted(groups.items(), key=lambda kv: -kv[1]['ns']))
    return phases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--ud-profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', default='iq2_pair', help='Current profile arm name')
    args = parser.parse_args()
    profile = read(args.profile, 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK')
    baseline = read(args.baseline, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    ud = read(args.ud_profile, 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK')
    current = args.profile / 'results'
    ref = args.baseline / 'results'
    checks = []
    for name in ('arithmetic-input.i32', 'counting-input.i32', 'arithmetic-0-prefill.f32',
                 'arithmetic-0-last.f32', 'counting-0-prefill.f32', 'counting-0-last.f32'):
        checks.append({'name': name, 'exact': (current / name).read_bytes() == (ref / name).read_bytes()})
    checks.append({'name': 'profile input', 'exact': (current / 'profile2048-input.i32').read_bytes() ==
                   (ref / 'pp2048-input.i32').read_bytes()})
    for label in ('warm2048', 'profile2048'):
        checks.append({'name': label + ' prefill', 'exact': (current / (label + '-0-prefill.f32')).read_bytes() ==
                       (ref / 'pp2048-0-prefill.f32').read_bytes()})
        out = (current / (label + '-0-output.u32')).read_bytes()
        checks.append({'name': label + ' first16 output', 'exact': len(out) == 16 * 4 and
                       out == (ref / 'pp2048-0-output.u32').read_bytes()[:16 * 4]})
    for suffix in ('prefill.f32', 'last.f32', 'output.u32'):
        checks.append({'name': 'warm/profile ' + suffix,
                       'exact': (current / ('warm2048-0-' + suffix)).read_bytes() ==
                       (current / ('profile2048-0-' + suffix)).read_bytes()})
    report = {'scope': 'Diagnostic marked pp2048/tg16, 15 decode calls; not unprofiled throughput. UD is historical.',
              'baseline_profile_replay': checks, 'profile_numerically_qualified_for_baseline': all(x['exact'] for x in checks),
              'baseline_binary_sha256': baseline['binary_sha256'], 'arms': {}}
    if args.label == 'ud_historical':
        parser.error('Current profile label must differ from the historical control')
    for label, root, result in [(args.label, args.profile, profile), ('ud_historical', args.ud_profile, ud)]:
        trace = root / 'results/profile/q2_results.db'
        report['arms'][label] = {'path': str(root), 'binary_sha256': result['binary_sha256'],
                                'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
                                'command_exits': [c['exit_code'] for c in result['commands']],
                                'phases': grouped(root)}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Baseline numerical replay:', sum(c['exact'] for c in checks), '/', len(checks))
    for label, arm in report['arms'].items():
        for phase, data in arm['phases'].items():
            print(label, phase, 'sum_ms', round(data['kernel_sum_ns'] / 1e6, 3))
            for group, values in data['groups'].items():
                print(group, values['calls'], round(values['ns'] / 1e6, 3))
    if not report['profile_numerically_qualified_for_baseline']:
        raise SystemExit('Profile does not replay the retained baseline')


if __name__ == '__main__':
    main()
