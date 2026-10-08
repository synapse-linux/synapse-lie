#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the paired-norm/library composition against fresh Q2 and UD controls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
audit = module('analyze-q2-combined.py')
library = module('analyze-q2-scaled-library.py')
sequence = module('analyze-q2-hc-sequence.py')
require = shared.require


def main():
    component = sequence.arm('q2-library-norm-component-r1', library=True)
    models, roots, validation = {}, {}, {}
    model_labels = [('reference', 'q2-library-norm-model-reference-r1', 'scaled-library'),
                    ('candidate', 'q2-library-norm-model-candidate-r1', 'library-norm-cycle'),
                    ('ud', 'q2-library-norm-model-ud-r1', 'qualified')]
    for name, label, variant in model_labels:
        roots[name], models[name] = shared.arm(ROOT / 'evidence' / label, variant)
        require(models[name]['within_arm_replay'] == dict(checks=9, exact=9),
                'Model replay changed: ' + name)
    replay = shared.compare(roots['reference'], roots['candidate'])
    library.histories(replay['frontiers'], roots['reference'], roots['candidate'])
    old, _ = shared.arm(ROOT / 'evidence/q2-scaled-library-model-candidate-r1', 'scaled-library')
    historical_replay = shared.compare(old, roots['reference'])
    qualified, _, _ = shared.hc.read(ROOT / 'evidence/q2-explore-reference-r1',
                                    'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    numerical = {}
    for name in ('reference', 'candidate'):
        rows = shared.hc.frontiers(qualified, roots[name], logits=True, subset=True)
        library.histories(rows, qualified, roots[name])
        for row in rows:
            row['within_original_kl_limit'] = row['matched_history'] and row['kl_p_to_candidate'] <= .002
        numerical[name] = rows
    relative = {name: {key: 100 * (models['candidate']['measurements'][key]['median'] /
        models[name]['measurements'][key]['median'] - 1) for key in
        ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')}
        for name in ('reference', 'ud')}
    # The model admission changes only the launcher's guard/test after the first
    # host/component cohort. Bind each runner to its own qualified host capsule.
    labels = ['q2-library-norm-host-r1', 'q2-library-norm-component-r1',
              'q2-library-norm-host-r2'] + [item[1] for item in model_labels]
    stable = ['CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tests/q2_model.cpp',
              'tests/q2_profile_markers.hip', 'tests/q2_hc_library_norm.cpp',
              'tests/q2_hc_sequence.cpp', 'tests/q2_hc_norm_half.cpp',
              'tests/q2_hc_moe_fused.cpp', 'config/models-157.inventory.json']
    scripts = ['tools/q2-runner.py', 'tools/q2-remote.py', 'tests/q2_remote_test.py',
               'tools/q2_process.py', 'tools/q2_thermal.py', 'tools/q2_reuse.py']
    for i, label in enumerate(labels):
        path = ROOT / 'evidence' / label
        r = json.loads((path / 'results/result.json').read_text())
        t = json.loads((path / 'transport.json').read_text())
        c = json.loads((path / 'collection.json').read_text())
        cpu = r['mode'] == 'cpu'
        exits = [x['exit_code'] for x in r['commands']]
        expected = [0] * 6 if cpu else [0, 0, 1] if i == 1 else [0] * 4
        require(exits == expected and t['exit_code'] == expected[-1], 'Exit mismatch')
        require(c['verified_artifacts'] == len(r['artifacts']), 'Collection count differs')
        for name, meta in r['artifacts'].items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
            p = path / 'results' / name
            require(p.stat().st_size == meta['bytes'] and audit.digest(p) == meta['sha256'], 'Artifact differs')
        if cpu:
            require(r['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not r['model_access'], 'Host scope')
            for log in ('03.log', '06.log'):
                require('100% tests passed out of 16' in (path / 'results' / log).read_text(), 'Incomplete host tests')
        else:
            require(r['locks'] == r['postflight_locks'] and
                    [(x['device'], x['inode']) for x in r['locks']] ==
                    [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)], 'Lease mismatch')
            require(not r['preflight_kfd'] and not r['postflight_kfd'], 'Unresolved KFD')
        host = ROOT / 'evidence' / ('q2-library-norm-host-r1' if i < 2 else 'q2-library-norm-host-r2')
        frozen = {}
        with tarfile.open(path / 'source.tar.gz') as cap, tarfile.open(host / 'source.tar.gz') as hcap:
            for name in scripts:
                content = cap.extractfile(name).read()
                require(content == hcap.extractfile(name).read(), 'Unqualified launcher cohort: ' + name)
                if i >= 2:
                    require(content == (ROOT / name).read_bytes(), 'Current launcher differs: ' + name)
                frozen[name] = hashlib.sha256(content).hexdigest()
        validation[label] = dict(audit.audit_capsule(path, stable), command_exits=exits,
            state=r['state'], model_access=r['model_access'], host_cohort=host.name, scripts=frozen)
    report = dict(scope='C1 pp2048/tg128; one warmup, three measured sessions; fan82; original models',
        component=component, model=models, replay=replay, historical_control_replay=historical_replay,
        median_change_percent=relative, qualified_reference=dict(kl_limit=.002, comparisons=numerical),
        validation=validation, numerical_pass=False, promoted=False, goal_met=False,
        limits='Decode includes legacy per-logit string allocation and finite checks inside timing; historical 26.049 token/s baseline requires matched reproduction. Inherited scaled/library numerical failures remain. No independent task-quality, HTTP, concurrency or long-context acceptance.')
    (ROOT / 'config/q2-library-norm-model-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(median_change_percent=relative, changed_files=replay['changed'],
        historical_control_changed=historical_replay['changed'],
        artifacts_verified=sum(v['artifacts_verified'] for v in validation.values())), indent=2))


if __name__ == '__main__':
    main()
