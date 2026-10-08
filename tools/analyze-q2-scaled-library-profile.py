#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute the composed Q2/UD traces while retaining complete replay evidence."""
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


pair = module('analyze-q2-profile-pair.py')
audit = module('analyze-q2-combined.py')
require = audit.require


def category(name, hc_library):
    if name in hc_library:
        return 'hc_down_projection'
    group = pair.expert.category(name)
    if group.startswith('hc_down_'):
        return 'hc_down_projection'
    if group.startswith('hc_up_'):
        return 'hc_up_projection'
    if 'PackQ2ScaledRowsKernel' in name:
        return 'explicit_activation_packing'
    if group != 'other':
        return group
    if 'HcCombineMoe' in name:
        return 'moe_hc_combine'
    if 'HcCombine' in name:
        return 'hc_combine'
    if 'HcMixEpilogue' in name:
        return 'hc_mix_epilogues'
    if 'WmmaCausalAttentionKernel' in name:
        return 'causal_attention'
    if 'Gdn' in name:
        return 'gdn_recurrence_and_epilogues'
    dense = re.search(r'DenseF16GEMMKernel<([^<>]+)>', name)
    if dense:
        args = [p.strip() for p in dense[1].split(',')]
        if len(args) >= 9 and args[7] == 'true':
            return 'gdn_projection_convolution'
        if len(args) >= 9 and args[8] == 'true':
            return 'attention_projection'
        return 'other_dense_wmma'
    return 'other'


def main():
    arms, validations = {}, {}
    fixtures = ['CMakeLists.txt', 'cmake/hip/CMakeLists.txt',
                'config/models-157.inventory.json', 'tests/q2_model.cpp',
                'tests/q2_profile_markers.hip', 'tools/q2-runner.py',
                'tools/q2_thermal.py', 'tools/q2_process.py', 'tools/q2_reuse.py',
                'tools/analyze-q2-profile.py', 'tools/q2-resource-report.py']
    for suffix in ('profile-host-r1', 'profile-host-r2', 'profile-r1', 'ud-profile-r1'):
        label = 'q2-scaled-library-' + suffix
        path = ROOT / 'evidence' / label
        receipt = json.loads((path / 'results/result.json').read_text())
        transport = json.loads((path / 'transport.json').read_text())
        count = 6 if receipt['mode'] == 'cpu' else 7
        require([c['exit_code'] for c in receipt['commands']] == [0] * count and
                transport['exit_code'] == 0 and not receipt.get('thermal_stop'), 'Run did not complete')
        for name, meta in receipt['artifacts'].items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
            file = path / 'results' / name
            require(file.stat().st_size == meta['bytes'] and audit.digest(file) == meta['sha256'],
                    'Changed artifact: ' + name)
        if receipt['mode'] != 'cpu':
            require(receipt['locks'] == receipt['postflight_locks'] and
                    [(x['device'], x['inode']) for x in receipt['locks']] ==
                    [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)] and
                    not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Invalid admission')
        # The first host cohort predates the corrected launcher guards.
        guards = [] if suffix == 'profile-host-r1' else ['tools/q2-remote.py', 'tests/q2_remote_test.py']
        validations[label] = dict(audit.audit_capsule(path, fixtures + guards),
                                 command_exits=[c['exit_code'] for c in receipt['commands']],
                                 state=receipt['state'], earlier_guard_version=not guards)

    library_names = set()
    for arm, label, baseline, variant in (
            ('q2', 'q2-scaled-library-profile-r1', 'q2-scaled-library-model-candidate-r1', 'scaled-library'),
            ('ud', 'q2-scaled-library-ud-profile-r1', 'q2-scaled-library-model-ud-r1', 'qualified')):
        path, control = ROOT / 'evidence' / label, ROOT / 'evidence' / baseline
        r = pair.expert.read(path, 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK')
        b = pair.expert.read(control, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        t = json.loads((path / 'transport.json').read_text())
        require(t['source_variant'] == variant and not r.get('mmq_reuse') and
                r['models_before'] == b['models_before'], 'Profile source/model changed')
        require('qfn_mmq.hip.cpp' in (path / 'results/02.log').read_text(), 'Missing full MMQ compilation')
        checks = pair.replay(path, control)
        require(all(c['exact'] for c in checks), 'Profile differs from its unprofiled control')
        raw = json.loads((path / 'results/profile-phases.json').read_text())
        if arm == 'q2':
            library = [k for k in raw['phases']['prefill']['kernels'] if k['kernel'].startswith(
                'Cijk_Alik_Bljk_HSS_BH_Bias_HA_S_SAV_UserArgs_MT96x32x32_MI16x16x1_')]
            require(len(library) == 1 and library[0]['calls'] == 96, 'Unexpected HC-library dispatch')
            library_names.add(library[0]['kernel'])
        phases = {}
        for phase, data in raw['phases'].items():
            groups = defaultdict(lambda: dict(calls=0, ns=0))
            for row in data['kernels']:
                g = groups[category(row['kernel'], library_names)]
                g['calls'] += row['calls']
                g['ns'] += row['total_ns']
            require(sum(g['ns'] for g in groups.values()) == data['kernel_sum_ns'] and
                    sum(g['calls'] for g in groups.values()) == data['dispatches'], 'Incomplete accounting')
            phases[phase] = dict(data, groups=dict(groups))
        arms[arm] = dict(path=str(path.relative_to(ROOT)), baseline=baseline,
                         finished_at=r['finished_at'], binary_sha256=r['binary_sha256'],
                         trace_sha256=audit.digest(path / 'results/profile/q2_results.db'),
                         replay=checks, phases=phases)

    deltas = {}
    for phase in ('prefill', 'decode'):
        q2, ud = (arms[n]['phases'][phase] for n in ('q2', 'ud'))
        groups = set(q2['groups']) | set(ud['groups'])
        rows = [dict(group=g, q2_ns=q2['groups'].get(g, {}).get('ns', 0),
                     ud_ns=ud['groups'].get(g, {}).get('ns', 0),
                     q2_calls=q2['groups'].get(g, {}).get('calls', 0),
                     ud_calls=ud['groups'].get(g, {}).get('calls', 0)) for g in groups]
        for row in rows:
            row['delta_ns'] = row['q2_ns'] - row['ud_ns']
        delta = q2['kernel_sum_ns'] - ud['kernel_sum_ns']
        require(sum(r['delta_ns'] for r in rows) == delta, 'Deltas do not reconcile')
        deltas[phase] = dict(kernel_sum_delta_ns=delta, groups=sorted(rows, key=lambda r: -r['delta_ns']))
    report = dict(scope='Marked pp2048/tg16 diagnostic, 15 decode calls; sequential profiles, not throughput',
                  arms=arms, deltas=deltas, validation=validations, hc_library_symbols=sorted(library_names),
                  grouping_limit='HC-library attribution uses its unique measured symbol, 96 calls and isolated M320/K10240/n2048 source dispatch; other kernels remain explicitly grouped or other',
                  goal_met=False, promoted=False, numerical_policy='Replay validates instrumentation only; inherited operator and KL failures remain')
    (ROOT / 'config/q2-scaled-library-profile-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(deltas['prefill'], indent=2))


if __name__ == '__main__':
    main()
