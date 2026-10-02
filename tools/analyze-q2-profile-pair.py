#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare fresh marked Q2/UD traces and replay each against its own model arm."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'expert_profile', Path(__file__).with_name('analyze-q2-expert-profile.py'))
expert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(expert)


def replay(profile, baseline):
    current, reference = profile / 'results', baseline / 'results'
    rows = []

    def check(name, left, right):
        rows.append(dict(name=name, exact=left == right))

    for name in ('arithmetic-input.i32', 'counting-input.i32',
                 'arithmetic-0-prefill.f32', 'arithmetic-0-last.f32',
                 'counting-0-prefill.f32', 'counting-0-last.f32'):
        check(name, (current / name).read_bytes(), (reference / name).read_bytes())
    check('profile input', (current / 'profile2048-input.i32').read_bytes(),
          (reference / 'pp2048-input.i32').read_bytes())
    for label in ('warm2048', 'profile2048'):
        check(label + ' prefill', (current / (label + '-0-prefill.f32')).read_bytes(),
              (reference / 'pp2048-0-prefill.f32').read_bytes())
        output = (current / (label + '-0-output.u32')).read_bytes()
        check(label + ' first16 output', output,
              (reference / 'pp2048-0-output.u32').read_bytes()[:64])
        if len(output) != 64:
            raise ValueError('Unexpected profiled output length')
    for suffix in ('prefill.f32', 'last.f32', 'output.u32'):
        check('warm/profile ' + suffix,
              (current / ('warm2048-0-' + suffix)).read_bytes(),
              (current / ('profile2048-0-' + suffix)).read_bytes())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('q2', 'ud', 'q2-baseline', 'ud-baseline', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    report = dict(scope='Fresh sequential diagnostic pp2048/tg16 traces with 15 decode calls; '
                        'kernel sums include profiler overhead and are not request throughput',
                  goal_met=False, promotion=False, arms={}, phase_deltas={})
    aliases = {'hc_down_f16_wmma': 'hc_down_projection',
               'hc_down_q8_wmma': 'hc_down_projection',
               'hc_down_f16_gemv': 'hc_down_projection',
               'hc_down_q8_gemv': 'hc_down_projection',
               'hc_up_f16_wmma': 'hc_up_projection',
               'hc_up_f16_fused': 'hc_up_projection',
               'hc_up_q8_fused': 'hc_up_projection'}
    for label in ('q2', 'ud'):
        directory = getattr(args, label)
        baseline = getattr(args, label + '_baseline')
        run = expert.read(directory, 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK')
        control = expert.read(baseline, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        if run['models_before'] != control['models_before']:
            raise ValueError('Different model identity for numerical control')
        checks = replay(directory, baseline)
        phases = expert.grouped(directory)
        for phase in phases.values():
            groups = {}
            for name, values in phase['groups'].items():
                group = groups.setdefault(aliases.get(name, name), dict(calls=0, ns=0))
                group['calls'] += values['calls']
                group['ns'] += values['ns']
            phase['comparison_groups'] = groups
            if sum(g['ns'] for g in groups.values()) != phase['kernel_sum_ns']:
                raise ValueError('Incomplete grouped kernel accounting')
        report['arms'][label] = dict(path=str(directory), baseline=str(baseline),
            binary_sha256=run['binary_sha256'], replay=checks,
            exact_replay=all(x['exact'] for x in checks), phases=phases,
            trace_sha256=hashlib.sha256(
                (directory / 'results/profile/q2_results.db').read_bytes()).hexdigest())
    for phase in ('prefill', 'decode'):
        q2, ud = (report['arms'][label]['phases'][phase] for label in ('q2', 'ud'))
        groups = set(q2['comparison_groups']) | set(ud['comparison_groups'])
        rows = [dict(group=name,
                     q2_ns=q2['comparison_groups'].get(name, {}).get('ns', 0),
                     ud_ns=ud['comparison_groups'].get(name, {}).get('ns', 0))
                for name in sorted(groups)]
        for row in rows:
            row['delta_ns'] = row['q2_ns'] - row['ud_ns']
        delta = q2['kernel_sum_ns'] - ud['kernel_sum_ns']
        if sum(r['delta_ns'] for r in rows) != delta:
            raise ValueError('Grouped deltas do not reconcile')
        report['phase_deltas'][phase] = dict(kernel_sum_delta_ns=delta,
            groups=sorted(rows, key=lambda r: -r['delta_ns']))
    report['grouping_limit'] = ('Only recognized projection families are grouped; library/fallback '
                               'projections remain in other. Decode Q8 dense includes HC up.')
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({phase: data for phase, data in report['phase_deltas'].items()}, indent=2))
    if not all(arm['exact_replay'] for arm in report['arms'].values()):
        raise SystemExit('Profile differs from its unprofiled model control; report retained')


if __name__ == '__main__':
    main()
