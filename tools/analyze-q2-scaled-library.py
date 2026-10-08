#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the scaled/library composition and preserve its numerical failures."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
audit = module('analyze-q2-combined.py')
require = shared.require


def histories(rows, reference, candidate):
    for row in rows:
        match = re.fullmatch(r'(.+)-(\d+)-(prefill|last)\.f32', row['name'])
        require(match is not None, 'Unexpected frontier history')
        prefix, rep, phase = match.groups()
        files = [prefix + '-input.i32']
        if phase == 'last':
            files.append(prefix + '-' + rep + '-output.u32')
        row['matched_history'] = all((reference / p).read_bytes() ==
                                     (candidate / p).read_bytes() for p in files)


def main():
    models, roots, validation = {}, {}, {}
    for name, label, variant in (
            ('reference', 'q2-scaled-library-model-reference-r1', 'scaled-input'),
            ('candidate', 'q2-scaled-library-model-candidate-r1', 'scaled-library'),
            ('ud', 'q2-scaled-library-model-ud-r1', 'qualified')):
        path = ROOT / 'evidence' / label
        roots[name], models[name] = shared.arm(path, variant)
    replay = shared.compare(roots['reference'], roots['candidate'])
    histories(replay['frontiers'], roots['reference'], roots['candidate'])
    qualified, _, meta = shared.hc.read(ROOT / 'evidence/q2-explore-reference-r1',
                                       'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    numeric = {}
    for name in ('reference', 'candidate'):
        rows = shared.hc.frontiers(qualified, roots[name], logits=True, subset=True)
        histories(rows, qualified, roots[name])
        for row in rows:
            row['within_original_kl_limit'] = row['matched_history'] and row['kl_p_to_candidate'] <= .002
        numeric[name] = rows
    models['replay'] = replay
    models['qualified_reference'] = dict(meta=meta, comparisons=numeric, kl_limit=.002,
        limit='Historical implementation diagnostic on matched histories, not an independent teacher')
    old, _ = shared.arm(ROOT / 'evidence/q2-combined-scaled-control-r1', 'scaled-input')
    models['reference_replay'] = shared.compare(old, roots['reference'])
    models['relative_medians'] = {name: {key: models['candidate']['measurements'][key]['median'] /
        models[name]['measurements'][key]['median'] for key in
        ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')}
        for name in ('reference', 'ud')}
    fixtures = ['CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'config/models-157.inventory.json',
                'tests/q2_hc_pp.cpp', 'tests/q2_model.cpp', 'tests/q2_profile_markers.hip',
                'tests/q2_remote_test.py', 'tools/q2-remote.py', 'tools/q2-runner.py',
                'tools/q2_thermal.py', 'tools/q2_process.py', 'tools/q2_reuse.py']
    for label in ('q2-scaled-library-host-r1', 'q2-scaled-library-component-reference-r1',
                  'q2-scaled-library-component-candidate-r1', 'q2-scaled-library-model-reference-r1',
                  'q2-scaled-library-model-candidate-r1', 'q2-scaled-library-model-ud-r1'):
        path = ROOT / 'evidence' / label
        receipt = json.loads((path / 'results/result.json').read_text())
        transport = json.loads((path / 'transport.json').read_text())
        exits = [c['exit_code'] for c in receipt['commands']]
        expected = [0] * 6 if receipt['mode'] == 'cpu' else [0, 0, 1] if 'component' in label else [0] * 4
        require(exits == expected and transport['exit_code'] == expected[-1], 'Unpreserved command exit')
        for name, item in receipt['artifacts'].items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
            file = path / 'results' / name
            require(file.stat().st_size == item['bytes'] and audit.digest(file) == item['sha256'],
                    'Artifact changed: ' + name)
        if receipt['mode'] != 'cpu':
            require(receipt['locks'] == receipt['postflight_locks'] and
                    [(x['device'], x['inode']) for x in receipt['locks']] ==
                    [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)] and
                    not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Unresolved admission')
            require(receipt['binary_sha256'] == receipt['binary_sha256_after'], 'Binary changed')
        if receipt['model_access']:
            require(receipt['models_before'] == receipt['models_after'], 'Model witness changed')
        validation[label] = dict(audit.audit_capsule(path, fixtures), command_exits=exits,
                                 state=receipt['state'], model_access=receipt['model_access'])
    report = dict(scope='Cumulative arithmetic exploration, C1 pp2048/tg128; no numerical promotion',
                  model=models, validation=validation,
                  component=json.loads((ROOT / 'config/q2-scaled-library-components.json').read_text()),
                  numerical_pass=False, goal_met=False, promoted=False,
                  limits='Scaled and library operator failures remain; no task-quality, HTTP, concurrency or long-context acceptance')
    (ROOT / 'config/q2-scaled-library-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(relative_medians=models['relative_medians'], changed_files=replay['changed'],
                         matched_history_qualified_kl_max={k:max(
                             (x['kl_p_to_candidate'] for x in v if x['matched_history']), default=None)
                             for k,v in numeric.items()},
                         artifacts_verified=sum(v['artifacts_verified'] for v in validation.values())), indent=2))


if __name__ == '__main__':
    main()
